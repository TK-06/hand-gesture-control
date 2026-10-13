import math

import pytest

from synth import circle_path, line_path, phases, run, still, track


def circling(
    clockwise=True, *, revs=1.2, period=1.0, fps=30, radius=30.0, mirror=False, noise=0.0, hold=0.3, pose="point"
):
    return track(
        hold + revs * period,
        pose,
        circle_path(radius=radius, period=period, clockwise=clockwise, t_start=hold),
        fps=fps,
        mirror=mirror,
        noise_px=noise,
    )


@pytest.mark.parametrize("fps", [10, 30])
@pytest.mark.parametrize("mirror", [False, True])
def test_one_clockwise_circle_is_one_step(fps, mirror):
    assert run(circling(True, fps=fps, mirror=mirror)) == ["circle_cw"]


@pytest.mark.parametrize("fps", [10, 30])
@pytest.mark.parametrize("mirror", [False, True])
def test_one_counterclockwise_circle_is_one_step(fps, mirror):
    assert run(circling(False, fps=fps, mirror=mirror)) == ["circle_ccw"]


@pytest.mark.parametrize("period", [0.6, 2.0])
def test_slow_and_fast_circles(period):
    assert run(circling(True, period=period)) == ["circle_cw"]


def test_keeps_stepping_every_half_turn_after_the_first_full_circle():
    # 2.75 turns = 990 deg -> steps at 360, 540, 720, 900 (repeats are exempt from cooldown)
    assert run(circling(True, revs=2.75)) == ["circle_cw"] * 4


def test_three_quarter_circle_does_not_fire():
    assert run(circling(True, revs=0.75)) == []


def test_noisy_circle_still_counts():
    assert run(circling(True, noise=1.0)) == ["circle_cw"]


def test_holding_a_pointing_finger_still_with_jitter_does_not_fire():
    assert run(track(4.0, "point", still(), noise_px=1.5, seed=3)) == []


def test_tiny_circle_does_not_fire():
    assert run(circling(True, revs=2.0, radius=6.0)) == []


def test_zigzag_does_not_fire():
    def zigzag(t):
        phase = (t * 2.0) % 2.0  # back and forth twice a second
        x = 120.0 + 80.0 * (phase if phase < 1.0 else 2.0 - phase)
        return (x, 120.0 + 10.0 * math.sin(t * 3.0))

    assert run(track(3.0, "point", zigzag)) == []


def test_arc_while_moving_the_hand_away_does_not_fire():
    # a 200-degree sweep, like moving a pointing hand around something
    def arc(t):
        a = math.radians(200.0) * min(t / 1.0, 1.0)
        return (160.0 + 60.0 * math.cos(a), 120.0 + 60.0 * math.sin(a))

    assert run(track(1.5, "point", arc)) == []


def test_circling_with_an_open_hand_does_not_fire():
    assert run(circling(True, pose="open", revs=1.5)) == []


def test_reversing_direction_restarts_the_count():
    def path(t):
        # half a turn clockwise, then 1.6 turns back the other way
        a = 2 * math.pi * (t if t < 0.5 else 1.0 - t)
        return (160.0 + 30.0 * math.cos(a), 120.0 + 30.0 * math.sin(a))

    assert run(track(0.5 + 1.6, "point", path)) == ["circle_ccw"]


def test_switching_pose_mid_circle_resets_progress():
    pose = phases((0.9, "point"), (1.2, "open"), (math.inf, "point"))
    frames = track(0.3 + 1.4, pose, circle_path(radius=30.0, period=1.0, t_start=0.3))
    assert run(frames) == []


def test_short_tracking_dropout_is_bridged():
    frames = track(
        1.6, "point", circle_path(radius=30.0, period=1.0, t_start=0.3), drop=lambda t: 0.8 <= t < 0.9
    )
    assert run(frames) == ["circle_cw"]


def test_straight_line_with_pointing_finger_does_not_fire():
    assert run(track(1.5, "point", line_path((60.0, 120.0), (260.0, 120.0), 0.3, 1.0))) == []


@pytest.mark.parametrize("mirror", [False, True])
def test_circles_with_the_finger_pointing_at_the_camera(mirror):
    frames = track(1.5, "point_at_camera", circle_path(radius=30.0, period=1.0, t_start=0.3), fps=9, mirror=mirror)
    assert run(frames) == ["circle_cw"]
