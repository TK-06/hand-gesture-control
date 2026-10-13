"""Replay recorded samples through the gesture engine and report PASS/FAIL per file.

    python scripts/replay_samples.py                    # everything under samples/
    python scripts/replay_samples.py samples/circle_cw  # one label
    python scripts/replay_samples.py --config my.yaml   # try different thresholds

Use it to tune config values against your own hand: edit the YAML, replay, repeat.
Exit code is 1 if any sample fails.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from gesturectl.config import load_config
from gesturectl.recording import SAMPLES_DIR, check, load, replay, sample_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path, help="sample files or folders (default: samples/)")
    parser.add_argument("--config", help="extra settings layered on config/default.yaml, e.g. config/car.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    files: list[Path] = []
    for p in args.paths or [SAMPLES_DIR]:
        if p.is_dir():
            files += sample_files(p) or sorted(p.glob("*.json"))
        elif p.is_file():
            files.append(p)
        else:
            print(f"not found: {p}")
    if not files:
        print("no samples found (record some with scripts/record_samples.py)")
        return 0

    results: Counter[tuple[str, bool]] = Counter()
    for path in files:
        rec = load(path)
        ok, why = check(rec.label, replay(rec, cfg), rec.reps)
        results[(rec.label, ok)] += 1
        print(f"{'PASS' if ok else 'FAIL'}  {rec.label:<13} {path.name:<24} {why}")

    print("\nlabel          pass  fail")
    for label in sorted({label for label, _ in results}):
        print(f"{label:<13} {results[(label, True)]:>5} {results[(label, False)]:>5}")
    failed = sum(n for (_, ok), n in results.items() if not ok)
    print(f"\n{len(files) - failed}/{len(files)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
