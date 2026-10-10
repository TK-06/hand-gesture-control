"""Scoring what the engine fired against what was actually performed on video.

A performed gesture is counted once: a continuous circle that steps the volume several
times is one circle (steps less than BURST_GAP_S apart are merged).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from gesturectl.engine import Event
from gesturectl.recording import BURST_GAP_S, REPEATING

Detection = tuple[float, str]  # (seconds, gesture)


@dataclass
class Score:
    expected: Counter = field(default_factory=Counter)  # gesture -> times performed
    hit: Counter = field(default_factory=Counter)  # gesture -> times detected
    missed: list[tuple[float | None, str]] = field(default_factory=list)  # (time if known, gesture)
    false: list[Detection] = field(default_factory=list)  # fired but not performed
    negative_s: float = 0.0  # seconds of footage in which nothing should fire

    def add(self, other: "Score") -> None:
        self.expected.update(other.expected)
        self.hit.update(other.hit)
        self.missed += other.missed
        self.false += other.false
        self.negative_s += other.negative_s


def collapse(events: list[Event], gap_s: float = BURST_GAP_S) -> list[Detection]:
    """One detection per performed gesture (merges the steps of one continuous circle)."""
    out: list[Detection] = []
    last_step: dict[str, float] = {}
    for e in sorted(events, key=lambda e: e.t):
        if e.gesture in REPEATING:
            prev = last_step.get(e.gesture)
            last_step[e.gesture] = e.t
            if prev is not None and e.t - prev <= gap_s:
                continue
        out.append((e.t, e.gesture))
    return out


def score_gesture_clip(label: str, reps: int, events: list[Event]) -> Score:
    """A clip of one gesture performed ``reps`` times."""
    detections = collapse(events)
    own = [d for d in detections if d[1] == label]
    hits = min(len(own), reps)
    score = Score()
    score.expected[label] = reps
    score.hit[label] = hits
    score.missed = [(None, label)] * (reps - hits)
    score.false = [d for d in detections if d[1] != label] + own[reps:]
    return score


def score_negative(events: list[Event], duration_s: float) -> Score:
    """Footage in which nothing should fire."""
    return Score(false=collapse(events), negative_s=duration_s)


def score_mixed(expected: list[Detection], events: list[Event], tolerance_s: float = 2.5) -> Score:
    """Normal movements with gestures at known (approximate) times. Each performed
    gesture matches the nearest unused detection of the same gesture within
    ``tolerance_s``; detections left over are false triggers."""
    detections = collapse(events)
    used = [False] * len(detections)
    score = Score()
    for t_exp, gesture in sorted(expected):
        score.expected[gesture] += 1
        best = None
        for i, (t, g) in enumerate(detections):
            if used[i] or g != gesture or abs(t - t_exp) > tolerance_s:
                continue
            if best is None or abs(t - t_exp) < abs(detections[best][0] - t_exp):
                best = i
        if best is None:
            score.missed.append((t_exp, gesture))
        else:
            used[best] = True
            score.hit[gesture] += 1
    score.false = [d for i, d in enumerate(detections) if not used[i]]
    return score


def fmt_time(t: float | None) -> str:
    if t is None:
        return "?"
    minutes, seconds = divmod(t, 60.0)
    return f"{int(minutes)}:{seconds:04.1f}"
