from gesturectl.geometry import Pose
from gesturectl.pose_filter import PoseFilter


def feed(filt, seq, fps=30.0, t0=100.0):
    out = []
    for i, pose in enumerate(seq):
        out.append(filt.update(t0 + i / fps, pose))
    return out


def test_new_pose_needs_to_persist_for_switch_time():
    filt = PoseFilter(switch_s=0.1, grace_s=0.2)
    out = feed(filt, [Pose.OPEN] * 5)
    assert [p for p, _ in out] == [Pose.NONE, Pose.NONE, Pose.NONE, Pose.OPEN, Pose.OPEN]
    assert out[-1][1] == 100.0  # since = when it was first seen


def test_single_frame_flicker_is_ignored():
    filt = PoseFilter(switch_s=0.1, grace_s=0.2)
    out = feed(filt, [Pose.FIST] * 6 + [Pose.OTHER] + [Pose.FIST] * 3)
    assert out[-1][0] is Pose.FIST
    assert {p for p, _ in out[4:]} == {Pose.FIST}


def test_hand_loss_is_bridged_for_the_grace_period():
    filt = PoseFilter(switch_s=0.1, grace_s=0.2)
    out = feed(filt, [Pose.POINT] * 6 + [Pose.NONE] * 5)  # 5 frames = 0.13 s gap
    assert out[-1][0] is Pose.POINT


def test_hand_loss_beyond_grace_becomes_none():
    filt = PoseFilter(switch_s=0.1, grace_s=0.2)
    out = feed(filt, [Pose.POINT] * 6 + [Pose.NONE] * 9)
    assert out[-1][0] is Pose.NONE


def test_alternating_noise_cannot_hold_a_stale_pose_forever():
    filt = PoseFilter(switch_s=0.1, grace_s=0.2)
    out = feed(filt, [Pose.OPEN] * 6 + [Pose.OTHER, Pose.NONE] * 10)
    assert out[-1][0] is not Pose.OPEN
