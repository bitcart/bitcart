use std::alloc::{GlobalAlloc, Layout, System};
use std::io;
use std::os::fd::RawFd;
use std::sync::atomic::{AtomicI32, AtomicPtr, AtomicUsize, Ordering::Relaxed};

use crate::protocol::{RenderError, RenderErrorKind, Response};
use crate::signals::{exit_now, handle_signal};

const RENDER_LIMIT_MICROS: i64 = 250_000;
const HEAP_LIMIT: usize = 8 * 1024 * 1024;
#[cfg(target_os = "linux")]
const PROCESS_MEMORY: u64 = 32 * 1024 * 1024;

static USED: AtomicUsize = AtomicUsize::new(0);
static ACTIVE_LIMIT: AtomicUsize = AtomicUsize::new(usize::MAX);
static CLIENT: AtomicI32 = AtomicI32::new(-1);
static MEMORY_FRAME: AtomicPtr<Vec<u8>> = AtomicPtr::new(std::ptr::null_mut());
static TIMEOUT_FRAME: AtomicPtr<Vec<u8>> = AtomicPtr::new(std::ptr::null_mut());

struct CountingAllocator;

// Allocation failure cannot be recovered from on stable Rust, so the allocation that crosses the
// budget replies with a frame prepared in advance and ends the worker, which owns only this render.
fn check_budget(extra: usize) {
    if USED.load(Relaxed).saturating_add(extra) > ACTIVE_LIMIT.load(Relaxed) {
        reply_and_exit(&MEMORY_FRAME);
    }
}

fn reply_and_exit(frame: &AtomicPtr<Vec<u8>>) -> ! {
    let client = CLIENT.load(Relaxed);
    let frame = frame.load(Relaxed);
    if client >= 0 && !frame.is_null() {
        // SAFETY: frames come from Box::into_raw in enable_memory_budget and are never changed or
        // freed, so the pointer and length stay valid. write is async-signal-safe and doesn't
        // allocate. If the client is already closed, it only returns an error.
        unsafe { libc::write(client, (*frame).as_ptr().cast(), (*frame).len()) };
    }
    exit_now(0)
}

// SAFETY: every call is forwarded to System with the arguments it received, so System upholds the
// allocator contract. The counting only touches atomics, and going over budget ends the process
// instead of unwinding, so these methods never allocate or panic.
unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        check_budget(layout.size());
        USED.fetch_add(layout.size(), Relaxed);
        // SAFETY: the caller upholds alloc's contract for layout.
        unsafe { System.alloc(layout) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        USED.fetch_sub(layout.size(), Relaxed);
        // SAFETY: the caller got ptr from this allocator with this layout, and alloc and realloc
        // always get their memory from System.
        unsafe { System.dealloc(ptr, layout) }
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        check_budget(new_size.saturating_sub(layout.size()));
        USED.fetch_add(new_size.saturating_sub(layout.size()), Relaxed);
        USED.fetch_sub(layout.size().saturating_sub(new_size), Relaxed);
        // SAFETY: the caller upholds realloc's contract, and ptr came from System as in dealloc.
        unsafe { System.realloc(ptr, layout, new_size) }
    }
}

#[global_allocator]
static ALLOCATOR: CountingAllocator = CountingAllocator;

fn frame(kind: RenderErrorKind, message: &str) -> *mut Vec<u8> {
    let reply = Response::failed(RenderError {
        kind,
        line: None,
        message: message.to_string(),
    });
    let body = serde_json::to_vec(&reply).expect("a failure reply always serializes");
    let mut frame = (body.len() as u32).to_be_bytes().to_vec();
    frame.extend_from_slice(&body);
    Box::into_raw(Box::new(frame))
}

pub fn enable_memory_budget() {
    MEMORY_FRAME.store(
        frame(RenderErrorKind::Memory, "memory budget exceeded"),
        Relaxed,
    );
    TIMEOUT_FRAME.store(
        frame(RenderErrorKind::Timeout, "render time limit exceeded"),
        Relaxed,
    );
    ACTIVE_LIMIT.store(HEAP_LIMIT, Relaxed);
}

extern "C" fn render_timed_out(_: libc::c_int) {
    reply_and_exit(&TIMEOUT_FRAME);
}

pub fn install_render_timer() {
    handle_signal(libc::SIGALRM, render_timed_out);
}

fn arm_render_timer(micros: i64) {
    let timer = libc::itimerval {
        it_interval: libc::timeval {
            tv_sec: 0,
            tv_usec: 0,
        },
        it_value: libc::timeval {
            tv_sec: micros / 1_000_000,
            tv_usec: (micros % 1_000_000) as _,
        },
    };
    // SAFETY: timer is valid for the whole call, and a null pointer means the old value isn't
    // needed.
    unsafe { libc::setitimer(libc::ITIMER_REAL, &timer, std::ptr::null_mut()) };
}

// The timer starts before the request is read, so a client that sends nothing can't hold the worker.
pub fn start_render_limits(client: RawFd) {
    CLIENT.store(client, Relaxed);
    arm_render_timer(RENDER_LIMIT_MICROS);
}

pub fn stop_render_limits() {
    arm_render_timer(0);
}

// The OOM score has to be raised before the process stops being dumpable: that also makes
// /proc/self/oom_score_adj unwritable.
#[cfg(target_os = "linux")]
pub fn apply_process_limits() -> io::Result<()> {
    if let Err(error) = std::fs::write("/proc/self/oom_score_adj", "1000") {
        eprintln!("could not raise the OOM score: {error}");
    }
    let memory = libc::rlimit {
        rlim_cur: PROCESS_MEMORY,
        rlim_max: PROCESS_MEMORY,
    };
    // SAFETY: memory is valid for the call, and this only changes a limit on this process.
    if unsafe { libc::setrlimit(libc::RLIMIT_AS, &memory) } != 0 {
        return Err(io::Error::last_os_error());
    }
    let not_dumpable: libc::c_ulong = 0;
    // SAFETY: prctl gets the unsigned long it reads for PR_SET_DUMPABLE, and this only changes a
    // setting on this process.
    if unsafe { libc::prctl(libc::PR_SET_DUMPABLE, not_dumpable) } != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(not(target_os = "linux"))]
pub fn apply_process_limits() -> io::Result<()> {
    Ok(())
}
