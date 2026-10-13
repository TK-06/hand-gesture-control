import itertools

import numpy as np
import pytest

from gesturectl.config import GeometryConfig
from gesturectl.geometry import (
    FingerState,
    Pose,
    classify_pose,
    finger_states,
    hand_scale,
    palm_center,
    phone_orientation,
    thumb_direction,
)
from synth import PHONE_AXIS, THUMB_AXIS, aim, make_hand

CFG = GeometryConfig()

EXPECTED = {
    "open": Pose.OPEN,
    "fist": Pose.FIST,
    "point": Pose.POINT,
    "two": Pose.TWO,
    "three": Pose.OTHER,
    "half": Pose.OTHER,
    "open_thumb_in": Pose.OTHER,  # "five fingers up" needs the thumb out too
    "gun": Pose.TWO,  # two fingers + thumb out still counts as the swipe pose
    "thumb": Pose.THUMB,  # fist with the thumb out
    "phone": Pose.PHONE,  # thumb + pinky out
    "point_at_camera": Pose.POINT,  # straight index aimed at the camera, bent only at the knuckle
    "point_at_camera_thumb_out": Pose.POINT,  # ...even with the thumb sticking out (not "thumb")
}


@pytest.mark.parametrize(
    "pose, mirror, angle, scale",
    [
        (pose, mirror, angle, scale)
        for pose, mirror, angle, scale in itertools.product(
            EXPECTED, (False, True), (0.0, 35.0, -60.0, 90.0, 180.0), (25.0, 60.0, 110.0)
        )
    ],
)
def test_pose_is_invariant_to_hand_side_rotation_and_size(pose, mirror, angle, scale):
    lm = make_hand(pose, mirror=mirror, angle_deg=angle, scale=scale)
    assert classify_pose(lm, CFG) is EXPECTED[pose]


@pytest.mark.parametrize("pose", list(EXPECTED))
def test_pose_survives_landmark_jitter(pose):
    rng = np.random.default_rng(1)
    base = make_hand(pose, scale=60.0)
    for _ in range(30):
        noisy = base + rng.normal(0.0, 1.0, base.shape)  # ~1 px jitter at 60 px hand scale
        assert classify_pose(noisy, CFG) is EXPECTED[pose]


def test_finger_states_for_point():
    states = finger_states(make_hand("point"), CFG)
    assert states == {
        "index": FingerState.EXTENDED,
        "middle": FingerState.CURLED,
        "ring": FingerState.CURLED,
        "pinky": FingerState.CURLED,
    }


def test_half_curled_fingers_are_uncertain():
    states = finger_states(make_hand("half"), CFG)
    assert set(states.values()) == {FingerState.UNCERTAIN}


@pytest.mark.parametrize("pose", ["open", "fist", "point"])
def test_hand_scale_is_wrist_to_middle_mcp_and_stable_across_poses(pose):
    assert hand_scale(make_hand(pose, scale=60.0)) == pytest.approx(60.0, rel=1e-6)


def test_palm_center_is_where_the_hand_was_placed():
    lm = make_hand("fist", center=(200.0, 90.0), angle_deg=45.0)
    assert palm_center(lm) == pytest.approx([200.0, 90.0])


@pytest.mark.parametrize(
    "deg, expected",
    [(90, "up"), (0, "right"), (180, "left"), (-90, "down"), (25, "right"), (65, "up"), (45, None), (135, None)],
)
@pytest.mark.parametrize("mirror", [False, True])
def test_thumb_direction_as_seen_by_the_user(deg, expected, mirror):
    lm = make_hand("thumb", mirror=mirror, angle_deg=aim("thumb", *THUMB_AXIS, deg, mirror=mirror))
    assert thumb_direction(lm, 35.0) == expected


@pytest.mark.parametrize(
    "deg, expected",
    [(90, "vertical"), (-90, "vertical"), (70, "vertical"), (0, "horizontal"), (180, "horizontal"),
     (-20, "horizontal"), (45, None), (-135, None)],
)
@pytest.mark.parametrize("mirror", [False, True])
def test_phone_orientation_ignores_which_end_is_which(deg, expected, mirror):
    lm = make_hand("phone", mirror=mirror, angle_deg=aim("phone", *PHONE_AXIS, deg, mirror=mirror))
    assert phone_orientation(lm, 30.0) == expected
