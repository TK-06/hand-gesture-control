"""Shared types for gesture recognizers."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from gesturectl.geometry import Pose
from gesturectl.hand import HandFrame


@dataclass(frozen=True)
class Observation:
    """What a recognizer sees each frame.

    ``hand`` is None when there is no fresh usable hand this frame; ``pose`` may still be
    a real pose during the dropout grace period, so recognizers keep their state but
    must not update positions."""

    t: float
    hand: HandFrame | None
    pose: Pose  # debounced pose
    pose_since: float  # when the debounced pose began
    scale: float  # hand scale in pixels (0 when hand is None)
    palm: np.ndarray | None  # palm centre (x, y) in pixels


class Recognizer(ABC):
    @abstractmethod
    def update(self, obs: Observation) -> list[str]:
        """Advance by one frame; return the gesture names that fired (usually none)."""

    @abstractmethod
    def reset(self) -> None: ...

    def status(self) -> str:
        """Short human-readable state for the debug overlay."""
        return ""


class StillHold:
    """How long the current pose has been held with the palm roughly still. Moving the
    palm more than ``max_drift`` hand scales restarts the clock."""

    def __init__(self, max_drift: float):
        self.max_drift = max_drift
        self.reset()

    def reset(self) -> None:
        self._pose: Pose | None = None
        self._start = math.inf
        self._anchor: np.ndarray | None = None

    def update(self, obs: Observation) -> float:
        if obs.pose is not self._pose:
            self._pose = obs.pose
            self._start = obs.pose_since
            self._anchor = obs.palm
        elif obs.palm is not None:
            if self._anchor is None:
                self._anchor = obs.palm
            elif np.linalg.norm(obs.palm - self._anchor) > self.max_drift * obs.scale:
                self._anchor = obs.palm
                self._start = obs.t
        return max(0.0, obs.t - self._start)
