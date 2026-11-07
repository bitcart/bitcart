use std::io;
use std::os::fd::AsRawFd;
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::UnixListener;
use std::sync::atomic::{AtomicI32, Ordering::Relaxed};
use std::time::Duration;

use bitcart_renderer::limits::{
    apply_process_limits, enable_memory_budget, install_render_timer, start_render_limits,
    stop_render_limits,
};
use bitcart_renderer::protocol::serve;
use bitcart_renderer::signals::{exit_now, handle_signal, reset_signal, set_stop_signals_blocked};

const DEFAULT_SOCKET: &str = "/run/renderer/renderer.sock";
const MAX_RENDERS: usize = 1000;
const MAX_WORKERS: usize = 32;
const WORKER_FAILED: i32 = 2;
const RESPAWN_DELAY: Duration = Duration::from_millis(100);

static WORKERS: [AtomicI32; MAX_WORKERS] = [const { AtomicI32::new(0) }; MAX_WORKERS];

extern "C" fn shut_down(_: libc::c_int) {
    for worker in &WORKERS {
        let pid = worker.load(Relaxed);
        if pid > 0 {
            // SAFETY: kill takes plain integers and is async-signal-safe. pid is a worker we forked
            // and haven't reaped yet, because forget clears its slot as soon as it's reaped.
            unsafe { libc::kill(pid, libc::SIGKILL) };
        }
    }
    exit_now(0)
}

fn worker(listener: &UnixListener) -> ! {
    reset_signal(libc::SIGTERM);
    reset_signal(libc::SIGINT);
    set_stop_signals_blocked(false);
    if let Err(error) = apply_process_limits() {
        eprintln!("could not apply process limits: {error}");
        exit_now(WORKER_FAILED);
    }
    install_render_timer();
    for _ in 0..MAX_RENDERS {
        let Ok((stream, _)) = listener.accept() else {
            exit_now(WORKER_FAILED);
        };
        start_render_limits(stream.as_raw_fd());
        let _ = serve(stream);
        stop_render_limits();
    }
    exit_now(0)
}

// Stop signals stay blocked until the new worker is recorded, otherwise shutting down at that
// moment would orphan it.
fn spawn(listener: &UnixListener) -> io::Result<()> {
    set_stop_signals_blocked(true);
    // SAFETY: the parent only ever has this one thread, so the child can't inherit a lock held by
    // another thread and can keep using the allocator.
    let pid = unsafe { libc::fork() };
    let fork_error = io::Error::last_os_error();
    if pid == 0 {
        worker(listener);
    }
    if pid > 0
        && let Some(slot) = WORKERS.iter().find(|slot| slot.load(Relaxed) == 0)
    {
        slot.store(pid, Relaxed);
    }
    set_stop_signals_blocked(false);
    if pid < 0 {
        return Err(fork_error);
    }
    Ok(())
}

fn forget(pid: i32) {
    if let Some(slot) = WORKERS.iter().find(|slot| slot.load(Relaxed) == pid) {
        slot.store(0, Relaxed);
    }
}

fn worker_count() -> usize {
    std::env::var("RENDERER_WORKERS")
        .ok()
        .and_then(|value| value.parse().ok())
        .filter(|count| *count > 0)
        .or_else(|| {
            std::thread::available_parallelism()
                .ok()
                .map(|count| count.get())
        })
        .unwrap_or(1)
        .min(MAX_WORKERS)
}

fn bind() -> io::Result<UnixListener> {
    let path = std::env::var("RENDERER_SOCKET").unwrap_or_else(|_| DEFAULT_SOCKET.to_string());
    let _ = std::fs::remove_file(&path);
    let listener = UnixListener::bind(&path)?;
    std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o666))?;
    eprintln!("renderer listening on {path}");
    Ok(listener)
}

fn main() -> io::Result<()> {
    let listener = bind()?;
    handle_signal(libc::SIGTERM, shut_down);
    handle_signal(libc::SIGINT, shut_down);
    enable_memory_budget();
    let count = worker_count();
    eprintln!("starting {count} workers");
    for _ in 0..count {
        spawn(&listener)?;
    }
    loop {
        let mut status = 0;
        // SAFETY: status is valid for the whole call.
        let pid = unsafe { libc::waitpid(-1, &mut status, 0) };
        if pid <= 0 {
            continue;
        }
        forget(pid);
        if libc::WIFEXITED(status) && libc::WEXITSTATUS(status) == WORKER_FAILED {
            std::thread::sleep(RESPAWN_DELAY);
        }
        while let Err(error) = spawn(&listener) {
            eprintln!("respawn failed: {error}");
            std::thread::sleep(RESPAWN_DELAY);
        }
    }
}
