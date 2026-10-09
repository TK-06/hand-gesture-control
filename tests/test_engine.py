import dataclasses
import math

from gesturectl.config import AppConfig
from gesturectl.engine import GestureEngine
from gesturectl.gestures.base import Observation, Recognizer
from synth import phases, run, track


class Scripted(Recognizer):
    """Fires the scripted gestures at the given (relative) times."""

    def __init__(self, script: dict[float, list[str]], t0: float = 100.0):
        self.script = {round(t0 + t, 3): names for t, names in script.items()}

    def update(self, obs: Observation) -> list[str]:
        return list(self.script.get(round(obs.t, 3), []))

    def reset(self) -> None:
        pass


def scripted_run(script, cfg=None):
    cfg = cfg or AppConfig()
    engine = GestureEngine(cfg, recognizers=[Scripted(script)])
    events = []
    for t, hand in track(3.0, "open", fps=10):
        events.extend(engine.update(t, hand))
    return events


def test_cooldown_suppresses_a_different_gesture():
    events = scripted_run({0.0: ["swipe_right"], 0.5: ["swipe_left"], 1.2: ["swipe_up"]})
    assert [e.gesture for e in events] == ["swipe_right", "swipe_up"]


def test_cooldown_suppresses_repeating_a_one_shot_gesture():
    events = scripted_run({0.0: ["swipe_right"], 0.5: ["swipe_right"]})
    assert [e.gesture for e in events] == ["swipe_right"]


def test_circle_steps_may_repeat_inside_the_cooldown_but_not_switch_direction():
    events = scripted_run({0.0: ["circle_cw"], 0.4: ["circle_cw"], 0.6: ["circle_ccw"]})
    assert [e.gesture for e in events] == ["circle_cw", "circle_cw"]


def test_events_carry_the_mapped_action():
    events = scripted_run({0.0: ["open_to_fist"], 1.5: ["fist_to_open"]})
    assert [(e.gesture, e.action) for e in events] == [("open_to_fist", "play"), ("fist_to_open", "pause")]


def test_disabled_gesture_is_dropped_without_starting_a_cooldown():
    cfg = AppConfig()
    cfg.mapping["swipe_right"] = None
    events = scripted_run({0.0: ["swipe_right"], 0.3: ["swipe_left"]}, cfg)
    assert [e.gesture for e in events] == ["swipe_left"]


def _grab_frames(**kw):
    pose_at = phases((0.6, "fist"), (math.inf, "open"))
    return track(1.3, pose_at, **kw)


def test_gesture_inside_active_zone_fires():
    cfg = AppConfig()
    cfg.gating = dataclasses.replace(cfg.gating, active_zone=(0.3, 0.3, 0.7, 0.7))
    assert run(_grab_frames(), cfg) == ["fist_to_open"]


def test_hand_outside_active_zone_is_ignored():
    cfg = AppConfig()
    cfg.gating = dataclasses.replace(cfg.gating, active_zone=(0.6, 0.0, 1.0, 1.0))
    assert run(_grab_frames(), cfg) == []


def test_far_away_small_hand_is_ignored():
    assert run(_grab_frames(scale=12.0)) == []


def test_low_confidence_hand_is_ignored():
    frames = [(t, dataclasses.replace(h, score=0.3) if h else None) for t, h in _grab_frames()]
    assert run(frames) == []


def test_no_hand_frames_produce_nothing():
    assert run(track(2.0, phases((math.inf, None)))) == []
