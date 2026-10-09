"""Hand data passed between the tracker, the gesture engine, recordings and tests.

Landmarks follow the MediaPipe 21-point hand model. Coordinates are in pixels of the
processed frame (x right, y down). z is MediaPipe's relative depth scaled by the frame
width, so it shares units with x (smaller z = closer to the camera).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

WRIST = 0
THUMB = (1, 2, 3, 4)  # CMC, MCP, IP, TIP
INDEX = (5, 6, 7, 8)  # MCP, PIP, DIP, TIP
MIDDLE = (9, 10, 11, 12)
RING = (13, 14, 15, 16)
PINKY = (17, 18, 19, 20)
FINGERS = {"index": INDEX, "middle": MIDDLE, "ring": RING, "pinky": PINKY}
PALM_POINTS = (0, 5, 9, 13, 17)

CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


@dataclass(frozen=True)
class HandFrame:
    """One detected hand in one frame."""

    t: float  # seconds, monotonic clock
    landmarks: np.ndarray  # (21, 3) float, pixel units (see module docstring)
    handedness: str  # "Left" / "Right" as reported by MediaPipe; informational only
    score: float  # handedness confidence
    frame_size: tuple[int, int]  # (width, height) of the processed frame
