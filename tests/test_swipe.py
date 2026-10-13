import math

import pytest

from synth import line_path, phases, run, track

DIRS = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}


def swipe_path(direction, *, start=(160.0, 120.0), distance=90.0, t_start=0.5, duration=0.35):
    dx, dy = DIRS[direction]
    end = (start[0] + dx * distance, start[1] + dy * distance)
    return line_path(start, end, t_start, t_start + duration)


def swipe(direction, *, arm=0.5, duration=0.35, distance=90.0, fps=30, mirror=False, pose="two"):
    path = swipe_path(direction, distance=distance, t_start=arm, duration=duration)
    return track(arm + duration + 0.4, pose, path, fps=fps, mirror=mirror)


@pytest.mark.parametrize("direction", list(DIRS))
@pytest.mark.parametrize("fps", [10, 30])
@pytest.mark.parametrize("mirror", [False, True])
def test_swipe_each_direction(direction, fps, mirror):
    assert run(swipe(direction, fps=fps, mirror=mirror)) == [f"swipe_{direction}"]


def test_fast_swipe_at_10_fps():
    assert run(swipe("right", duration=0.2, fps=10)) == ["swipe_right"]


def test_swipe_without_holding_still_first_does_not_fire():
    assert run(swipe("right", arm=0.1)) == []


def test_slow_drift_does_not_fire():
    assert run(swipe("right", duration=3.0)) == []  # ~0.5 hand scales per second


def test_short_movement_does_not_fire():
    assert run(swipe("right", distance=40.0)) == []


def test_diagonal_movement_does_not_fire():
    path = line_path((120.0, 80.0), (190.0, 150.0), 0.5, 0.85)
    assert run(track(1.3, "two", path)) == []


@pytest.mark.parametrize("direction", ["left", "right"])
@pytest.mark.parametrize("mirror", [False, True])
def test_finger_gun_held_upright_swipes_too(direction, mirror):
    # two fingers together pointing up, thumb out: the user's preferred left/right pose
    assert run(swipe(direction, pose="gun", mirror=mirror)) == [f"swipe_{direction}"]


def test_other_poses_do_not_swipe():
    assert run(swipe("right", pose="open")) == []
    assert run(swipe("right", pose="three")) == []


def test_return_stroke_does_not_fire_the_opposite_direction():
    out = swipe_path("right", t_start=0.5, duration=0.35)
    back = line_path((250.0, 120.0), (160.0, 120.0), 1.3, 1.65)

    def path(t):
        return out(t) if t < 1.3 else back(t)

    assert run(track(2.2, "two", path)) == ["swipe_right"]


def test_repeat_swipe_after_releasing_the_pose():
    first = swipe_path("right", t_start=0.5, duration=0.35)
    second = swipe_path("right", t_start=2.0, duration=0.35)

    def path(t):
        return first(t) if t < 1.3 else second(t)

    pose_at = phases((1.3, "two"), (1.5, "half"), (math.inf, "two"))
    assert run(track(2.8, pose_at, path)) == ["swipe_right", "swipe_right"]
