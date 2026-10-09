"""Capture -> track -> recognize, one frame per ``step()``. Shared by the main program
and the sample recorder."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from gesturectl.camera import open_camera, prepare
from gesturectl.config import AppConfig
from gesturectl.engine import Event, GestureEngine
from gesturectl.hand import HandFrame
from gesturectl.tracker import HandTracker, largest


@dataclass
class FrameResult:
    t: float
    frame: np.ndarray  # oriented, processing-size BGR frame
    hand: HandFrame | None
    events: list[Event]
    infer_ms: float


class RateMeter:
    """Exponential moving average of a rate (per second) and of a duration (ms)."""

    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha
        self.fps = 0.0
        self.ms = 0.0
        self._last_t: float | None = None

    def tick(self, t: float, ms: float) -> None:
        if self._last_t is not None and t > self._last_t:
            inst = 1.0 / (t - self._last_t)
            self.fps = inst if self.fps == 0.0 else self.fps + self.alpha * (inst - self.fps)
        self.ms = ms if self.ms == 0.0 else self.ms + self.alpha * (ms - self.ms)
        self._last_t = t


class Pipeline:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.camera = open_camera(cfg.camera)
        try:
            self.tracker = HandTracker(cfg.tracker, cfg.model_path())
        except Exception:
            self.camera.close()
            raise
        self.engine = GestureEngine(cfg)
        self.meter = RateMeter()

    def step(self) -> FrameResult | None:
        """Process one camera frame. Returns None if the camera gave no frame."""
        raw = self.camera.read()
        if raw is None:
            return None
        frame = prepare(raw, self.cfg.camera)
        t = time.monotonic()
        t0 = time.perf_counter()
        hand = largest(self.tracker.process(frame, t))
        infer_ms = (time.perf_counter() - t0) * 1000.0
        events = self.engine.update(t, hand)
        self.meter.tick(t, infer_ms)
        return FrameResult(t=t, frame=frame, hand=hand, events=events, infer_ms=infer_ms)

    def close(self) -> None:
        self.tracker.close()
        self.camera.close()
