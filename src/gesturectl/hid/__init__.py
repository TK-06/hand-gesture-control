"""Bluetooth LE media remote: makes the Pi a HID consumer-control device ("media keys")
paired to the phone. Run the service with ``python -m gesturectl.hid``.

- keys.py      HID report map and the report bytes for each action (pure)
- protocol.py  the local TCP line protocol between the gesture program and the service
- bluez.py     BlueZ D-Bus objects: GATT HID service, advertisement, pairing agent (Pi only)
- service.py   wires it all together
"""
