"""Record labelled hand-landmark samples with your own hand.

    python scripts/record_samples.py --label circle_cw

SPACE starts a take, SPACE again stops and saves it to samples/<label>/<time>.json.
Q or ESC quits. Each saved take is replayed immediately and marked PASS/FAIL.

Record each gesture several times, with both hands, at different distances. Also record
``--label none`` takes of normal movements (reaching, scratching, gripping the gear
knob, steering, waving): those must fire nothing.

Only landmark coordinates are saved, never camera images.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

import cv2

from gesturectl.app import Pipeline
from gesturectl.config import load_config
from gesturectl.overlay import draw
from gesturectl.recording import LABELS, SAMPLES_DIR, Recording, check, replay, save

MAX_TAKE_S = 15.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True, choices=LABELS)
    parser.add_argument("--config", help="YAML config (default: config/default.yaml)")
    parser.add_argument("--note", default="", help="free text stored in each file, e.g. 'left hand, far'")
    args = parser.parse_args()

    cfg = load_config(args.config)
    pipeline = Pipeline(cfg)
    take: Recording | None = None
    take_start = 0.0
    saved = 0
    status = f"label '{args.label}': SPACE to start a take, Q to quit"
    print(status)
    try:
        while True:
            result = pipeline.step()
            if result is None:
                continue
            if take is not None:
                take.frames.append((result.t, result.hand))
            img = draw(
                result.frame,
                hand=result.hand,
                engine=pipeline.engine,
                t=result.t,
                fps=pipeline.meter.fps,
                infer_ms=pipeline.meter.ms,
                banner=status,
                scale=cfg.overlay.scale,
                recording=take is not None,
            )
            cv2.imshow("record samples  (SPACE start/stop, Q quit)", img)
            key = cv2.waitKey(1) & 0xFF
            too_long = take is not None and result.t - take_start > MAX_TAKE_S

            if key == ord(" ") or too_long:
                if take is None:
                    take = Recording(label=args.label, frame_size=(cfg.camera.width, cfg.camera.height), note=args.note)
                    take_start = result.t
                    status = "recording... SPACE to stop"
                else:
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    path = SAMPLES_DIR / args.label / f"{stamp}.json"
                    save(take, path)
                    saved += 1
                    fired = [e.gesture for e in replay(take, cfg)]
                    ok, why = check(args.label, fired)
                    status = f"{'PASS' if ok else 'FAIL'}: {why}"
                    print(f"saved {path.name} ({len(take.frames)} frames) -> {status}")
                    take = None
            elif key in (ord("q"), 27):
                break
    finally:
        pipeline.close()
        cv2.destroyAllWindows()
    print(f"{saved} take(s) saved under {SAMPLES_DIR / args.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
