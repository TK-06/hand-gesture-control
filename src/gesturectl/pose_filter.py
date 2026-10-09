"""Debounces per-frame poses into a stable pose plus the time it began."""

from __future__ import annotations

import math

from gesturectl.geometry import Pose

_EPS = 1e-6


class PoseFilter:
    """A new pose must persist ``switch_s`` before it replaces the current one; losing
    the hand (Pose.NONE) is tolerated for ``grace_s``. If the raw pose keeps changing
    (noise), the old pose still expires ``grace_s + switch_s`` after it was last seen."""

    def __init__(self, switch_s: float, grace_s: float):
        self.switch_s = switch_s
        self.grace_s = grace_s
        self.reset()

    def reset(self) -> None:
        self.pose = Pose.NONE
        self.since = -math.inf
        self._last_match = -math.inf
        self._candidate: Pose | None = None
        self._candidate_since = 0.0

    def update(self, t: float, raw: Pose) -> tuple[Pose, float]:
        if raw is self.pose:
            self._last_match = t
            self._candidate = None
            return self.pose, self.since

        if raw is not self._candidate:
            self._candidate = raw
            self._candidate_since = t

        needed = self.grace_s if raw is Pose.NONE else self.switch_s
        if t - self._candidate_since >= needed - _EPS:
            self._switch(raw, self._candidate_since, t)
        elif self.pose is not Pose.NONE and t - self._last_match >= self.grace_s + self.switch_s - _EPS:
            self._switch(raw, t, t)  # expire a stale pose even if the raw pose keeps flickering
        return self.pose, self.since

    def _switch(self, pose: Pose, since: float, t: float) -> None:
        self.pose = pose
        self.since = since
        self._last_match = t
        self._candidate = None
