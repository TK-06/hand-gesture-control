"""Record raw camera video for testing and tuning (runs headless, e.g. over SSH on the Pi).

    python scripts/record_video.py videos/swipe_left_driver_day_1.mp4 --duration 45
    python scripts/record_video.py videos/drive_day_1.mp4 --split 300      # long drive, 5-min files

The filename is the label (see src/gesturectl/video.py):
  <gesture>_...   one gesture performed 5 times (add _x3 for 3 times)
  none_...        look-alike or random movements: nothing should fire
  drive_...       real driving, no gestures
  mixed_...       normal movements with gestures thrown in, plus a same-named .txt
                  with one "m:ss gesture" line per gesture you did

Frames are saved raw (no flip, rotation or crop), so the camera orientation can still be
changed in the config afterwards. A .json sidecar stores each frame's real timestamp.
Stop with Ctrl+C, or use --duration.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
import time
from pathlib import Path

from gesturectl.camera import open_camera
from gesturectl.config import load_config
from gesturectl.video import VideoRecorder, parse_video_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path, help="e.g. videos/swipe_left_driver_day_1.mp4")
    parser.add_argument("--duration", type=float, help="stop after this many seconds (default: Ctrl+C)")
    parser.add_argument("--split", type=float, help="cut into files of this many seconds (long drives)")
    parser.add_argument("--countdown", type=float, default=3.0, help="seconds to wait before recording")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--config", help="YAML config (camera source / index)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing file")
    args = parser.parse_args()

    out: Path = args.output
    if out.suffix.lower() != ".mp4":
        parser.error("output must end in .mp4")
    try:
        label = parse_video_name(out.stem)
    except ValueError as exc:
        parser.error(f"{exc}. The filename is the label, e.g. swipe_left_driver_day_1.mp4")
    if out.exists() and not args.force:
        parser.error(f"{out} exists (use --force to overwrite)")

    cfg = load_config(args.config)
    cam_cfg = dataclasses.replace(
        cfg.camera, width=args.width, height=args.height, fps=args.fps, flip_horizontal=False, rotate=0
    )
    camera = open_camera(cam_cfg)
    what = f"{label.label} x{label.reps}" if label.kind == "gesture" else label.label
    print(f"{camera.describe()}\nlabel: {what}")
    if label.kind == "mixed":
        print(f"remember to write {out.with_suffix('.txt').name}: one 'm:ss gesture' line per gesture")

    recorder = VideoRecorder(out, args.fps, split_s=args.split, source=camera.describe())
    try:
        for remaining in range(int(args.countdown), 0, -1):
            print(f"starting in {remaining}...", flush=True)
            time.sleep(1.0)
        print("RECORDING (Ctrl+C to stop)", flush=True)
        start = time.monotonic()
        next_report = start + 5.0
        frames = 0
        while True:
            frame = camera.read()
            now = time.monotonic()
            if frame is None:
                continue
            recorder.add(frame, now - start)
            frames += 1
            if now >= next_report:
                print(f"  {now - start:5.0f} s  {frames / (now - start):4.1f} fps", flush=True)
                next_report = now + 5.0
            if args.duration and now - start >= args.duration:
                break
    except KeyboardInterrupt:
        pass
    finally:
        written = recorder.close()
        camera.close()

    for path in written:
        size_mb = path.stat().st_size / 1e6
        print(f"saved {path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
