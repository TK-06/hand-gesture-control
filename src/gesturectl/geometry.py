"""Hand geometry: hand scale, palm centre, finger states and static pose.

Everything here is independent of left/right hand and in-plane rotation, so the same
rules work for the driver and the passenger.
"""

from __future__ import annotations

import math
from enum import Enum

import numpy as np

from gesturectl.config import GeometryConfig
from gesturectl.hand import FINGERS, INDEX, MIDDLE, PALM_POINTS, PINKY, THUMB, WRIST


class Pose(str, Enum):
    NONE = "none"  # no usable hand
    OPEN = "open"  # all five fingers extended
    FIST = "fist"  # all four fingers curled, thumb tucked
    THUMB = "thumb"  # all four fingers curled, thumb out (thumbs up / sideways)
    POINT = "point"  # index only
    TWO = "two"  # index + middle (thumb ignored)
    PHONE = "phone"  # thumb + pinky out, the rest curled ("call me")
    OTHER = "other"


class FingerState(Enum):
    EXTENDED = "extended"
    CURLED = "curled"
    UNCERTAIN = "uncertain"


def hand_scale(lm: np.ndarray) -> float:
    """Wrist->middle-MCP length in pixels (palm width as a floor when the palm is
    foreshortened). Does not change when fingers curl."""
    length = np.linalg.norm(lm[MIDDLE[0], :2] - lm[WRIST, :2])
    width = np.linalg.norm(lm[INDEX[0], :2] - lm[PINKY[0], :2])
    return float(max(length, 1.25 * width))


def palm_center(lm: np.ndarray) -> np.ndarray:
    return lm[list(PALM_POINTS), :2].mean(axis=0)


def _finger_metrics(lm: np.ndarray, joints: tuple[int, int, int, int]) -> tuple[float, float]:
    mcp, pip, dip, tip = (lm[j] for j in joints)
    path = np.linalg.norm(pip - mcp) + np.linalg.norm(dip - pip) + np.linalg.norm(tip - dip)
    chord = tip - mcp
    chord_len = np.linalg.norm(chord)
    palm_dir = mcp - lm[WRIST]
    denom = chord_len * np.linalg.norm(palm_dir)
    straightness = float(chord_len / path) if path > 1e-9 else 0.0
    alignment = float(np.dot(chord, palm_dir) / denom) if denom > 1e-9 else 0.0
    return straightness, alignment


def finger_states(lm: np.ndarray, cfg: GeometryConfig) -> dict[str, FingerState]:
    states = {}
    for name, joints in FINGERS.items():
        straightness, alignment = _finger_metrics(lm, joints)
        if straightness >= cfg.extended_straightness and alignment >= cfg.extended_alignment:
            states[name] = FingerState.EXTENDED
        elif straightness <= cfg.curled_straightness or alignment <= cfg.curled_alignment:
            states[name] = FingerState.CURLED
        else:
            states[name] = FingerState.UNCERTAIN
    return states


def thumb_extended(lm: np.ndarray, cfg: GeometryConfig) -> bool:
    """Thumb tip well away from the index knuckle and pointing outward (not folded
    across the palm)."""
    tip, ip = lm[THUMB[3]], lm[THUMB[2]]
    far = np.linalg.norm(tip - lm[INDEX[0]]) / hand_scale(lm) >= cfg.thumb_open_distance
    outward = np.linalg.norm(tip - lm[PINKY[0]]) > np.linalg.norm(ip - lm[PINKY[0]])
    return bool(far and outward)


def index_pointing(lm: np.ndarray, cfg: GeometryConfig, state: FingerState) -> bool:
    """Extended, or straight but bent at the knuckle: pointing toward the camera. A
    fist's index is bent in the middle (low straightness), so it never qualifies."""
    if state is FingerState.EXTENDED:
        return True
    straightness, alignment = _finger_metrics(lm, FINGERS["index"])
    return straightness >= cfg.point_straightness and alignment > cfg.point_min_alignment


def classify_pose(lm: np.ndarray, cfg: GeometryConfig) -> Pose:
    states = finger_states(lm, cfg)
    extended = {n for n, s in states.items() if s is FingerState.EXTENDED}
    curled = {n for n, s in states.items() if s is FingerState.CURLED}
    others_curled = {"middle", "ring", "pinky"} <= curled
    if others_curled and index_pointing(lm, cfg, states["index"]):
        return Pose.POINT
    if len(curled) == 4:
        return Pose.THUMB if thumb_extended(lm, cfg) else Pose.FIST
    if extended == {"index"} and curled == {"middle", "ring", "pinky"}:
        return Pose.POINT
    if extended == {"index", "middle"} and curled == {"ring", "pinky"}:
        return Pose.TWO
    if extended == {"pinky"} and curled == {"index", "middle", "ring"} and thumb_extended(lm, cfg):
        return Pose.PHONE
    if len(extended) == 4 and thumb_extended(lm, cfg):
        return Pose.OPEN
    return Pose.OTHER


def _screen_angle(vec: np.ndarray) -> float:
    """Angle of an image-space vector in degrees: 0 = right, 90 = up, 180 = left,
    -90 = down (image y points down, so it is negated)."""
    return math.degrees(math.atan2(-float(vec[1]), float(vec[0])))


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def thumb_direction(lm: np.ndarray, tolerance_deg: float) -> str | None:
    """Where the thumb points, as the user sees it: "up", "right", "left" or "down".
    None when it is diagonal (more than ``tolerance_deg`` from all four)."""
    angle = _screen_angle(lm[THUMB[3], :2] - lm[THUMB[1], :2])  # thumb MCP -> tip
    for name, target in (("right", 0.0), ("up", 90.0), ("left", 180.0), ("down", -90.0)):
        if _angle_diff(angle, target) <= tolerance_deg:
            return name
    return None


def phone_orientation(lm: np.ndarray, tolerance_deg: float) -> str | None:
    """The "phone" hand's thumb-pinky axis: "vertical" (held like a phone at your ear)
    or "horizontal". Which end points where doesn't matter, so it works with either
    hand. None in between."""
    angle = _screen_angle(lm[THUMB[3], :2] - lm[PINKY[3], :2]) % 180.0  # 0..180, direction-free
    if min(angle, 180.0 - angle) <= tolerance_deg:
        return "horizontal"
    if abs(angle - 90.0) <= tolerance_deg:
        return "vertical"
    return None
