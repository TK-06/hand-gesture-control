"""Run the gesture controller: ``python -m gesturectl [--config PATH] [--no-window]``.

Stage 1-2: recognized gestures are printed (and shown in the debug window). Sending
them to the phone comes with the action backends in Stage 3-4.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from gesturectl.app import Pipeline
from gesturectl.config import load_config

log = logging.getLogger("gesturectl")

BANNER_S = 1.5
STATS_EVERY_S = 5.0
MAX_EMPTY_READS = 50


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gesturectl", description=__doc__.splitlines()[0])
    parser.add_argument("--config", help="YAML config (default: config/default.yaml)")
    parser.add_argument("--no-window", action="store_true", help="headless: no debug window")
    parser.add_argument("--duration", type=float, help="stop after this many seconds")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(args.config)
    try:
        pipeline = Pipeline(cfg)
    except (RuntimeError, FileNotFoundError, NotImplementedError) as exc:
        log.error("%s", exc)
        return 2
    log.info("%s -> processing %dx%d", pipeline.camera.describe(), cfg.camera.width, cfg.camera.height)

    window = not args.no_window
    if window:
        import cv2

        from gesturectl.overlay import draw

    start = time.monotonic()
    next_stats = start + STATS_EVERY_S
    banner, banner_until = "", 0.0
    empty_reads = 0
    frames = frames_with_hand = 0
    try:
        while True:
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
        pipeline.close()
        if window:
            cv2.destroyAllWindows()
    log.info("stopped after %d frames", frames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
