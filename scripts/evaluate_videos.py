"""Run recorded videos through the gesture pipeline and score the results.

    python scripts/evaluate_videos.py                   # everything under videos/
    python scripts/evaluate_videos.py --fps 12          # simulate the Pi's processing rate
    python scripts/evaluate_videos.py --timeline        # list every detection with its time
    python scripts/evaluate_videos.py --config my.yaml  # try other thresholds

For each video: what was detected vs what the filename (or the mixed take's .txt) says
was performed. The summary gives the hit rate per gesture and false triggers, including
false triggers per hour of footage where nothing should fire.

Hand tracking results are cached in videos/.cache, so re-running with different gesture
thresholds is fast. Changing camera/tracker settings or --fps re-runs MediaPipe.

--export-samples saves gesture and none clips as landmark samples in samples/, so pytest
keeps checking them (do this once the results look right).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from gesturectl.config import GESTURES, load_config
from gesturectl.evaluation import Score, collapse, fmt_time, score_gesture_clip, score_mixed, score_negative
from gesturectl.recording import SAMPLES_DIR, replay, save
from gesturectl.video import VIDEOS_DIR, find_videos, landmarks_for, parse_video_name, read_labels


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path, help="videos or folders (default: videos/)")
    parser.add_argument("--config", help="YAML config (default: config/default.yaml)")
    parser.add_argument("--fps", type=float, help="process only this many frames per second (simulate the Pi)")
    parser.add_argument("--tolerance", type=float, default=2.5, help="seconds of slack for mixed-take labels")
    parser.add_argument("--timeline", action="store_true", help="print every detection with its time")
    parser.add_argument("--export-samples", action="store_true", help="save gesture/none clips to samples/")
    parser.add_argument("--no-cache", action="store_true", help="always re-run hand tracking")
    args = parser.parse_args()

    cfg = load_config(args.config)
    videos = find_videos(args.paths or [VIDEOS_DIR])
    if not videos:
        print("no videos found (record some with scripts/record_video.py)")
        return 0

    total = Score()
    false_by_kind: Counter[str] = Counter()  # gesture / negative / mixed
    infer_ms: list[float] = []
    for path in videos:
        try:
            label = parse_video_name(path.stem)
        except ValueError as exc:
            print(f"SKIP  {path.name}: {exc}")
            continue
        if sys.stdout.isatty():
            print(f"... {path.name}", end="\r", flush=True)  # overwritten by the result line
        rec, stats = landmarks_for(path, cfg, args.fps, use_cache=not args.no_cache)
        if stats is not None and stats.frames_processed:
            infer_ms.append(stats.avg_inference_ms)
        events = replay(rec, cfg)
        duration = rec.frames[-1][0] if rec.frames else 0.0
        with_hand = sum(h is not None for _, h in rec.frames)
        seen = f"hand in {100 * with_hand / max(len(rec.frames), 1):.0f}% of frames"

        if label.kind == "gesture":
            score = score_gesture_clip(label.label, label.reps, events)
            result = f"{score.hit[label.label]}/{label.reps} {label.label}"
        elif label.kind == "negative":
            score = score_negative(events, duration)
            result = "clean" if not score.false else f"{len(score.false)} false"
        else:
            labels_file = path.with_suffix(".txt")
            if not labels_file.exists():
                print(f"MIXED {path.name}: no {labels_file.name}, showing detections only")
                for t, g in collapse(events):
                    print(f"        {fmt_time(t):>7}  {g}")
                continue
            score = score_mixed(read_labels(labels_file), events, args.tolerance)
            result = f"{sum(score.hit.values())}/{sum(score.expected.values())} hit"
        total.add(score)
        false_by_kind[label.kind] += len(score.false)

        flag = "OK  " if not score.missed and not score.false else "FAIL"
        extra = ""
        if score.false:
            extra += "  false: " + ", ".join(f"{fmt_time(t)} {g}" for t, g in score.false)
        if label.kind == "mixed" and score.missed:
            extra += "  missed: " + ", ".join(f"{fmt_time(t)} {g}" for t, g in score.missed)
        print(f"{flag}  {path.name:<36} {result:<22} ({fmt_time(duration)}, {seen}){extra}")
        if args.timeline:
            for t, g in collapse(events):
                print(f"        {fmt_time(t):>7}  {g}")

        if args.export_samples and label.label != "drive" and label.kind != "mixed":
            sample_label = label.label  # gesture name or "none"
            target = SAMPLES_DIR / sample_label / f"{path.stem}.json"
            save(rec, target)
            print(f"        exported -> {target.relative_to(SAMPLES_DIR.parent)}")

    _summary(total, false_by_kind, infer_ms, args.fps)
    return 0


def _summary(total: Score, false_by_kind: Counter, infer_ms: list[float], fps: float | None) -> None:
    print("\ngesture          hit / performed")
    for g in GESTURES:
        if total.expected[g]:
            pct = 100 * total.hit[g] / total.expected[g]
            print(f"  {g:<14} {total.hit[g]:>3} / {total.expected[g]:<3}  ({pct:.0f}%)")
    if not total.expected:
        print("  (no gesture or mixed clips)")

    by_gesture = Counter(g for _, g in total.false)
    print(f"\nfalse triggers: {len(total.false)}" + (f"  {dict(by_gesture)}" if by_gesture else ""))
    print(f"  in gesture clips (wrong or extra gesture): {false_by_kind['gesture']}")
    print(f"  in mixed takes: {false_by_kind['mixed']}")
    if total.negative_s:
        minutes = total.negative_s / 60.0
        rate = 60.0 * false_by_kind["negative"] / minutes
        print(f"  in {minutes:.1f} min of no-gesture footage: {false_by_kind['negative']} ({rate:.1f} per hour)")
    if infer_ms:
        avg = sum(infer_ms) / len(infer_ms)
        print(
            f"\nhand tracking: {avg:.1f} ms per frame on this machine (~{1000 / avg:.0f} fps max)"
            + (f"; processed at {fps:g} fps" if fps else "")
        )


if __name__ == "__main__":
    sys.exit(main())
