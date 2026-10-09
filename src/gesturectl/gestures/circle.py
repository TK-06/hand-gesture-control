"""Index-finger circles: clockwise / counter-clockwise, stepping while you keep circling.

The fingertip path is resampled at a minimum step (drops jitter), then the signed turning
angle between consecutive segments is summed. This needs no circle centre, and zigzags
cancel out. With image y pointing down, a positive turn is clockwise on screen.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np

from gesturectl.config import CircleConfig
from gesturectl.geometry import Pose
from gesturectl.gestures.base import Observation, Recognizer
from gesturectl.hand import INDEX

CW, CCW = "circle_cw", "circle_ccw"


class CircleRecognizer(Recognizer):
    def __init__(self, cfg: CircleConfig):
        self.cfg = cfg
        self.reset()

    def reset(self) -> None:
        self._last: np.ndarray | None = None  # last kept fingertip point
        self._prev_seg: np.ndarray | None = None
        self._points: deque[np.ndarray] = deque(maxlen=64)
        self._last_move_t = 0.0
        self._restart(0.0)

    def _restart(self, t: float) -> None:
        """Zero the rotation count but keep following the fingertip."""
        self._accum = 0.0  # signed degrees since restart
        self._max = 0.0
        self._min = 0.0
        self._fired = 0
        self._start_t = t
        self._points.clear()
        if self._last is not None:
            self._points.append(self._last)

    def update(self, obs: Observation) -> list[str]:
        cfg = self.cfg
        if obs.pose is not Pose.POINT:
            if self._last is not None:
                self.reset()
            return []
        if obs.hand is None:
            return []  # dropout grace: hold state

        p = obs.hand.landmarks[INDEX[3], :2].astype(float)
        if self._last is None:
            self._last = p
            self._last_move_t = obs.t
            self._restart(obs.t)
            return []

        seg = p - self._last
        if np.linalg.norm(seg) < cfg.min_step * obs.scale:
            if obs.t - self._last_move_t > cfg.idle_reset_s:
                self._prev_seg = None
                self._last_move_t = obs.t
                self._restart(obs.t)
            return []

        self._last = p
        self._last_move_t = obs.t
        self._points.append(p)
        prev, self._prev_seg = self._prev_seg, seg
        if prev is None:
            return []

        cross = prev[0] * seg[1] - prev[1] * seg[0]
        turn = math.degrees(math.atan2(cross, float(np.dot(prev, seg))))
        if abs(turn) > cfg.max_turn_deg:
            return []  # a reversal or a glitch, not part of a circle

        self._accum += turn
        self._max = max(self._max, self._accum)
        self._min = min(self._min, self._accum)
        drop = self._max - self._accum if self._max >= -self._min else self._accum - self._min
        if drop > cfg.reverse_reset_deg:
            self._restart(obs.t)
            return []

        magnitude = abs(self._accum)
        due = 0 if magnitude < cfg.first_step_deg else 1 + int((magnitude - cfg.first_step_deg) // cfg.step_deg)
        if due > self._fired:
            if not self._big_enough(obs.scale):
                self._restart(obs.t)
                return []
            fired = [CW if self._accum > 0 else CCW] * (due - self._fired)
            self._fired = due
            return fired

        if self._fired == 0 and obs.t - self._start_t > cfg.first_step_max_s:
            self._restart(obs.t)
        return []

    def _big_enough(self, scale: float) -> bool:
        pts = np.array(self._points)
        extent = float(np.max(np.ptp(pts, axis=0))) if len(pts) >= 2 else 0.0
        return extent >= self.cfg.min_diameter * scale

    def status(self) -> str:
        if self._last is None:
            return "circle: idle"
        return f"circle: {self._accum:+.0f} deg, steps {self._fired}"
