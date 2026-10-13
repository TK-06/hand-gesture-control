import math

from gesturectl.hid.pairing import PairingWindow


def test_closed_by_default():
    window = PairingWindow()
    assert not window.is_open(0.0)
    assert window.remaining(0.0) is None


def test_first_setup_stays_open_until_a_phone_pairs():
    window = PairingWindow()
    window.open(0.0)  # no duration: until the first phone
    assert window.is_open(10_000.0) and window.remaining(5.0) == math.inf
    assert window.update(10.0, bonded_count=0, bonded_before=0) is False
    assert window.update(12.0, bonded_count=1, bonded_before=0) is True
    assert not window.is_open(12.0)


def test_pair_command_window_times_out():
    window = PairingWindow()
    window.open(100.0, 120.0)
    assert window.is_open(219.0) and round(window.remaining(200.0)) == 20
    assert window.update(221.0, bonded_count=1, bonded_before=1) is True
    assert not window.is_open(221.0)


def test_pair_command_window_closes_when_a_new_phone_pairs():
    window = PairingWindow()
    window.open(0.0, 120.0)
    assert window.update(30.0, bonded_count=1, bonded_before=1) is False  # same phones
    assert window.update(32.0, bonded_count=2, bonded_before=1) is True  # a new one


def test_update_when_closed_does_nothing():
    assert PairingWindow().update(5.0, bonded_count=3, bonded_before=0) is False
