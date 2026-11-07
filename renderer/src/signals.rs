pub fn exit_now(code: i32) -> ! {
    // SAFETY: _exit has no preconditions and is async-signal-safe, so it is also fine in signal
    // handlers and in the allocator.
    unsafe { libc::_exit(code) }
}

fn set_signal_action(signal: libc::c_int, action: libc::sighandler_t) {
    // SAFETY: signal only records the action. It is either SIG_DFL or a handler from handle_signal.
    unsafe { libc::signal(signal, action) };
}

// Handlers can interrupt the program anywhere, so they must only make async-signal-safe calls.
pub fn handle_signal(signal: libc::c_int, handler: extern "C" fn(libc::c_int)) {
    set_signal_action(signal, handler as libc::sighandler_t);
}

pub fn reset_signal(signal: libc::c_int) {
    set_signal_action(signal, libc::SIG_DFL);
}

pub fn set_stop_signals_blocked(blocked: bool) {
    // SAFETY: all zeroes is a valid sigset_t for sigemptyset to initialize, signals stays valid for
    // every call, and a null pointer means the old mask isn't needed.
    unsafe {
        let mut signals: libc::sigset_t = std::mem::zeroed();
        libc::sigemptyset(&mut signals);
        libc::sigaddset(&mut signals, libc::SIGTERM);
        libc::sigaddset(&mut signals, libc::SIGINT);
        libc::sigprocmask(
            if blocked {
                libc::SIG_BLOCK
            } else {
                libc::SIG_UNBLOCK
            },
            &signals,
            std::ptr::null_mut(),
        );
    }
}
