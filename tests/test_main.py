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


# --- stall watchdog -------------------------------------------------------------------
# Real subprocesses: the point is that the process exits by itself while its main thread
# is stuck, which can't be tested in-process.

import subprocess
import sys
import textwrap

_WATCHDOG_SCRIPT = textwrap.dedent(
    """
    import sys, time
    import numpy as np
    import gesturectl.__main__ as m
    from gesturectl.app import FrameResult

    MODE = sys.argv[1]

    class Cam:
        def describe(self): return "fake camera"

    class Meter:
        fps = 9.0
        ms = 1.0

    class Pipe:
        def __init__(self, cfg):
            self.camera, self.meter, self.engine, self.n = Cam(), Meter(), None, 0

        def step(self):
            self.n += 1
            if MODE == "hang" and self.n == 3:
                time.sleep(3600)  # stuck inside a "native" call; the program can't react
            time.sleep(0.05)
            return FrameResult(t=time.monotonic(), frame=np.zeros((2, 2, 3), np.uint8), hand=None, events=[], infer_ms=1.0)

        def close(self): pass

    m.Pipeline = Pipe
    args = ["--no-window", "--stall-timeout", "1.5", "--log-file", "logs/gesturectl.log"]
    code = m.main(args + (["--duration", "0.5"] if MODE == "ok" else []))
    if MODE == "ok":
        time.sleep(3)  # a watchdog that was left armed would kill us in here
    print("alive", code, flush=True)
    """
)


def _run_watchdog_script(tmp_path, mode: str) -> subprocess.CompletedProcess:
    (tmp_path / "logs").mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, "-c", _WATCHDOG_SCRIPT, mode],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )


def test_a_stalled_main_loop_exits_with_status_1_and_leaves_the_stacks(tmp_path):
    result = _run_watchdog_script(tmp_path, "hang")
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr[-500:])
    assert "alive" not in result.stdout
    dump = (tmp_path / "logs" / "gesturectl-stall.log").read_text(encoding="utf-8")
    assert "watchdog armed" in dump
    assert "most recent call first" in dump
    assert "in step" in dump  # names where the program was stuck


def test_a_healthy_run_shuts_down_and_disarms_the_watchdog(tmp_path):
    result = _run_watchdog_script(tmp_path, "ok")
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr[-500:])
    assert "alive 0" in result.stdout
    dump = (tmp_path / "logs" / "gesturectl-stall.log").read_text(encoding="utf-8")
    assert "most recent call first" not in dump
