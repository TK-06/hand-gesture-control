"""BlueZ D-Bus objects for the remote: GATT services/characteristics/descriptors, the LE
advertisement and the pairing agent, plus small helpers for the adapter. Linux only
(needs BlueZ and the dbus-fast package).

No ``from __future__ import annotations`` in this file: dbus-fast reads the D-Bus type
signatures from the annotations at runtime, and postponed annotations would break that.
"""

import logging
from typing import Callable, Optional

from dbus_fast import BusType, DBusError, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.constants import PropertyAccess
from dbus_fast.service import ServiceInterface, dbus_method, dbus_property

log = logging.getLogger(__name__)

BLUEZ = "org.bluez"
GATT_PATH = "/gesturectl/gatt"  # GetManagedObjects lists only objects below this
ADVERTISEMENT_PATH = "/gesturectl/advertisement0"
AGENT_PATH = "/gesturectl/agent"
REJECTED = "org.bluez.Error.Rejected"


def uuid16(short: str) -> str:
    return f"0000{short.lower()}-0000-1000-8000-00805f9b34fb"


class GattService(ServiceInterface):
    def __init__(self, index: int, uuid: str, primary: bool = True):
        super().__init__("org.bluez.GattService1")
        self.path = f"{GATT_PATH}/service{index}"
        self._uuid = uuid
        self._primary = primary
        self.characteristics: list["GattCharacteristic"] = []

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return self._uuid

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> "b":
        return self._primary


class GattCharacteristic(ServiceInterface):
    def __init__(
        self,
        service: GattService,
        uuid: str,
        flags: list,
        value: bytes = b"",
        on_write: Optional[Callable[[bytes], None]] = None,
        name: str = "",
    ):
        super().__init__("org.bluez.GattCharacteristic1")
        self.path = f"{service.path}/char{len(service.characteristics)}"
        self.service = service
        # not self.name: dbus-fast uses that for the D-Bus interface name
        self.label = name or uuid
        self._uuid = uuid
        self._flags = list(flags)
        self._value = bytes(value)
        self.on_write = on_write
        self.notifying = False
        self.descriptors: list["GattDescriptor"] = []
        service.characteristics.append(self)

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return self._uuid

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return self.service.path

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return self._flags

    @dbus_property(access=PropertyAccess.READ)
    def Value(self) -> "ay":
        return self._value

    @dbus_method()
    def ReadValue(self, options: "a{sv}") -> "ay":
        log.debug("read %s", self.label)
        return self._value

    @dbus_method()
    def WriteValue(self, value: "ay", options: "a{sv}"):
        self._value = bytes(value)
        log.debug("write %s = %s", self.label, self._value.hex())
        if self.on_write is not None:
            self.on_write(self._value)

    @dbus_method()
    def StartNotify(self):
        self.notifying = True
        log.info("phone subscribed to %s", self.label)

    @dbus_method()
    def StopNotify(self):
        self.notifying = False
        log.info("phone unsubscribed from %s", self.label)

    def notify(self, value: bytes) -> None:
        """Send a notification. Always emitted: BlueZ remembers which bonded phones have
        notifications on (they don't re-subscribe after reconnecting) and delivers it."""
        self._value = bytes(value)
        self.emit_properties_changed({"Value": self._value})


class GattDescriptor(ServiceInterface):
    def __init__(self, characteristic: GattCharacteristic, uuid: str, flags: list, value: bytes):
        super().__init__("org.bluez.GattDescriptor1")
        self.path = f"{characteristic.path}/desc{len(characteristic.descriptors)}"
        self.characteristic = characteristic
        self._uuid = uuid
        self._flags = list(flags)
        self._value = bytes(value)
        characteristic.descriptors.append(self)

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return self._uuid

    @dbus_property(access=PropertyAccess.READ)
    def Characteristic(self) -> "o":
        return self.characteristic.path

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return self._flags

    @dbus_method()
    def ReadValue(self, options: "a{sv}") -> "ay":
        return self._value


class Advertisement(ServiceInterface):
    """Connectable LE advertisement: name, HID service, appearance."""

    def __init__(self, local_name: str, service_uuids: list, appearance: int):
        super().__init__("org.bluez.LEAdvertisement1")
        self.path = ADVERTISEMENT_PATH
        self._name = local_name
        self._uuids = list(service_uuids)
        self._appearance = appearance
        self.released = False  # set when BlueZ drops it; the service then re-registers it

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":
        return self._uuids

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":
        return self._name

    @dbus_property(access=PropertyAccess.READ)
    def Appearance(self) -> "q":
        return self._appearance

    @dbus_property(access=PropertyAccess.READ)
    def Discoverable(self) -> "b":
        return True

    @dbus_method()
    def Release(self):
        self.released = True
        log.warning("advertisement released by BlueZ")


class Agent(ServiceInterface):
    """Pairing agent with no display or keyboard ("Just Works": the phone shows a
    Pair/Cancel prompt). New pairings are only accepted while ``allow_pairing()``."""

    def __init__(self, allow_pairing: Callable[[], bool]):
        super().__init__("org.bluez.Agent1")
        self.path = AGENT_PATH
        self._allow = allow_pairing

    def _check(self, device: str, what: str) -> None:
        if not self._allow():
            log.warning("rejected %s from %s: pairing window is closed (run: python -m gesturectl.hid pair)", what, device)
            raise DBusError(REJECTED, "pairing window closed")
        log.info("accepting %s from %s", what, device)

    @dbus_method()
    def Release(self):
        pass

    @dbus_method()
    def RequestPinCode(self, device: "o") -> "s":
        raise DBusError(REJECTED, "no PIN entry")

    @dbus_method()
    def DisplayPinCode(self, device: "o", pincode: "s"):
        pass

    @dbus_method()
    def RequestPasskey(self, device: "o") -> "u":
        raise DBusError(REJECTED, "no passkey entry")

    @dbus_method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
        pass

    @dbus_method()
    def RequestConfirmation(self, device: "o", passkey: "u"):
        self._check(device, "pairing (confirmation)")

    @dbus_method()
    def RequestAuthorization(self, device: "o"):
        self._check(device, "pairing")

    @dbus_method()
    def AuthorizeService(self, device: "o", uuid: "s"):
        pass  # bonded phones may use any service

    @dbus_method()
    def Cancel(self):
        log.info("pairing cancelled")


async def connect_system_bus() -> MessageBus:
    return await MessageBus(bus_type=BusType.SYSTEM).connect()


async def interface(bus: MessageBus, path: str, name: str):
    introspection = await bus.introspect(BLUEZ, path)
    return bus.get_proxy_object(BLUEZ, path, introspection).get_interface(name)


class Adapter:
    """The Bluetooth controller (e.g. /org/bluez/hci0)."""

    def __init__(self, bus: MessageBus, name: str):
        self.bus = bus
        self.path = f"/org/bluez/{name}"

    async def set(self, prop: str, signature: str, value) -> None:
        props = await interface(self.bus, self.path, "org.freedesktop.DBus.Properties")
        await props.call_set("org.bluez.Adapter1", prop, Variant(signature, value))

    async def get(self, prop: str):
        props = await interface(self.bus, self.path, "org.freedesktop.DBus.Properties")
        return (await props.call_get("org.bluez.Adapter1", prop)).value

    async def disconnect(self, device_path: str) -> None:
        device = await interface(self.bus, device_path, "org.bluez.Device1")
        await device.call_disconnect()

    async def devices(self) -> list:
        """[(path, name, paired, connected)] for devices known to this adapter."""
        manager = await interface(self.bus, "/", "org.freedesktop.DBus.ObjectManager")
        objects = await manager.call_get_managed_objects()
        found = []
        for path, interfaces in objects.items():
            device = interfaces.get("org.bluez.Device1")
            if device is None or device["Adapter"].value != self.path:
                continue
            name = device["Alias"].value if "Alias" in device else path
            paired = bool(device["Paired"].value) if "Paired" in device else False
            bonded = bool(device["Bonded"].value) if "Bonded" in device else paired
            connected = bool(device["Connected"].value) if "Connected" in device else False
            found.append((path, name, paired or bonded, connected))
        return found
