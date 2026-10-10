"""picamera2 only exists on a Raspberry Pi, so these tests use a stand-in module. They
check our wiring (requested size, format, frame rate, auto-detection, error message),
not the real camera, which still needs testing on the Pi."""

import sys
import types

import numpy as np
import pytest

from gesturectl.camera import PicameraCamera, open_camera, picamera2_available
from gesturectl.config import CameraConfig


class FakePicamera2:
    instances: list = []
    cameras: list = [{"Model": "ov5647"}]

    def __init__(self, camera_num=0):
        self.camera_num = camera_num
        self.closed = False
        FakePicamera2.instances.append(self)

    @classmethod
    def global_camera_info(cls):
        return cls.cameras

    def create_video_configuration(self, main, controls):
        self.main, self.controls = main, controls
        return {"main": main}

    def configure(self, config):
        self.config = config

    def start(self):
        self.started = True

    def capture_array(self, name="main"):
        w, h = self.main["size"]
        return np.zeros((h, w, 3), np.uint8)

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


@pytest.fixture
def fake_picamera2(monkeypatch):
    module = types.ModuleType("picamera2")
    module.Picamera2 = FakePicamera2
    FakePicamera2.instances = []
    FakePicamera2.cameras = [{"Model": "ov5647"}]
    monkeypatch.setitem(sys.modules, "picamera2", module)
    return FakePicamera2


def test_picamera_requests_processing_size_in_opencv_byte_order(fake_picamera2):
    cam = open_camera(CameraConfig(source="picamera2"))
    assert cam.read().shape == (240, 320, 3)
    inst = fake_picamera2.instances[0]
    assert inst.main == {"size": (320, 240), "format": "RGB888"}
    assert inst.controls == {"FrameRate": 30.0}
    cam.close()
    assert inst.closed


def test_rotated_mount_requests_the_unrotated_sensor_size(fake_picamera2):
    open_camera(CameraConfig(source="picamera2", width=240, height=320, rotate=90))
    assert fake_picamera2.instances[0].main["size"] == (320, 240)


def test_auto_uses_the_ribbon_camera_when_one_is_found(fake_picamera2):
    assert isinstance(open_camera(CameraConfig(source="auto")), PicameraCamera)


def test_auto_ignores_picamera2_without_a_camera(fake_picamera2):
    fake_picamera2.cameras = []
    assert picamera2_available() is False


def test_missing_picamera2_gives_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "picamera2", None)  # makes the import fail
    assert picamera2_available() is False
    with pytest.raises(RuntimeError, match="python3-picamera2"):
        open_camera(CameraConfig(source="picamera2"))
