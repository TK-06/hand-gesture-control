"""Recorded landmark sequences ("samples"): file format, replay, and pass/fail rules.

A sample is one JSON file under ``samples/<label>/``. It stores landmarks only (no
images), already in the engine's coordinate space, so replaying it runs exactly the
same gesture logic as the live camera.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from gesturectl.config import DEFAULT_MAPPING, GESTURES, PROJECT_ROOT, AppConfig
from gesturectl.engine import Event, GestureEngine
from gesturectl.hand import HandFrame

SCHEMA_VERSION = 1
NONE_LABEL = "none"  # normal movements that must NOT fire anything
LABELS = GESTURES + (NONE_LABEL,)
SAMPLES_DIR = PROJECT_ROOT / "samples"
REPEATING = ("circle_cw", "circle_ccw")


@dataclass
class Recording:
    label: str
    frame_size: tuple[int, int]
    frames: list[tuple[float, HandFrame | None]] = field(default_factory=list)
    created: str = ""
    note: str = ""


def save(rec: Recording, path: Path) -> None:
    if rec.label not in LABELS:
        raise ValueError(f"unknown label {rec.label!r}; use one of {', '.join(LABELS)}")
    t0 = rec.frames[0][0] if rec.frames else 0.0
    frames = []
    for t, hand in rec.frames:
        entry: dict = {"t": round(t - t0, 4), "hand": None}
        if hand is not None:
            entry["hand"] = {
                "handedness": hand.handedness,
                "score": round(hand.score, 3),
                "landmarks": np.round(hand.landmarks, 2).tolist(),
            }
        frames.append(entry)
    doc = {
        "version": SCHEMA_VERSION,
        "label": rec.label,
        "frame_size": list(rec.frame_size),
        "created": rec.created or datetime.now().isoformat(timespec="seconds"),
        "note": rec.note,
        "frames": frames,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")


def load(path: Path) -> Recording:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("version") != SCHEMA_VERSION:
        raise ValueError(f"{path}: unsupported sample version {doc.get('version')!r}")
    size = tuple(doc["frame_size"])
    frames: list[tuple[float, HandFrame | None]] = []
    for entry in doc["frames"]:
        t = float(entry["t"])
        h = entry["hand"]
        hand = None
        if h is not None:
            lm = np.asarray(h["landmarks"], dtype=float)
            hand = HandFrame(t=t, landmarks=lm, handedness=h["handedness"], score=float(h["score"]), frame_size=size)
        frames.append((t, hand))
    return Recording(label=doc["label"], frame_size=size, frames=frames, created=doc.get("created", ""), note=doc.get("note", ""))


def sample_files(root: Path = SAMPLES_DIR) -> list[Path]:
    return sorted(Path(root).glob("*/*.json"))


def replay(rec: Recording, cfg: AppConfig) -> list[Event]:
    """Run a recording through a fresh engine with ``cfg``'s thresholds. Every gesture is
    enabled during replay, so disabling one in the mapping doesn't break its samples."""
    cfg = dataclasses.replace(cfg, mapping=dict(DEFAULT_MAPPING))
    engine = GestureEngine(cfg)
    events: list[Event] = []
    for t, hand in rec.frames:
        events.extend(engine.update(t, hand))
    return events


def check(label: str, fired: list[str]) -> tuple[bool, str]:
    """Did a recording labelled ``label`` fire what it should?"""
    if label == NONE_LABEL:
        return (not fired, "fired nothing" if not fired else f"should fire nothing, fired {fired}")
    if label in REPEATING:
        ok = bool(fired) and all(g == label for g in fired)
        return ok, f"fired {fired}" if ok else f"expected one or more {label}, fired {fired}"
    ok = fired == [label]
    return ok, f"fired {fired}" if ok else f"expected exactly [{label}], fired {fired}"
