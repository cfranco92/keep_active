#!/usr/bin/env python3
"""Cross-platform keep-active: block sleep and simulate subtle mouse movement."""

from __future__ import annotations

import argparse
import atexit
import signal
import subprocess
import sys
import time
from datetime import datetime

# --- macOS --------------------------------------------------------------------

def _darwin_start_caffeinate() -> subprocess.Popen[bytes]:
    return subprocess.Popen(["caffeinate", "-d", "-i"])


def _darwin_stop_caffeinate(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _darwin_simulate_activity() -> None:
    import ctypes
    import ctypes.util

    cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))

    class CGPoint(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    cg.CGEventCreate.restype = ctypes.c_void_p
    cg.CGEventCreate.argtypes = [ctypes.c_void_p]
    cg.CGEventGetLocation.restype = CGPoint
    cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
    cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    cg.CGEventCreateMouseEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        CGPoint,
        ctypes.c_uint32,
    ]
    cg.CGEventPost.restype = None
    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

    pos = cg.CGEventGetLocation(cg.CGEventCreate(None))
    x, y = pos.x, pos.y
    # kCGEventMouseMoved=5, kCGHIDEventTap=0
    for cx in (x + 1, x):
        e = cg.CGEventCreateMouseEvent(None, 5, CGPoint(cx, y), 0)
        cg.CGEventPost(0, e)
        time.sleep(0.1)


# --- Windows ------------------------------------------------------------------

def _win_set_execution_state(awake: bool) -> None:
    import ctypes
    from ctypes import wintypes

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002

    kernel32 = ctypes.windll.kernel32
    kernel32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
    kernel32.SetThreadExecutionState.restype = wintypes.DWORD

    if awake:
        kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
    else:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def _win_simulate_activity() -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        )

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]

    def send_move(dx: int, dy: int) -> None:
        mi = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, 0)
        inp = INPUT(type=INPUT_MOUSE, union=_INPUT_UNION(mi=mi))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    send_move(1, 0)
    time.sleep(0.1)
    send_move(-1, 0)


# --- main ---------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Prevent sleep and simulate user activity at an interval."
    )
    p.add_argument(
        "interval",
        nargs="?",
        type=int,
        default=60,
        help="Seconds between simulated activity (default: 60)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    interval = args.interval
    if interval < 1:
        print("interval must be at least 1 second.", file=sys.stderr)
        sys.exit(1)

    plat = sys.platform
    if plat == "darwin":
        caffeinate: subprocess.Popen[bytes] | None = None

        def cleanup_darwin() -> None:
            _darwin_stop_caffeinate(caffeinate)

        try:
            caffeinate = _darwin_start_caffeinate()
        except FileNotFoundError:
            print("caffeinate not found (macOS only).", file=sys.stderr)
            sys.exit(1)

        atexit.register(cleanup_darwin)

        def handle_exit(signum: int, frame: object | None) -> None:
            cleanup_darwin()
            print("")
            print("Stopping keep-active script...")
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

        simulate = _darwin_simulate_activity

    elif plat == "win32":

        def cleanup_win() -> None:
            _win_set_execution_state(False)

        _win_set_execution_state(True)
        atexit.register(cleanup_win)

        def handle_exit(signum: int, frame: object | None) -> None:
            cleanup_win()
            print("")
            print("Stopping keep-active script...")
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_exit)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handle_exit)

        simulate = _win_simulate_activity

    else:
        print(
            f"Unsupported platform: {plat!r}. Use macOS or Windows.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"Starting keep-active script (interval: {interval}s). "
        "Press Ctrl+C to stop."
    )
    print(f"Running — will simulate activity every {interval} seconds.")

    while True:
        simulate()
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] Activity simulated. Next in {interval}s...")
        time.sleep(interval)


if __name__ == "__main__":
    main()
