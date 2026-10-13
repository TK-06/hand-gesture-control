import math

import pytest

from synth import line_path, phases, track
from synth import run as _run

# These motion gestures are switched off in the default mapping; enable them here.
FAMILY = ("fist_to_open", "open_to_fist")


def run(frames, cfg=None):
    return _run(frames, cfg, gestures=FAMILY)


def grab(start, end, *, hold=0.6, transition=0.15, target_hold=0.5, fps=30, mirror=False, path=None):
    pose_at = phases((hold, start), (hold + transition, "half"), (math.inf, end))
    return track(hold + transition + target_hold, pose_at, path, fps=fps, mirror=mirror)


@pytest.mark.parametrize("fps", [10, 30])
@pytest.mark.parametrize("mirror", [False, True])
def test_fist_to_open(fps, mirror):
    assert run(grab("fist", "open", fps=fps, mirror=mirror)) == ["fist_to_open"]


@pytest.mark.parametrize("fps", [10, 30])
@pytest.mark.parametrize("mirror", [False, True])
def test_open_to_fist(fps, mirror):
    assert run(grab("open", "fist", fps=fps, mirror=mirror)) == ["open_to_fist"]


def test_instant_transition_without_intermediate_frames():
    assert run(grab("open", "fist", transition=0.0)) == ["open_to_fist"]


def test_start_pose_held_too_briefly_does_not_fire():
    assert run(grab("open", "fist", hold=0.25)) == []


def test_slow_transition_does_not_fire():
    assert run(grab("open", "fist", transition=1.2)) == []


def test_target_pose_held_too_briefly_does_not_fire():
    pose_at = phases((0.6, "open"), (0.7, "fist"), (math.inf, "half"))
    assert run(track(1.5, pose_at)) == []


def test_hand_dropping_while_closing_does_not_fire():
    # e.g. an open hand dropping onto the gear knob
    path = line_path((160.0, 100.0), (160.0, 190.0), 0.6, 0.9)
    assert run(grab("open", "fist", path=path)) == []


def test_reaching_with_an_open_hand_then_grabbing_does_not_fire():
    # the hand moves the whole time it is open, so it never arms
    path = line_path((60.0, 60.0), (200.0, 160.0), 0.0, 0.75)
    assert run(grab("open", "fist", hold=0.75, path=path)) == []


def test_pause_does_not_chain_into_play_while_the_hand_stays_up():
    pose_at = phases((0.6, "fist"), (2.5, "open"), (math.inf, "fist"))
    assert run(track(3.2, pose_at)) == ["fist_to_open"]


def test_after_releasing_the_hand_the_reverse_gesture_works():
    pose_at = phases((0.6, "fist"), (1.6, "open"), (2.1, None), (2.8, "open"), (math.inf, "fist"))
    assert run(track(3.4, pose_at)) == ["fist_to_open", "open_to_fist"]


def test_open_hand_with_thumb_tucked_is_not_five_fingers():
    pose_at = phases((0.6, "open_thumb_in"), (math.inf, "fist"))
    assert run(track(1.2, pose_at)) == []
