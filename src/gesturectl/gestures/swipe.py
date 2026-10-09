"""Two-finger (index + middle) swipes: up / down / left / right.

1. Arm: hold the TWO pose still for ``arm_hold_s``.
2. Moving more than ``start_distance`` hand scales from the armed spot starts the clock.
3. Fire when the palm has travelled ``min_distance`` hand scales within
   ``max_duration_s`` and one axis dominates by ``axis_ratio``.
4. Latch until the TWO pose is released, so the return stroke never fires the opposite
   direction.
"""

from __future__ import annotations

import numpy as np

from gesturectl.config import SwipeConfig
from gesturectl.geometry import Pose
from gesturectl.gestures.base import Observation, Recognizer, StillHold

IDLE, ARMED, MOVING, LATCHED = "idle", "armed", "moving", "latched"


class SwipeRecognizer(Recognizer):
    def __init__(self, cfg: SwipeConfig):
        self.cfg = cfg
        self._hold = StillHold(cfg.arm_max_drift)
        self.reset()

    def reset(self) -> None:
        self._state = IDLE
        self._hold.reset()
        self._anchor: np.ndarray | None = None
        self._scale = 0.0
        self._t_near = 0.0
        self._t_start = 0.0

    def update(self, obs: Observation) -> list[str]:
        cfg = self.cfg
        held = self._hold.update(obs)
        if obs.pose is not Pose.TWO:
            self._state = IDLE
            return []
        if self._state == LATCHED or obs.palm is None:
            return []

        if self._state == IDLE:
            if held >= cfg.arm_hold_s:
                self._state = ARMED
                self._anchor = obs.palm
                self._scale = obs.scale
                self._t_near = obs.t
            return []

        disp = obs.palm - self._anchor
        dist = float(np.linalg.norm(disp))

        if self._state == ARMED:
            if dist < cfg.start_distance * self._scale:
                self._t_near = obs.t
                return []
            self._state = MOVING
            self._t_start = self._t_near

        if obs.t - self._t_start > cfg.max_duration_s:
            self._state = IDLE  # too slow: a drift, not a swipe
            return []
        if dist < cfg.min_distance * self._scale:
            return []

        ax, ay = abs(float(disp[0])), abs(float(disp[1]))
        if max(ax, ay) < cfg.axis_ratio * min(ax, ay):
            self._state = IDLE  # diagonal
            return []
        self._state = LATCHED
        if ax > ay:
            return ["swipe_right" if disp[0] > 0 else "swipe_left"]
        return ["swipe_down" if disp[1] > 0 else "swipe_up"]

    def status(self) -> str:
        return f"swipe: {self._state}"
