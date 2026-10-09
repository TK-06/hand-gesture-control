"""Camera sources. Frames come out BGR, oriented (flip/rotate) and fitted to the
processing size from the config (``camera.width`` x ``camera.height`` after rotation)."""

from __future__ import annotations

import sys
from typing import Protocol

import cv2
import numpy as np

from gesturectl.config import CameraConfig

_BACKENDS = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "v4l2": cv2.CAP_V4L2, "any": cv2.CAP_ANY}
_ROTATIONS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


class Camera(Protocol):
    def read(self) -> np.ndarray | None: ...

    def close(self) -> None: ...

    def describe(self) -> str: ...


class OpenCVCamera:
    """USB / built-in webcams through OpenCV."""

    def __init__(self, cfg: CameraConfig):
        if cfg.backend == "auto":
            api = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        else:
            api = _BACKENDS[cfg.backend]
        self._cap = cv2.VideoCapture(cfg.index, api)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open camera index {cfg.index} (backend {cfg.backend})")
        # Ask for the processing size directly (pre-rotation); prepare() fixes any mismatch.
        width, height = (cfg.height, cfg.width) if cfg.rotate in (90, 270) else (cfg.width, cfg.height)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, cfg.fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # prefer the newest frame (not all backends honour it)
        self._index = cfg.index

    def read(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        self._cap.release()

    def describe(self) -> str:
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = self._cap.get(cv2.CAP_PROP_FPS)
        return f"opencv camera {self._index}: {w}x{h} @ {fps:.0f} fps (native)"


def open_camera(cfg: CameraConfig) -> Camera:
    if cfg.source == "opencv":
        return OpenCVCamera(cfg)
    raise NotImplementedError("camera.source 'picamera2' (Pi CSI camera) is planned for the Pi stage")


def prepare(frame: np.ndarray, cfg: CameraConfig) -> np.ndarray:
    """Flip, rotate, then centre-crop to the target aspect ratio and resize."""
    if cfg.flip_horizontal:
        frame = cv2.flip(frame, 1)
    if cfg.rotate:
        frame = cv2.rotate(frame, _ROTATIONS[cfg.rotate])
    return _fit(frame, cfg.width, cfg.height)


def _fit(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if (w, h) == (width, height):
        return frame
    target = width / height
    if w / h > target:  # too wide: crop the sides
        new_w = int(round(h * target))
        x0 = (w - new_w) // 2
        frame = frame[:, x0 : x0 + new_w]
    elif w / h < target:  # too tall: crop top and bottom
        new_h = int(round(w / target))
        y0 = (h - new_h) // 2
        frame = frame[y0 : y0 + new_h]
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
