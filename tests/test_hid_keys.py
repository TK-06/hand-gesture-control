import pytest

from gesturectl.config import ACTIONS
from gesturectl.hid.keys import MEDIA_KEYS, MEDIA_RELEASE, NO_KEY, media_report, report_map


def test_every_action_is_either_a_media_key_or_explicitly_keyless():
    keys = {name for name, _ in MEDIA_KEYS}
    for action in ACTIONS:
        assert (action in keys) != (action in NO_KEY), action


@pytest.mark.parametrize("action", [name for name, _ in MEDIA_KEYS])
def test_each_media_key_sets_exactly_one_bit(action):
    report = media_report(action)
    assert len(report) == 2
    assert bin(int.from_bytes(report, "little")).count("1") == 1


def test_media_keys_have_distinct_bits_and_release_is_all_zero():
    reports = {media_report(name) for name, _ in MEDIA_KEYS}
    assert len(reports) == len(MEDIA_KEYS)
    assert MEDIA_RELEASE == b"\x00\x00"


def test_call_actions_have_no_media_key():
    assert media_report("answer_call") is None
    assert media_report("end_call") is None


def test_standard_usage_codes():
    usages = dict(MEDIA_KEYS)
    assert usages["volume_up"] == 0xE9
    assert usages["volume_down"] == 0xEA
    assert usages["play_pause"] == 0xCD
    assert usages["next"] == 0xB5
    assert usages["previous"] == 0xB6


def test_media_report_map_describes_a_16_bit_consumer_report():
    rmap = report_map("media")
    assert rmap[:4] == bytes([0x05, 0x0C, 0x09, 0x01])  # Consumer page, Consumer Control
    assert bytes([0x85, 0x01]) in rmap  # report ID 1
    assert rmap.count(0xA1) == 1 and rmap.endswith(bytes([0xC0]))
    # one bit per key plus padding = 16 bits
    i = rmap.index(bytes([0x75, 0x01, 0x95]))
    key_bits = rmap[i + 3]
    j = rmap.index(bytes([0x95, 0x01, 0x81, 0x01]))
    padding_bits = rmap[j - 1]
    assert key_bits == len(MEDIA_KEYS) and key_bits + padding_bits == 16


def test_keyboard_fallback_adds_a_second_report():
    rmap = report_map("media+keyboard")
    assert rmap.startswith(report_map("media"))
    assert bytes([0x85, 0x02]) in rmap
    assert bytes([0x05, 0x01, 0x09, 0x06]) in rmap  # Generic Desktop, Keyboard


def test_unknown_profile_is_an_error():
    with pytest.raises(ValueError):
        report_map("joystick")
