import math

import pytest

from synth import PHONE_AXIS, THUMB_AXIS, aim, line_path, phases, run, track


def held(pose, seconds=1.5, *, deg=None, axis=None, mirror=False, fps=30, path=None, **kw):
    """A pose held in front of the camera, optionally pointed in a direction."""
    angle = aim(pose, *axis, deg, mirror=mirror) if deg is not None else 0.0
    return track(seconds, pose, path, angle_deg=angle, mirror=mirror, fps=fps, **kw)


@pytest.mark.parametrize("fps", [9, 30])
@pytest.mark.parametrize("mirror", [False, True])
def test_five_fingers_held_still_pauses(fps, mirror):
    assert run(held("open", fps=fps, mirror=mirror)) == ["open_palm"]


@pytest.mark.parametrize("direction, deg", [("up", 90), ("right", 0), ("left", 180)])
@pytest.mark.parametrize("fps", [9, 30])
@pytest.mark.parametrize("mirror", [False, True])
def test_thumb_up_right_left(direction, deg, fps, mirror):
    frames = held("thumb", deg=deg, axis=THUMB_AXIS, mirror=mirror, fps=fps)
    assert run(frames) == [f"thumb_{direction}"]


def test_thumb_down_is_off_by_default_but_works_when_mapped():
    frames = held("thumb", deg=-90, axis=THUMB_AXIS)
    assert run(frames) == []
    assert run(frames, gestures=["thumb_down"]) == ["thumb_down"]


@pytest.mark.parametrize(
    "deg, expected",
    [
        (90, "phone_vertical"),  # thumb up, pinky down: like holding a phone
        (-90, "phone_vertical"),
        (0, "phone_horizontal"),  # pinky left, thumb right
        (180, "phone_horizontal"),  # the other hand's natural way round
    ],
)
@pytest.mark.parametrize("fps", [9, 30])
@pytest.mark.parametrize("mirror", [False, True])
def test_phone_vertical_answers_horizontal_hangs_up(deg, expected, fps, mirror):
    assert run(held("phone", deg=deg, axis=PHONE_AXIS, mirror=mirror, fps=fps)) == [expected]


def test_diagonal_thumb_or_phone_fires_nothing():
    assert run(held("thumb", deg=45, axis=THUMB_AXIS)) == []
    assert run(held("phone", deg=45, axis=PHONE_AXIS)) == []


def test_held_too_briefly_fires_nothing():
    assert run(held("open", seconds=0.5)) == []


def test_holding_on_fires_only_once():
    assert run(held("open", seconds=5.0)) == ["open_palm"]


def test_a_hand_moving_through_the_pose_never_fires():
    sweep = line_path((40.0, 120.0), (280.0, 120.0), 0.0, 2.4)  # ~1.7 hand scales per second
    assert run(held("open", seconds=2.4, path=sweep)) == []


def test_lowering_the_hand_rearms_the_pose():
    up = aim("thumb", *THUMB_AXIS, 90)
    pose_at = phases((1.0, "thumb"), (1.6, None), (math.inf, "thumb"))
    assert run(track(3.0, pose_at, angle_deg=up)) == ["thumb_up", "thumb_up"]


def test_a_short_tracking_dropout_does_not_refire():
    up = aim("thumb", *THUMB_AXIS, 90)
    frames = track(3.0, "thumb", angle_deg=up, drop=lambda t: 1.5 <= t < 1.6)
    assert run(frames) == ["thumb_up"]


def test_switching_pose_fires_the_new_one_after_its_own_hold():
    up = aim("thumb", *THUMB_AXIS, 90)
    pose_at = phases((1.2, "open"), (math.inf, "thumb"))  # pause, then play
    assert run(track(3.0, pose_at, angle_deg=up)) == ["open_palm", "thumb_up"]


@pytest.mark.parametrize("pose", ["fist", "point", "two", "half"])
def test_other_poses_held_still_fire_nothing(pose):
    # e.g. a fist gripping the gear knob
    assert run(held(pose, seconds=3.0)) == []


@pytest.mark.parametrize("deg, gesture", [(0, "thumb_right"), (180, "thumb_left")])
def test_holding_next_or_previous_repeats_every_2_s(deg, gesture):
    # fires at ~0.7 s, then again at ~2.7 s and ~4.7 s while still held
    assert run(held("thumb", seconds=5.0, deg=deg, axis=THUMB_AXIS)) == [gesture] * 3


def test_play_does_not_repeat_while_held():
    assert run(held("thumb", seconds=5.0, deg=90, axis=THUMB_AXIS)) == ["thumb_up"]


def test_repeat_needs_the_hand_held_still():
    # thumb right, but the hand drifts the whole time after the first skip
    drift = line_path((60.0, 120.0), (300.0, 120.0), 1.0, 5.0)  # ~1 hand length/s until the end
    assert run(held("thumb", seconds=5.0, deg=0, axis=THUMB_AXIS, path=drift)) == ["thumb_right"]
