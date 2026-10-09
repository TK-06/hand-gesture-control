"""Hand open <-> closed transitions: ``fist_to_open`` and ``open_to_fist``.

1. Arm: hold the start pose (FIST or OPEN) still for ``arm_hold_s``. Moving the hand
   while armed disarms it, so a hand reaching for something never arms.
2. Transition: the opposite pose must appear within ``transition_max_s`` while the palm
   stays within ``transition_max_move`` hand scales of where it was held.
3. Fire once the target pose has been held ``target_hold_s``, then latch: nothing fires
   again until the hand leaves or shows a pose other than OPEN/FIST. A pause can never
   chain straight into a play.
"""

from __future__ import annotations

import numpy as np

from gesturectl.config import GrabConfig
from gesturectl.geometry import Pose
from gesturectl.gestures.base import Observation, Recognizer, StillHold

TARGETS = {Pose.FIST: (Pose.OPEN, "fist_to_open"), Pose.OPEN: (Pose.FIST, "open_to_fist")}

IDLE, ARMED, TRANSITION, LATCHED = "idle", "armed", "transition", "latched"


class GrabRecognizer(Recognizer):
    def __init__(self, cfg: GrabConfig):
        self.cfg = cfg
        self._hold = StillHold(cfg.arm_max_drift)
        self.reset()

    def reset(self) -> None:
        self._state = IDLE
        self._hold.reset()
        self._start_pose: Pose | None = None
        self._anchor: np.ndarray | None = None
        self._t_leave = 0.0

    def update(self, obs: Observation) -> list[str]:
        cfg = self.cfg
        held = self._hold.update(obs)

        if self._state == LATCHED:
            if obs.pose not in TARGETS:
                self._state = IDLE
            return []

        if self._state == ARMED:
            if obs.pose is self._start_pose:
                if held < cfg.arm_hold_s:
                    self._state = IDLE  # hand moved: disarm
                elif obs.palm is not None:
                    self._anchor = obs.palm
                return []
            self._state = TRANSITION
            self._t_leave = obs.pose_since

        if self._state == TRANSITION:
            target, name = TARGETS[self._start_pose]
            moved = (
                obs.palm is not None
                and self._anchor is not None
                and np.linalg.norm(obs.palm - self._anchor) > cfg.transition_max_move * obs.scale
            )
            reached_at = obs.pose_since if obs.pose is target else obs.t
            late = reached_at - self._t_leave > cfg.transition_max_s
            if moved or late or obs.pose not in (target, Pose.OTHER):
                self._state = IDLE  # fall through: the current pose may arm
            elif obs.pose is target:
                if obs.t - obs.pose_since >= cfg.target_hold_s:
                    self._state = LATCHED
                    return [name]
                return []
            else:
                return []  # passing through an in-between pose

        if obs.pose in TARGETS and held >= cfg.arm_hold_s and obs.palm is not None:
            self._state = ARMED
            self._start_pose = obs.pose
            self._anchor = obs.palm
        return []

    def status(self) -> str:
        if self._state in (ARMED, TRANSITION):
            return f"grab: {self._state} from {self._start_pose.value}"
        return f"grab: {self._state}"
