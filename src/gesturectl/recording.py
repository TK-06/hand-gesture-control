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

from gesturectl.config import GESTURES, PROJECT_ROOT, AppConfig
from gesturectl.engine import Event, GestureEngine
from gesturectl.hand import HandFrame

SCHEMA_VERSION = 1
NONE_LABEL = "none"  # normal movements that must NOT fire anything
LABELS = GESTURES + (NONE_LABEL,)
SAMPLES_DIR = PROJECT_ROOT / "samples"
REPEATING = ("circle_cw", "circle_ccw")
BURST_GAP_S = 1.5  # circle steps closer together than this belong to one repetition


@dataclass
class Recording:
    label: str
    frame_size: tuple[int, int]
    frames: list[tuple[float, HandFrame | None]] = field(default_factory=list)
    created: str = ""
    note: str = ""
    reps: int = 1  # how many times the gesture was performed in this recording


def save(rec: Recording, path: Path, *, check_label: bool = True) -> None:
    if check_label and rec.label not in LABELS:
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
        "reps": rec.reps,
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
    return Recording(
        label=doc["label"],
        frame_size=size,
        frames=frames,
        created=doc.get("created", ""),
        note=doc.get("note", ""),
        reps=int(doc.get("reps", 1)),
    )


def sample_files(root: Path = SAMPLES_DIR) -> list[Path]:
    return sorted(Path(root).glob("*/*.json"))


def replay(rec: Recording, cfg: AppConfig) -> list[Event]:
    """Run a recording through a fresh engine with ``cfg``'s thresholds and live mapping,
    so what fires is what would fire for real. The recording's own gesture is always
    enabled, so its samples keep testing it even if it's switched off in the mapping."""
    mapping = dict(cfg.mapping)
    if rec.label in GESTURES and not mapping.get(rec.label):
        mapping[rec.label] = "(replay)"
    engine = GestureEngine(dataclasses.replace(cfg, mapping=mapping))
    events: list[Event] = []
    for t, hand in rec.frames:
        events.extend(engine.update(t, hand))
    return events


def count_reps(events: list[Event], gesture: str, gap_s: float = BURST_GAP_S) -> int:
    """How many times ``gesture`` was performed. One continuous circle can step the
    volume several times, so circle steps less than ``gap_s`` apart count once."""
    times = [e.t for e in events if e.gesture == gesture]
    if gesture not in REPEATING:
        return len(times)
    count, last = 0, None
    for t in times:
        if last is None or t - last > gap_s:
            count += 1
        last = t
    return count


def check(label: str, events: list[Event], reps: int = 1) -> tuple[bool, str]:
    """Did a recording labelled ``label`` (performed ``reps`` times) fire what it should?"""
    fired = [e.gesture for e in events]
    if label == NONE_LABEL:
        return (not fired, "fired nothing" if not fired else f"should fire nothing, fired {fired}")
    others = [g for g in fired if g != label]
    got = count_reps(events, label)
    ok = not others and got == reps
    detail = f"{got}/{reps} {label}" + (f", wrong gestures {others}" if others else "")
    return ok, detail
