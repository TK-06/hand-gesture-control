import json
import math

import pytest

from gesturectl.config import AppConfig
from gesturectl.engine import Event
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


def _events(*spec):
    """_events((0.0, "circle_cw"), (0.5, "circle_cw")) -> Event list."""
    return [Event(t=t, gesture=g, action="x") for t, g in spec]


@pytest.mark.parametrize(
    "label, events, reps, ok",
    [
        ("none", [], 1, True),
        ("none", [(1.0, "swipe_up")], 1, False),
        ("circle_cw", [(0.0, "circle_cw"), (0.5, "circle_cw")], 1, True),  # one continuous circle
        ("circle_cw", [], 1, False),
        ("circle_cw", [(0.0, "circle_cw"), (0.5, "circle_ccw")], 1, False),
        ("circle_cw", [(0.0, "circle_cw"), (0.5, "circle_cw"), (4.0, "circle_cw")], 2, True),  # two bursts
        ("circle_cw", [(0.0, "circle_cw"), (0.5, "circle_cw")], 2, False),
        ("swipe_left", [(1.0, "swipe_left")], 1, True),
        ("swipe_left", [(1.0, "swipe_left"), (5.0, "swipe_left")], 1, False),
        ("swipe_left", [(t, "swipe_left") for t in (1, 4, 7, 10, 13)], 5, True),
        ("swipe_left", [(t, "swipe_left") for t in (1, 4, 7, 10)], 5, False),
        ("open_to_fist", [(1.0, "fist_to_open")], 1, False),
    ],
)
def test_check_rules(label, events, reps, ok):
    assert check(label, _events(*events), reps)[0] is ok


def test_reps_survive_a_round_trip(tmp_path):
    path = tmp_path / "x.json"
    save(Recording(label="swipe_up", frame_size=FRAME_SIZE, frames=track(0.2, "two"), reps=5), path)
    assert load(path).reps == 5


def test_old_files_without_reps_load_as_one(tmp_path):
    path = tmp_path / "x.json"
    save(Recording(label="swipe_up", frame_size=FRAME_SIZE, frames=track(0.2, "two")), path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    del doc["reps"]
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert load(path).reps == 1
