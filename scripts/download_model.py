"""Download the MediaPipe Hand Landmarker model bundle into models/.

Usage:  python scripts/download_model.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

# Versioned URL (not ".../latest/...") so every install gets the same model.
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
DEST = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    args = parser.parse_args()

    if DEST.exists() and not args.force:
        print(f"Already present: {DEST} ({DEST.stat().st_size} bytes)")
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_suffix(".part")
    print(f"Downloading {MODEL_URL}")
    with urllib.request.urlopen(MODEL_URL, timeout=60) as resp, open(tmp, "wb") as out:
        out.write(resp.read())
    tmp.replace(DEST)

    digest = hashlib.sha256(DEST.read_bytes()).hexdigest()
    print(f"Saved {DEST} ({DEST.stat().st_size} bytes, sha256 {digest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
