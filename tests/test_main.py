"""The main loop's shutdown: a systemd stop (SIGTERM) must end the loop between frames
and close the camera and tracker normally, never interrupt them mid-call."""

import signal

import numpy as np

import gesturectl.__main__ as main_mod
from gesturectl.app import FrameResult


class _Meter:
    fps = 9.0
    ms = 110.0


class _Camera:
    def describe(self) -> str:
        return "fake camera"


class FakePipeline:
    """Sends SIGTERM to this process during frame ``term_at``; records what ran."""

    instances: list["FakePipeline"] = []

    def __init__(self, cfg, term_at: int = 3):
        self.camera = _Camera()
        self.meter = _Meter()
        self.engine = None
        self.steps = 0
        self.term_at = term_at
        self.in_step = False
        self.interrupted_in_step = False
        self.closed = False
        FakePipeline.instances.append(self)

    def step(self) -> FrameResult:
        self.steps += 1
        self.in_step = True
        try:
            if self.steps == self.term_at:
                signal.raise_signal(signal.SIGTERM)
            return FrameResult(t=float(self.steps), frame=np.zeros((2, 2, 3), np.uint8), hand=None, events=[], infer_ms=1.0)
        except BaseException:
            self.interrupted_in_step = True
            raise
        finally:
            self.in_step = False

    def close(self) -> None:
        self.closed = True


def test_sigterm_ends_the_loop_between_frames_and_closes_cleanly(monkeypatch):
    FakePipeline.instances.clear()
    monkeypatch.setattr(main_mod, "Pipeline", FakePipeline)
    previous = signal.getsignal(signal.SIGTERM)
    try:
        code = main_mod.main(["--no-window", "--duration", "60"])
    finally:
        signal.signal(signal.SIGTERM, previous)

    pipe = FakePipeline.instances[-1]
    assert code == 0
    assert not pipe.interrupted_in_step  # the signal never broke into a frame
    assert pipe.steps == pipe.term_at  # stopped right after the frame it arrived in
    assert pipe.closed
