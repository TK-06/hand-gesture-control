"""Camera sources: OpenCV (USB / laptop webcams) and picamera2 (Pi ribbon cameras).

Cameras return raw BGR frames; ``prepare()`` orients them (flip/rotate) and fits them to
the processing size from the config (``camera.width`` x ``camera.height`` after rotation)."""

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


class PicameraCamera:
    """Raspberry Pi ribbon (CSI) cameras through picamera2 / libcamera.

    picamera2 comes from apt (``sudo apt install python3-picamera2``), so the venv must be
    created with ``--system-site-packages``. Its "RGB888" format is laid out B, G, R in
    memory, which is exactly what OpenCV expects."""

    def __init__(self, cfg: CameraConfig):
        try:
            from picamera2 import Picamera2
        except ImportError as exc:
            raise RuntimeError(
                "camera.source is 'picamera2' but picamera2 is not importable. On the Pi: "
                "sudo apt install python3-picamera2, and create the venv with --system-site-packages"
            ) from exc
        width, height = (cfg.height, cfg.width) if cfg.rotate in (90, 270) else (cfg.width, cfg.height)
        self._cam = Picamera2(cfg.index)
        video_cfg = self._cam.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"},
            controls={"FrameRate": float(cfg.fps)},
        )
        self._cam.configure(video_cfg)
        self._cam.start()
        self._index = cfg.index
        self._size = (width, height)
        self._fps = cfg.fps

    def read(self) -> np.ndarray | None:
        return self._cam.capture_array("main")

    def close(self) -> None:
        self._cam.stop()
        self._cam.close()

    def describe(self) -> str:
        w, h = self._size
        return f"picamera2 camera {self._index}: {w}x{h} @ {self._fps} fps (requested)"


def picamera2_available() -> bool:
    """True when picamera2 imports and libcamera reports at least one camera."""
    try:
        from picamera2 import Picamera2
    except Exception:
        return False
    try:
        return len(Picamera2.global_camera_info()) > 0
    except Exception:
        return False


def open_camera(cfg: CameraConfig) -> Camera:
    source = cfg.source
    if source == "auto":
        source = "picamera2" if picamera2_available() else "opencv"
    if source == "picamera2":
        return PicameraCamera(cfg)
    return OpenCVCamera(cfg)


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
