"""Synthetic hands and hand trajectories for tests.

The canonical hand is a right hand, palm facing the camera, fingers pointing up, in
"hand units" where WRIST -> MIDDLE_MCP = 1.0. Axes match the tracker output: x right,
y down, z toward the camera is negative. Fingers flex toward the camera (palm side).
"""

from __future__ import annotations

import math
from typing import Callable, Iterable

import numpy as np

from gesturectl.config import AppConfig
from gesturectl.hand import FINGERS, PALM_POINTS, HandFrame

FRAME_SIZE = (320, 240)

_MCP = {"index": (-0.28, -0.92), "middle": (0.0, -1.0), "ring": (0.24, -0.95), "pinky": (0.44, -0.85)}
_LENGTHS = {
    "index": (0.38, 0.22, 0.20),
    "middle": (0.42, 0.26, 0.21),
    "ring": (0.38, 0.25, 0.20),
    "pinky": (0.30, 0.18, 0.18),
}
_FAN_DEG = {"index": -8.0, "middle": 0.0, "ring": 6.0, "pinky": 14.0}
# Flexion (degrees) at MCP, PIP, DIP.
_FLEX = {"extended": (0.0, 5.0, 5.0), "curled": (85.0, 100.0, 60.0), "half": (40.0, 50.0, 30.0)}
_THUMB = {
    "extended": [(-0.25, -0.15, 0.0), (-0.45, -0.30, 0.0), (-0.62, -0.46, 0.0), (-0.78, -0.62, 0.0)],
    "tucked": [(-0.25, -0.15, 0.0), (-0.36, -0.36, -0.10), (-0.26, -0.58, -0.18), (-0.12, -0.75, -0.20)],
    "half": [(-0.25, -0.15, 0.0), (-0.42, -0.33, -0.05), (-0.48, -0.52, -0.12), (-0.45, -0.68, -0.15)],
}
_E, _C, _H = "extended", "curled", "half"
POSES = {
    "open": ({"index": _E, "middle": _E, "ring": _E, "pinky": _E}, "extended"),
    "fist": ({"index": _C, "middle": _C, "ring": _C, "pinky": _C}, "tucked"),
    "point": ({"index": _E, "middle": _C, "ring": _C, "pinky": _C}, "tucked"),
    "two": ({"index": _E, "middle": _E, "ring": _C, "pinky": _C}, "tucked"),
    "three": ({"index": _E, "middle": _E, "ring": _E, "pinky": _C}, "tucked"),
    "half": ({"index": _H, "middle": _H, "ring": _H, "pinky": _H}, "half"),
    "open_thumb_in": ({"index": _E, "middle": _E, "ring": _E, "pinky": _E}, "tucked"),
    # "finger gun": index + middle held together, thumb sticking out
    "gun": ({"index": _E, "middle": _E, "ring": _C, "pinky": _C}, "extended"),
}


def _finger_chain(name: str, flex: str) -> list[np.ndarray]:
    fan = math.radians(_FAN_DEG[name])
    d0 = np.array([math.sin(fan), -math.cos(fan), 0.0])
    toward_camera = np.array([0.0, 0.0, -1.0])
    pts = [np.array([*_MCP[name], 0.0])]
    phi = 0.0
    for seg_len, bend in zip(_LENGTHS[name], _FLEX[flex]):
        phi += math.radians(bend)
        pts.append(pts[-1] + seg_len * (math.cos(phi) * d0 + math.sin(phi) * toward_camera))
    return pts


def make_hand(
    pose: str = "open",
    *,
    center: tuple[float, float] = (160.0, 120.0),
    scale: float = 60.0,
    angle_deg: float = 0.0,
    mirror: bool = False,
) -> np.ndarray:
    """21x3 landmarks in pixel units. ``mirror`` makes a left hand; ``angle_deg`` rotates
    clockwise on screen; ``scale`` is WRIST->MIDDLE_MCP in pixels; the palm centre lands
    on ``center``."""
    fingers, thumb = POSES[pose]
    lm = np.zeros((21, 3))
    lm[1:5] = _THUMB[thumb]
    for name, joints in FINGERS.items():
        lm[list(joints)] = _finger_chain(name, fingers[name])
    if mirror:
        lm[:, 0] *= -1.0
    a = math.radians(angle_deg)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    lm[:, :2] = lm[:, :2] @ rot.T
    lm *= scale
    lm[:, :2] += np.asarray(center, dtype=float) - lm[list(PALM_POINTS), :2].mean(axis=0)
    return lm


# ---------------------------------------------------------------- trajectories

Frames = list[tuple[float, "HandFrame | None"]]
PoseAt = Callable[[float], "str | None"]
PosAt = Callable[[float], tuple[float, float]]


def phases(*spec: tuple[float, str | None]) -> PoseAt:
    """``phases((1.0, "open"), (2.0, "fist"))`` = open until t=1.0, then fist until 2.0.
    After the last phase the last pose holds. ``None`` = no hand."""

    def pose_at(t: float) -> str | None:
        for end, pose in spec:
            if t < end:
                return pose
        return spec[-1][1]

    return pose_at


def still(x: float = 160.0, y: float = 120.0) -> PosAt:
    return lambda t: (x, y)


def circle_path(
    center: tuple[float, float] = (160.0, 120.0),
    radius: float = 30.0,
    period: float = 1.0,
    *,
    clockwise: bool = True,
    t_start: float = 0.0,
) -> PosAt:
    """Hold at the start point until ``t_start``, then circle. Clockwise is as seen on
    screen (image y points down, so increasing atan2 angle is clockwise)."""
    sign = 1.0 if clockwise else -1.0

    def pos(t: float) -> tuple[float, float]:
        a = sign * 2 * math.pi * max(0.0, t - t_start) / period
        return (center[0] + radius * math.cos(a), center[1] + radius * math.sin(a))

    return pos


def line_path(start: tuple[float, float], end: tuple[float, float], t_start: float, t_end: float) -> PosAt:
    """Hold at ``start`` until ``t_start``, move linearly, then hold at ``end``."""

    def pos(t: float) -> tuple[float, float]:
        if t <= t_start:
            return start
        if t >= t_end:
            return end
        f = (t - t_start) / (t_end - t_start)
        return (start[0] + f * (end[0] - start[0]), start[1] + f * (end[1] - start[1]))

    return pos


def track(
    duration: float,
    pose_at: PoseAt | str,
    pos_at: PosAt | None = None,
    *,
    fps: float = 30.0,
    scale: float = 60.0,
    angle_deg: float = 0.0,
    mirror: bool = False,
    noise_px: float = 0.0,
    drop: Callable[[float], bool] | None = None,
    seed: int = 0,
    t0: float = 100.0,
) -> Frames:
    """Sample a hand trajectory into timestamped frames (t starts at ``t0``)."""
    if isinstance(pose_at, str):
        pose_at = phases((math.inf, pose_at))
    pos_at = pos_at or still()
    rng = np.random.default_rng(seed)
    frames: Frames = []
    for i in range(int(round(duration * fps))):
        rel = i / fps
        t = t0 + rel
        pose = pose_at(rel)
        if pose is None or (drop is not None and drop(rel)):
            frames.append((t, None))
            continue
        lm = make_hand(pose, center=pos_at(rel), scale=scale, angle_deg=angle_deg, mirror=mirror)
        if noise_px:
            lm = lm + rng.normal(0.0, noise_px, lm.shape)
        frames.append((t, HandFrame(t, lm, "Left" if mirror else "Right", 0.95, FRAME_SIZE)))
    return frames


def run(frames: Iterable[tuple[float, HandFrame | None]], cfg: AppConfig | None = None) -> list[str]:
    """Feed frames through a fresh engine; return the fired gesture names in order."""
    from gesturectl.engine import GestureEngine

    engine = GestureEngine(cfg or AppConfig())
    fired: list[str] = []
    for t, hand in frames:
        fired.extend(e.gesture for e in engine.update(t, hand))
    return fired
