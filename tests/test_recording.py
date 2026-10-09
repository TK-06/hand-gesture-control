import math

import pytest

from gesturectl.config import AppConfig
from gesturectl.recording import Recording, check, load, replay, save
from synth import FRAME_SIZE, circle_path, phases, run, track


def test_save_load_replay_round_trip(tmp_path):
    frames = track(1.6, "point", circle_path(radius=30.0, period=1.0, t_start=0.3), drop=lambda t: 0.5 <= t < 0.55)
    path = tmp_path / "circle_cw" / "take.json"
    save(Recording(label="circle_cw", frame_size=FRAME_SIZE, frames=frames), path)

    rec = load(path)
    assert rec.label == "circle_cw"
    assert len(rec.frames) == len(frames)
    assert any(hand is None for _, hand in rec.frames)
    assert [e.gesture for e in replay(rec, AppConfig())] == run(frames) == ["circle_cw"]


def test_replay_ignores_disabled_mapping():
    cfg = AppConfig()
    cfg.mapping["fist_to_open"] = None
    frames = track(1.3, phases((0.6, "fist"), (math.inf, "open")))
    rec = Recording(label="fist_to_open", frame_size=FRAME_SIZE, frames=frames)
    assert [e.gesture for e in replay(rec, cfg)] == ["fist_to_open"]


def test_unknown_label_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        save(Recording(label="wave", frame_size=FRAME_SIZE), tmp_path / "x.json")


@pytest.mark.parametrize(
    "label, fired, ok",
    [
        ("none", [], True),
        ("none", ["swipe_up"], False),
        ("circle_cw", ["circle_cw", "circle_cw"], True),
        ("circle_cw", [], False),
        ("circle_cw", ["circle_cw", "circle_ccw"], False),
        ("swipe_left", ["swipe_left"], True),
        ("swipe_left", ["swipe_left", "swipe_left"], False),
        ("open_to_fist", ["fist_to_open"], False),
    ],
)
def test_check_rules(label, fired, ok):
    assert check(label, fired)[0] is ok
