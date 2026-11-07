use std::io::{BufRead, BufReader, Read, Write};
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

use serde_json::{Value, json};

const RENDERER: &str = env!("CARGO_BIN_EXE_bitcart-renderer");

fn slow_request() -> String {
    json!({
        "text": "{% for i in range(100000) %}{% set product = big * big %}{% endfor %}",
        "context": {"big": {"$decimal": "9".repeat(4000)}},
    })
    .to_string()
}

struct Server {
    child: Child,
    socket: PathBuf,
    _directory: TempDirectory,
}

struct TempDirectory(PathBuf);

impl Drop for TempDirectory {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

impl Server {
    fn launch(name: &str, workers: usize, mut command: Command) -> Self {
        let directory =
            std::env::temp_dir().join(format!("renderer-{name}-{}", std::process::id()));
        std::fs::create_dir_all(&directory).unwrap();
        let socket = directory.join("renderer.sock");
        let child = command
            .env("RENDERER_SOCKET", &socket)
            .env("RENDERER_WORKERS", workers.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        Self {
            child,
            socket,
            _directory: TempDirectory(directory),
        }
    }

    fn start(name: &str, workers: usize) -> Self {
        let server = Self::launch(name, workers, Command::new(RENDERER));
        let deadline = Instant::now() + Duration::from_secs(5);
        while UnixStream::connect(&server.socket).is_err() {
            assert!(Instant::now() < deadline, "renderer did not start");
            std::thread::sleep(Duration::from_millis(10));
        }
        server
    }

    fn wait_for_log_line(&mut self, prefix: &'static str) -> Option<String> {
        let lines = BufReader::new(self.child.stderr.take().unwrap()).lines();
        let (found, result) = mpsc::channel();
        std::thread::spawn(move || {
            let line = lines
                .map_while(Result::ok)
                .find(|line| line.starts_with(prefix));
            let _ = found.send(line);
        });
        result.recv_timeout(Duration::from_secs(5)).ok().flatten()
    }

    fn send(&self, body: &[u8]) -> Value {
        self.send_claiming_size(body.len() as u32, body)
    }

    fn send_claiming_size(&self, size: u32, body: &[u8]) -> Value {
        let mut stream = UnixStream::connect(&self.socket).unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(5)))
            .unwrap();
        stream.write_all(&size.to_be_bytes()).unwrap();
        stream.write_all(body).unwrap();
        let mut size = [0u8; 4];
        stream.read_exact(&mut size).unwrap();
        let mut reply = vec![0u8; u32::from_be_bytes(size) as usize];
        stream.read_exact(&mut reply).unwrap();
        serde_json::from_slice(&reply).unwrap()
    }

    fn render(&self, text: &str) -> Value {
        self.send(json!({"text": text}).to_string().as_bytes())
    }
}

impl Drop for Server {
    fn drop(&mut self) {
        if matches!(self.child.try_wait(), Ok(None)) {
            terminate(&self.child);
        }
        let _ = self.child.wait();
    }
}

fn terminate(child: &Child) {
    // SAFETY: kill takes plain integers, and callers only pass a child they haven't reaped yet.
    unsafe { libc::kill(child.id() as i32, libc::SIGTERM) };
}

fn error_kind(reply: &Value) -> &str {
    reply["error"]["kind"].as_str().unwrap_or("")
}

#[cfg(target_os = "linux")]
fn worker_pid(server: &Server) -> u32 {
    let parent = server.child.id();
    let children = format!("/proc/{parent}/task/{parent}/children");
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let found = std::fs::read_to_string(&children).unwrap();
        if let Some(pid) = found.split_whitespace().next() {
            return pid.parse().unwrap();
        }
        assert!(Instant::now() < deadline, "renderer has no worker");
        std::thread::sleep(Duration::from_millis(10));
    }
}

#[test]
fn renders_and_reports_failures_by_kind() {
    let server = Server::start("kinds", 1);
    let reply = server.send(
        json!({"text": "Hello {{ name }}", "context": {"name": "<b>"}, "autoescape": true})
            .to_string()
            .as_bytes(),
    );
    assert_eq!(reply["text"], "Hello &lt;b&gt;");
    let reply = server.render("line one\n{% if %}");
    assert_eq!(error_kind(&reply), "syntax");
    assert_eq!(reply["error"]["line"], 2);
    assert_eq!(error_kind(&server.render("{{ 1 / 0 }}")), "runtime");
    assert_eq!(error_kind(&server.send(b"not json")), "request");
}

#[test]
fn check_compiles_without_rendering() {
    let server = Server::start("check", 1);
    assert_eq!(
        server.send(
            json!({"text": "{{ 1 / 0 }}", "check": true})
                .to_string()
                .as_bytes()
        )["ok"],
        true
    );
    assert_eq!(
        error_kind(
            &server.send(
                json!({"text": "{% if %}", "check": true})
                    .to_string()
                    .as_bytes()
            )
        ),
        "syntax"
    );
}

#[test]
fn memory_budget_stops_the_render_and_keeps_serving() {
    let server = Server::start("memory", 1);
    let reply = server.render("{{ 'x' * 20000000 }}");
    assert_eq!(error_kind(&reply), "memory");
    assert_eq!(server.render("still {{ 'here' }}")["text"], "still here");
}

#[test]
fn time_limit_stops_the_render_and_keeps_serving() {
    let server = Server::start("time", 1);
    let reply = server.send(slow_request().as_bytes());
    assert_eq!(error_kind(&reply), "timeout", "{reply}");
    assert_eq!(server.render("still {{ 'here' }}")["text"], "still here");
}

#[test]
fn socket_is_open_to_other_users() {
    let server = Server::start("mode", 1);
    let mode = std::fs::metadata(&server.socket)
        .unwrap()
        .permissions()
        .mode();
    assert_eq!(mode & 0o777, 0o666);
}

#[test]
fn caps_output_and_refuses_oversized_requests() {
    let server = Server::start("caps", 1);
    assert_eq!(
        error_kind(&server.render("{% for i in range(100000) %}{{ 'x' * 100 }}{% endfor %}")),
        "output"
    );
    let reply = server.send_claiming_size(2_000_000, b"");
    assert_eq!(error_kind(&reply), "request");
}

#[test]
fn slow_client_cannot_hold_a_worker() {
    let server = Server::start("idle", 1);
    let idle = UnixStream::connect(&server.socket).unwrap();
    std::thread::sleep(Duration::from_millis(350));
    assert_eq!(server.render("ok")["text"], "ok");
    drop(idle);
}

#[test]
fn skips_requests_whose_client_left() {
    let server = Server::start("left", 1);
    let slow = slow_request();
    let mut busy = UnixStream::connect(&server.socket).unwrap();
    busy.write_all(&(slow.len() as u32).to_be_bytes()).unwrap();
    busy.write_all(slow.as_bytes()).unwrap();
    std::thread::sleep(Duration::from_millis(20));
    for _ in 0..4 {
        let mut queued = UnixStream::connect(&server.socket).unwrap();
        queued
            .write_all(&(slow.len() as u32).to_be_bytes())
            .unwrap();
        queued.write_all(slow.as_bytes()).unwrap();
    }
    let started = Instant::now();
    assert_eq!(server.render("ok")["text"], "ok");
    assert!(
        started.elapsed() < Duration::from_secs(1),
        "{:?}",
        started.elapsed()
    );
    drop(busy);
}

#[test]
fn recycles_workers_without_failing_renders() {
    let server = Server::start("recycle", 1);
    for index in 0..1100 {
        assert_eq!(
            server.render(&format!("{index}"))["text"],
            index.to_string()
        );
    }
}

#[cfg(target_os = "linux")]
#[test]
fn replaces_workers_after_their_render_limit() {
    let server = Server::start("replace", 1);
    let first = worker_pid(&server);
    for _ in 0..1000 {
        assert_eq!(server.render("ok")["text"], "ok");
    }
    let deadline = Instant::now() + Duration::from_secs(5);
    while worker_pid(&server) == first {
        assert!(Instant::now() < deadline, "worker was not replaced");
        std::thread::sleep(Duration::from_millis(10));
    }
}

#[cfg(target_os = "linux")]
#[test]
fn workers_run_with_their_limits() {
    let server = Server::start("applied", 1);
    assert_eq!(server.render("ok")["text"], "ok");
    let worker = worker_pid(&server);
    let limits = std::fs::read_to_string(format!("/proc/{worker}/limits")).unwrap();
    let address_space = limits
        .lines()
        .find(|line| line.starts_with("Max address space"))
        .unwrap();
    assert!(address_space.contains("33554432"), "{address_space}");
    let oom_score = std::fs::read_to_string(format!("/proc/{worker}/oom_score_adj")).unwrap();
    assert_eq!(oom_score.trim(), "1000");
}

#[test]
fn caps_the_worker_count() {
    let mut server = Server::launch("cap", 1000, Command::new(RENDERER));
    assert_eq!(
        server.wait_for_log_line("starting").as_deref(),
        Some("starting 32 workers")
    );
}

#[cfg(target_os = "linux")]
#[test]
fn workers_refuse_to_run_without_their_limits() {
    let mut limited = Command::new("sh");
    limited
        .arg("-c")
        .arg(format!("ulimit -v 31000; exec {RENDERER}"));
    let mut server = Server::launch("limits", 1, limited);
    assert!(
        server
            .wait_for_log_line("could not apply process limits")
            .is_some(),
        "the failure was not logged"
    );
    let mut request = UnixStream::connect(&server.socket).unwrap();
    request
        .set_read_timeout(Some(Duration::from_millis(500)))
        .unwrap();
    let body = json!({"text": "ok"}).to_string();
    request
        .write_all(&(body.len() as u32).to_be_bytes())
        .unwrap();
    request.write_all(body.as_bytes()).unwrap();
    let served = request.read(&mut [0u8; 4]).is_ok_and(|size| size > 0);
    assert!(!served, "a worker served a request without its limits");
}

#[test]
fn stops_workers_on_terminate() {
    let mut server = Server::start("stop", 2);
    terminate(&server.child);
    let deadline = Instant::now() + Duration::from_secs(2);
    while server.child.try_wait().unwrap().is_none() {
        assert!(Instant::now() < deadline, "renderer ignored SIGTERM");
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(UnixStream::connect(&server.socket).is_err());
}
