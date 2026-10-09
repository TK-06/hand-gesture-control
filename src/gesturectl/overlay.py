"""Debug overlay for development (never used in the car: the Pi runs headless)."""

from __future__ import annotations

import cv2
import numpy as np

from gesturectl.engine import GestureEngine
from gesturectl.hand import CONNECTIONS, HandFrame

_WHITE = (255, 255, 255)
_GREEN = (80, 220, 80)
_YELLOW = (0, 220, 255)
_RED = (60, 60, 230)
_GREY = (160, 160, 160)


def _text(img: np.ndarray, text: str, org: tuple[int, int], color=_WHITE, size: float = 0.5) -> None:
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, size, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, size, color, 1, cv2.LINE_AA)


def draw(
    frame: np.ndarray,
    *,
    hand: HandFrame | None,
    engine: GestureEngine,
    t: float,
    fps: float,
    infer_ms: float,
    banner: str = "",
    scale: float = 2.0,
    recording: bool = False,
) -> np.ndarray:
    img = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR) if scale != 1 else frame.copy()
    h, w = img.shape[:2]

    x0, y0, x1, y1 = engine.cfg.gating.active_zone
    if (x0, y0, x1, y1) != (0.0, 0.0, 1.0, 1.0):
        cv2.rectangle(img, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), _YELLOW, 1)

    if hand is not None:
        pts = (hand.landmarks[:, :2] * scale).astype(int)
        color = _GREEN if engine.gate_reason == "ok" else _GREY
        for a, b in CONNECTIONS:
            cv2.line(img, tuple(pts[a]), tuple(pts[b]), color, 2, cv2.LINE_AA)
        for p in pts:
            cv2.circle(img, tuple(p), 3, _WHITE, -1, cv2.LINE_AA)

    obs = engine.last_obs
    stable = obs.pose.value if obs else "none"
    lines = [
        (f"FPS {fps:4.1f}   inference {infer_ms:5.1f} ms", _WHITE),
        (f"pose {stable} (raw {engine.raw_pose.value})   {engine.gate_reason}", _WHITE),
    ]
    cooldown = engine.cooldown_remaining(t)
    if cooldown > 0:
        lines.append((f"cooldown {cooldown:.1f}s", _YELLOW))
    lines += [(s, _GREY) for s in engine.status_lines()]
    for i, (line, color) in enumerate(lines):
        _text(img, line, (8, 20 + 20 * i), color)

    if banner:
        _text(img, banner, (8, h - 16), _GREEN, 0.8)
    if recording:
        cv2.circle(img, (w - 20, 20), 8, _RED, -1)
        _text(img, "REC", (w - 62, 26), _RED)
    return img
