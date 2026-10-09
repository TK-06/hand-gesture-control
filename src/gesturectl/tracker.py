"""MediaPipe Hand Landmarker (Tasks API) in VIDEO mode: palm detection runs only when
tracking is lost; otherwise the landmark model tracks the hand from the previous frame."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from gesturectl.config import TrackerConfig
from gesturectl.geometry import hand_scale
from gesturectl.hand import HandFrame

# Quiet MediaPipe's native INFO/WARNING logging (must be set before it loads).
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


class HandTracker:
    def __init__(self, cfg: TrackerConfig, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"model not found: {model_path} (run: python scripts/download_model.py)")
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        self._mp = mp
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=cfg.num_hands,
            min_hand_detection_confidence=cfg.min_detection,
            min_hand_presence_confidence=cfg.min_presence,
            min_tracking_confidence=cfg.min_tracking,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_ts = -1

    def process(self, frame_bgr: np.ndarray, t: float) -> list[HandFrame]:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        ts = max(int(t * 1000), self._last_ts + 1)  # VIDEO mode needs strictly increasing timestamps
        self._last_ts = ts
        result = self._landmarker.detect_for_video(image, ts)

        h, w = frame_bgr.shape[:2]
        hands = []
        for i, points in enumerate(result.hand_landmarks):
            lm = np.array([[p.x * w, p.y * h, p.z * w] for p in points], dtype=float)
            cats = result.handedness[i] if i < len(result.handedness) else []
            label = cats[0].category_name if cats else "?"
            score = float(cats[0].score) if cats else 0.0
            hands.append(HandFrame(t=t, landmarks=lm, handedness=label or "?", score=score, frame_size=(w, h)))
        return hands

    def close(self) -> None:
        self._landmarker.close()


def largest(hands: list[HandFrame]) -> HandFrame | None:
    """With num_hands > 1, the hand closest to the camera (largest) is the one that counts."""
    return max(hands, key=lambda h: hand_scale(h.landmarks), default=None)
