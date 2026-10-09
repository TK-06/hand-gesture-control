import dataclasses

import numpy as np
import pytest

from gesturectl.camera import prepare
from gesturectl.config import AppConfig, CameraConfig
from gesturectl.engine import GestureEngine
from gesturectl.overlay import draw
from synth import track


def _marked_frame(w, h):
    frame = np.zeros((h, w, 3), np.uint8)
    frame[:, : w // 10] = 255  # bright band on the left edge
    return frame


@pytest.mark.parametrize("native", [(640, 360), (640, 480), (1280, 720), (320, 240)])
def test_prepare_fits_any_camera_to_the_processing_size(native):
    out = prepare(_marked_frame(*native), CameraConfig())
    assert out.shape == (240, 320, 3)


def test_prepare_mirrors_when_flip_is_on():
    out = prepare(_marked_frame(320, 240), CameraConfig(flip_horizontal=True))
    assert out[:, -1].mean() > 200 and out[:, 0].mean() < 50


def test_prepare_rotates_into_the_processing_size():
    cfg = CameraConfig(width=240, height=320, rotate=90, flip_horizontal=False)
    assert prepare(_marked_frame(320, 240), cfg).shape == (320, 240, 3)


def test_overlay_draws_without_error():
    cfg = AppConfig()
    cfg.gating = dataclasses.replace(cfg.gating, active_zone=(0.1, 0.1, 0.9, 0.9))
    engine = GestureEngine(cfg)
    frames = track(0.5, "point")
    for t, hand in frames:
        engine.update(t, hand)
    t, hand = frames[-1]
    img = draw(
        np.zeros((240, 320, 3), np.uint8), hand=hand, engine=engine, t=t, fps=20.0, infer_ms=14.0,
        banner="volume_up  (circle_cw)", scale=2.0, recording=True,
    )
    assert img.shape == (480, 640, 3)
    assert img.any()
