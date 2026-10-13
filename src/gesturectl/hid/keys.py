"""HID media keys (USB HID "Consumer" usage page, the same keys as on a keyboard's media
row): the report map the phone reads once, and the report bytes for each action.

The media report is a 16-bit bitmap, one bit per key (the layout most BLE media remotes
use). With HID over GATT the report ID is not part of the payload: it lives in the
Report Reference descriptor, so a report is exactly 2 bytes.
"""

from __future__ import annotations

# (action, HID consumer usage), in bit order.
MEDIA_KEYS: tuple[tuple[str, int], ...] = (
    ("next", 0xB5),  # Scan Next Track
    ("previous", 0xB6),  # Scan Previous Track
    ("stop", 0xB7),
    ("play_pause", 0xCD),
    ("mute", 0xE2),
    ("volume_up", 0xE9),
    ("volume_down", 0xEA),
    ("play", 0xB0),
    ("pause", 0xB1),
)
MEDIA_REPORT_ID = 1
KEYBOARD_REPORT_ID = 2
MEDIA_RELEASE = b"\x00\x00"
KEYBOARD_RELEASE = bytes(8)

# Actions the gesture program can send that have no media key. Phones only answer or
# end calls over the hands-free profile, which this remote deliberately doesn't use.
NO_KEY = ("answer_call", "end_call")


def media_report(action: str) -> bytes | None:
    """The 2-byte "key down" report for an action, or None if it isn't a media key."""
    for bit, (name, _usage) in enumerate(MEDIA_KEYS):
        if name == action:
            return (1 << bit).to_bytes(2, "little")
    return None


def report_map(profile: str = "media") -> bytes:
    """The HID report descriptor. ``media``: media keys only. ``media+keyboard``: adds a
    standard (never used) keyboard, for phones that ignore media-only remotes."""
    usages = b"".join(bytes([0x09, usage]) for _, usage in MEDIA_KEYS)
    padding = 16 - len(MEDIA_KEYS)
    media = (
        bytes([0x05, 0x0C, 0x09, 0x01, 0xA1, 0x01])  # Usage Page (Consumer), Usage (Consumer Control), Collection (App)
        + bytes([0x85, MEDIA_REPORT_ID])  # Report ID
        + bytes([0x15, 0x00, 0x25, 0x01])  # Logical Min 0, Logical Max 1
        + bytes([0x75, 0x01, 0x95, len(MEDIA_KEYS)])  # Report Size 1, Report Count n
        + usages
        + bytes([0x81, 0x02])  # Input (Data, Var, Abs)
        + bytes([0x75, padding, 0x95, 0x01, 0x81, 0x01])  # padding to 16 bits: Input (Const)
        + bytes([0xC0])  # End Collection
    )
    if profile == "media":
        return media
    if profile != "media+keyboard":
        raise ValueError(f"unknown HID profile {profile!r}")
    keyboard = (
        bytes([0x05, 0x01, 0x09, 0x06, 0xA1, 0x01])  # Generic Desktop, Keyboard, Collection (App)
        + bytes([0x85, KEYBOARD_REPORT_ID])
        + bytes([0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7, 0x15, 0x00, 0x25, 0x01])  # modifier keys
        + bytes([0x75, 0x01, 0x95, 0x08, 0x81, 0x02])  # 8 modifier bits
        + bytes([0x75, 0x08, 0x95, 0x01, 0x81, 0x01])  # reserved byte
        + bytes([0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x15, 0x00, 0x25, 0x65])  # key codes 0..101
        + bytes([0x75, 0x08, 0x95, 0x06, 0x81, 0x00])  # 6 keys: Input (Data, Array)
        + bytes([0xC0])
    )
    return media + keyboard
