"""Run the gesture controller: ``python -m gesturectl [--config PATH] [--no-window]``.

Recognized gestures are logged, shown in the debug window, and handed to the action
backend from the config: ``print`` (laptop) or ``bt_hid`` (the Bluetooth remote service
that presses media keys on the phone; used by config/car.yaml).
"""

from __future__ import annotations

import argparse
import faulthandler
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from gesturectl.actions import make_backend
from gesturectl.app import Pipeline
from gesturectl.config import load_config
from gesturectl.logsetup import setup_logging

log = logging.getLogger("gesturectl")

BANNER_S = 1.5
STATS_EVERY_S = 5.0
MAX_EMPTY_READS = 50

# Stall watchdog: if the main loop makes no progress for --stall-timeout seconds, a C
# thread (faulthandler; works even when the main thread is stuck inside native code)
# writes every thread's stack, then exits with status 1 so systemd restarts the service.
# Seen 2026-10-15: the program froze with no log output, ignored SIGTERM, and systemd
# only got rid of it with SIGKILL after 90 s.
STALL_TIMEOUT_S = 20.0
STALL_REARM_S = 1.0

# Set by SIGTERM (systemd stop). The loop checks it between frames, so the camera and
# tracker are never interrupted mid-call: picamera2 interrupted inside capture_array()
# could then hang in close() until systemd killed it 90 s later.
_stop = threading.Event()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gesturectl", description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="extra settings layered on config/default.yaml, e.g. config/car.yaml")
    parser.add_argument("--no-window", action="store_true", help="headless: no debug window")
    parser.add_argument("--duration", type=float, help="stop after this many seconds")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--log-file", help="also write a rotating log file (1 MB x 5), e.g. logs/gesturectl.log")
    parser.add_argument(
        "--stall-timeout",
        type=float,
        default=STALL_TIMEOUT_S,
        help="exit (so systemd restarts us) if no frame is processed for this many seconds; thread stacks go to "
        "<log-file>-stall.log, or stderr without --log-file (0 = off)",
    )
    args = parser.parse_args(argv)

    setup_logging(args.log_level, args.log_file)
    _stop.clear()
    signal.signal(signal.SIGTERM, _request_stop)  # systemd stop: finish the frame, then shut down
    cfg = load_config(args.config)
    backend = make_backend(cfg)
    try:
        pipeline = Pipeline(cfg)
    except (RuntimeError, FileNotFoundError, NotImplementedError) as exc:
        log.error("%s", exc)
        return 2
    log.info(
        "%s -> processing %dx%d; actions -> %s", pipeline.camera.describe(), cfg.camera.width, cfg.camera.height,
        cfg.actions.backend,
    )

    window = not args.no_window
    if window:
        import cv2

        from gesturectl.overlay import draw

    stall_file = _open_stall_file(args.log_file) if args.stall_timeout > 0 else None
    last_armed = -float("inf")
    start = time.monotonic()
    next_stats = start + STATS_EVERY_S
    banner, banner_until = "", 0.0
    empty_reads = 0
    frames = frames_with_hand = 0
    try:
        while not _stop.is_set():
            if stall_file is not None and time.monotonic() - last_armed >= STALL_REARM_S:
                last_armed = time.monotonic()
                faulthandler.dump_traceback_later(args.stall_timeout, exit=True, file=stall_file)
            result = pipeline.step()
            if result is None:
                empty_reads += 1
                if empty_reads >= MAX_EMPTY_READS:
                    log.error("camera stopped delivering frames")
                    return 1
                continue
            empty_reads = 0
            frames += 1
            frames_with_hand += result.hand is not None

            for event in result.events:
                log.info("ACTION %-12s (gesture %s)", event.action, event.gesture)
                backend.send(event.action)
                banner, banner_until = f"{event.action}  ({event.gesture})", result.t + BANNER_S

            if result.t >= next_stats:
                log.info(
                    "%.1f fps, inference %.1f ms, hand in %d%% of frames",
                    pipeline.meter.fps,
                    pipeline.meter.ms,
                    round(100 * frames_with_hand / max(frames, 1)),
                )
                next_stats = result.t + STATS_EVERY_S

            if window:
                img = draw(
                    result.frame,
                    hand=result.hand,
                    engine=pipeline.engine,
                    t=result.t,
                    fps=pipeline.meter.fps,
                    infer_ms=pipeline.meter.ms,
                    banner=banner if result.t < banner_until else "",
                    scale=cfg.overlay.scale,
                )
                cv2.imshow("gesturectl  (q to quit)", img)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break

            if args.duration is not None and result.t - start >= args.duration:
                break
    except KeyboardInterrupt:
        pass
    finally:
        # Left armed while closing: a hang in close() is then also caught and restarted.
        pipeline.close()
        backend.close()
        if window:
            cv2.destroyAllWindows()
        faulthandler.cancel_dump_traceback_later()
        if stall_file is not None and stall_file is not sys.stderr:
            stall_file.close()
    if _stop.is_set():
        log.info("stop requested (SIGTERM)")
    log.info("stopped after %d frames", frames)
    return 0


def _request_stop(signum, frame) -> None:
    _stop.set()


def _open_stall_file(log_file: str | None):
    """Where the watchdog writes thread stacks: ``<log-file stem>-stall.log`` next to the
    log file (kept across restarts), else stderr."""
    if not log_file:
        return sys.stderr
    path = Path(log_file)
    path = path.with_name(f"{path.stem}-stall{path.suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a", encoding="utf-8")
    stamp = datetime.now().isoformat(timespec="seconds")
    f.write(f"--- watchdog armed {stamp} pid {os.getpid()} ---\n")
    f.flush()
    return f


if __name__ == "__main__":
    sys.exit(main())
