"""Static poses held still: five fingers up (``open_palm``), a thumb pointing
up/right/left/down (``thumb_<dir>``), and the "phone" hand, thumb + pinky out, held
vertical or horizontal (``phone_vertical`` / ``phone_horizontal``).

A pose fires once it has been held for ``hold_s`` with the palm roughly still; moving
the hand restarts the hold, so a hand passing through a pose never fires. It then
latches: the same gesture can't fire again until something else (another pose, or no
hand) has been shown for ``release_s``. Directions are as the user sees them, and
nothing depends on which hand is used.
"""

from __future__ import annotations

import numpy as np

from gesturectl.config import StaticConfig
from gesturectl.geometry import Pose, phone_orientation, thumb_direction
from gesturectl.gestures.base import Observation, Recognizer

_EPS = 1e-6


def static_gesture(pose: Pose, lm: np.ndarray, cfg: StaticConfig) -> str | None:
    """The static gesture a (debounced) pose plus the current landmarks show, if any."""
    if pose is Pose.OPEN:
        return "open_palm"
    if pose is Pose.THUMB:
        direction = thumb_direction(lm, cfg.thumb_tolerance_deg)
        return f"thumb_{direction}" if direction else None
    if pose is Pose.PHONE:
        orientation = phone_orientation(lm, cfg.phone_tolerance_deg)
        return f"phone_{orientation}" if orientation else None
    return None


class StaticPoseRecognizer(Recognizer):
    def __init__(self, cfg: StaticConfig):
        self.cfg = cfg
        self.reset()

    def reset(self) -> None:
        self._candidate: str | None = None
        self._since = 0.0
        self._anchor: np.ndarray | None = None
        self._latched: str | None = None
        self._other_since: float | None = None

    def update(self, obs: Observation) -> list[str]:
        cfg = self.cfg
        if obs.hand is None:
            if obs.pose is not Pose.NONE:
                return []  # short dropout: keep the hold going
            name = None
        else:
            name = static_gesture(obs.pose, obs.hand.landmarks, cfg)
        t = obs.t

        # Hold timer: restarts when the gesture changes or the hand moves.
        if name != self._candidate:
            self._candidate, self._since, self._anchor = name, t, obs.palm
        elif (
            obs.palm is not None
            and self._anchor is not None
            and np.linalg.norm(obs.palm - self._anchor) > cfg.max_drift * obs.scale
        ):
            self._since, self._anchor = t, obs.palm

        # Latch: released once something else has been shown for release_s.
        if self._latched is not None:
            if name == self._latched:
                self._other_since = None
            else:
                if self._other_since is None:
                    self._other_since = t
                if t - self._other_since >= cfg.release_s - _EPS:
                    self._latched, self._other_since = None, None

        if name is not None and name != self._latched and t - self._since >= cfg.hold_s - _EPS:
            self._latched, self._other_since = name, None
            return [name]
        return []

    def status(self) -> str:
        if self._candidate is None:
            return "static: -"
        latched = " (fired)" if self._candidate == self._latched else ""
        return f"static: {self._candidate}{latched}"
