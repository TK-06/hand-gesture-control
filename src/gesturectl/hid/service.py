"""The Bluetooth remote service: a BLE HID "media remote" (HID over GATT) that the phone
pairs with once and then reconnects to automatically. It listens on 127.0.0.1 for
actions from the gesture program and presses the matching media key on the phone.

Services offered to the phone:
- HID (0x1812): HID Information, Report Map, Control Point, Protocol Mode, and the
  media-keys Report (+ Report Reference descriptor). Reading them requires an encrypted
  link, which makes the phone pair and bond on first use.
- Battery (0x180F) and Device Information (0x180A), which phones expect from HID devices.
"""

from __future__ import annotations

import asyncio
import logging
import math
import signal
import time

from gesturectl.config import AppConfig, HidConfig
from gesturectl.hid.keys import (
    KEYBOARD_RELEASE,
    KEYBOARD_REPORT_ID,
    MEDIA_RELEASE,
    MEDIA_REPORT_ID,
    media_report,
    report_map,
)
from gesturectl.hid.pairing import PairingWindow
from gesturectl.hid.protocol import serve

log = logging.getLogger("gesturectl.hid")

HID_INFORMATION = bytes([0x11, 0x01, 0x00, 0x02])  # HID 1.11, no country, normally connectable
PNP_ID = bytes([0x02, 0x6B, 0x1D, 0x46, 0x02, 0x00, 0x01])  # USB vendor 0x1D6B (Linux Foundation), product 0x0246, v1.0
REPORT_FLAGS = ["encrypt-read", "notify", "encrypt-notify"]
REPORT_INPUT = 1  # Report Reference "report type": input
APPEARANCE = {"media": 0x03C0, "media+keyboard": 0x03C1}  # Generic HID / Keyboard
WATCH_EVERY_S = 2.0
# A bonded phone that is connected but hasn't subscribed to the key report within this
# time (e.g. it stayed connected while the service restarted) is disconnected on
# purpose: it then reconnects by itself and subscribes afresh.
SUBSCRIBE_GRACE_S = 6.0
MIN_HEAL_INTERVAL_S = 20.0


class HidRemote:
    def __init__(self, bus, cfg: HidConfig):
        from gesturectl.hid import bluez as bz

        self.bz = bz
        self.bus = bus
        self.cfg = cfg
        self.adapter = bz.Adapter(bus, cfg.adapter)
        self.window = PairingWindow()
        self._bonded_at_open = 0
        self._connected: dict[str, bool] = {}
        self._connected_since: dict[str, float] = {}
        self._last_heal = -math.inf
        self._lock = asyncio.Lock()

        u = bz.uuid16
        hid = bz.GattService(0, u("1812"))
        bz.GattCharacteristic(hid, u("2a4a"), ["encrypt-read"], HID_INFORMATION, name="HID Information")
        bz.GattCharacteristic(hid, u("2a4b"), ["encrypt-read"], report_map(cfg.profile), name="Report Map")
        bz.GattCharacteristic(hid, u("2a4c"), ["write-without-response"], b"\x00", name="HID Control Point")
        bz.GattCharacteristic(hid, u("2a4e"), ["read", "write-without-response"], b"\x01", name="Protocol Mode")
        self.media = bz.GattCharacteristic(hid, u("2a4d"), REPORT_FLAGS, MEDIA_RELEASE, name="media keys")
        bz.GattDescriptor(self.media, u("2908"), ["read"], bytes([MEDIA_REPORT_ID, REPORT_INPUT]))
        if cfg.profile == "media+keyboard":
            keyboard = bz.GattCharacteristic(hid, u("2a4d"), REPORT_FLAGS, KEYBOARD_RELEASE, name="keyboard")
            bz.GattDescriptor(keyboard, u("2908"), ["read"], bytes([KEYBOARD_REPORT_ID, REPORT_INPUT]))

        battery = bz.GattService(1, u("180f"))
        bz.GattCharacteristic(battery, u("2a19"), ["read", "notify"], bytes([100]), name="Battery Level")

        info = bz.GattService(2, u("180a"))
        bz.GattCharacteristic(info, u("2a29"), ["read"], b"gesturectl", name="Manufacturer Name")
        bz.GattCharacteristic(info, u("2a24"), ["read"], cfg.name.encode(), name="Model Number")
        bz.GattCharacteristic(info, u("2a50"), ["read"], PNP_ID, name="PnP ID")

        self.services = [hid, battery, info]
        self.advertisement = bz.Advertisement(cfg.name, [u("1812")], APPEARANCE[cfg.profile])
        self.agent = bz.Agent(lambda: self.window.is_open(time.monotonic()))

    def _gatt_objects(self):
        for service in self.services:
            yield service
            for characteristic in service.characteristics:
                yield characteristic
                yield from characteristic.descriptors

    # ------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        bz = self.bz
        for obj in [*self._gatt_objects(), self.advertisement, self.agent]:
            self.bus.export(obj.path, obj)

        await self.adapter.set("Powered", "b", True)
        await self.adapter.set("Alias", "s", self.cfg.name)

        agents = await bz.interface(self.bus, "/org/bluez", "org.bluez.AgentManager1")
        await agents.call_register_agent(bz.AGENT_PATH, "NoInputNoOutput")
        await agents.call_request_default_agent(bz.AGENT_PATH)

        gatt = await bz.interface(self.bus, self.adapter.path, "org.bluez.GattManager1")
        await gatt.call_register_application(bz.GATT_PATH, {})

        adverts = await bz.interface(self.bus, self.adapter.path, "org.bluez.LEAdvertisingManager1")
        await adverts.call_register_advertisement(bz.ADVERTISEMENT_PATH, {})

        bonded = [d for d in await self.adapter.devices() if d[2]]
        if bonded:
            log.info("paired phones: %s (pairing closed; run 'pair' to add another)", ", ".join(d[1] for d in bonded))
            await self._set_pairable(False)
        else:
            log.info("no phone paired yet: pairing is open until one pairs")
            await self._open_window(None, bonded_now=0)
        log.info("advertising as %r (profile %s)", self.cfg.name, self.cfg.profile)

    async def stop(self) -> None:
        bz = self.bz
        for path, iface, call in (
            (self.adapter.path, "org.bluez.LEAdvertisingManager1", "call_unregister_advertisement"),
            (self.adapter.path, "org.bluez.GattManager1", "call_unregister_application"),
            ("/org/bluez", "org.bluez.AgentManager1", "call_unregister_agent"),
        ):
            target = {"call_unregister_advertisement": bz.ADVERTISEMENT_PATH,
                      "call_unregister_application": bz.GATT_PATH,
                      "call_unregister_agent": bz.AGENT_PATH}[call]
            try:
                proxy = await bz.interface(self.bus, path, iface)
                await getattr(proxy, call)(target)
            except Exception as exc:  # shutting down anyway
                log.debug("%s failed: %s", call, exc)

    async def watch(self) -> None:
        """Every few seconds: keep Bluetooth up and advertising, close the pairing window
        when due, log (dis)connections, and repair a connected-but-not-subscribed phone."""
        while True:
            await asyncio.sleep(WATCH_EVERY_S)
            try:
                await self._keep_alive()
                await self._check_devices()
            except Exception as exc:  # never let the watcher die
                log.warning("Bluetooth check failed: %s", exc)

    async def _keep_alive(self) -> None:
        if not await self.adapter.get("Powered"):
            log.warning("Bluetooth was powered off: turning it back on")
            await self.adapter.set("Powered", "b", True)
        if self.advertisement.released:
            adverts = await self.bz.interface(self.bus, self.adapter.path, "org.bluez.LEAdvertisingManager1")
            await adverts.call_register_advertisement(self.bz.ADVERTISEMENT_PATH, {})
            self.advertisement.released = False
            log.info("advertising again")

    async def _check_devices(self) -> None:
        now = time.monotonic()
        devices = await self.adapter.devices()
        bonded = sum(1 for d in devices if d[2])
        if self.window.update(now, bonded, self._bonded_at_open):
            await self._set_pairable(False)
            log.info("pairing window closed")
        for path, name, paired, connected in devices:
            if self._connected.get(path) != connected:
                if paired or connected:
                    log.info("%s %s", name, "connected" if connected else "disconnected")
                self._connected_since[path] = now
            self._connected[path] = connected
            stuck = (
                paired
                and connected
                and not self.media.notifying
                and now - self._connected_since.get(path, now) >= SUBSCRIBE_GRACE_S
                and now - self._last_heal >= MIN_HEAL_INTERVAL_S
            )
            if stuck:
                self._last_heal = now
                log.warning("%s is connected but not listening for keys: disconnecting it so it reconnects", name)
                await self.adapter.disconnect(path)

    # ------------------------------------------------------------- commands

    async def press(self, action: str) -> str:
        report = media_report(action)
        if report is None:
            return f"error: no media key for {action} (phones only take call controls over hands-free)"
        if not any(paired and connected for _, _, paired, connected in await self.adapter.devices()):
            return "error: phone not connected"
        if not self.media.notifying:
            return "error: phone connected but not listening for keys yet (it reconnects by itself within ~20 s)"
        await self._lock.acquire()  # one key at a time; released after key-up
        self.media.notify(report)
        asyncio.get_running_loop().call_later(self.cfg.key_press_s, self._release, action)
        return "ok"

    def _release(self, action: str) -> None:
        try:
            self.media.notify(MEDIA_RELEASE)
            log.info("pressed %s", action)
        finally:
            self._lock.release()

    async def status(self) -> str:
        devices = await self.adapter.devices()
        connected = [d[1] for d in devices if d[3]] or ["none"]
        paired = [d[1] for d in devices if d[2]] or ["none"]
        remaining = self.window.remaining(time.monotonic())
        if remaining is None:
            pairing = "closed"
        elif remaining == math.inf:
            pairing = "open until a phone pairs"
        else:
            pairing = f"open for {remaining:.0f} more s"
        ready = "yes" if self.media.notifying and connected != ["none"] else "no"
        return f"connected: {', '.join(connected)}; paired: {', '.join(paired)}; keys ready: {ready}; pairing {pairing}"

    async def open_pairing(self) -> str:
        bonded = sum(1 for d in await self.adapter.devices() if d[2])
        await self._open_window(self.cfg.pairing_window_s, bonded_now=bonded)
        return (
            f"pairing open for {self.cfg.pairing_window_s:.0f} s: on the iPhone open "
            f"Settings > Bluetooth and tap '{self.cfg.name}'"
        )

    async def _open_window(self, duration_s: float | None, bonded_now: int) -> None:
        self.window.open(time.monotonic(), duration_s)
        self._bonded_at_open = bonded_now
        await self._set_pairable(True)

    async def _set_pairable(self, on: bool) -> None:
        await self.adapter.set("PairableTimeout", "u", 0)
        await self.adapter.set("Pairable", "b", on)


async def run(cfg: AppConfig) -> None:
    from gesturectl.hid import bluez

    bus = await bluez.connect_system_bus()
    remote = HidRemote(bus, cfg.hid)
    await remote.start()
    server = await serve(cfg.hid.host, cfg.hid.port, remote)
    log.info("listening for actions on %s:%d", cfg.hid.host, cfg.hid.port)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    watcher = asyncio.create_task(remote.watch())
    try:
        await stop.wait()
    finally:
        log.info("stopping")
        watcher.cancel()
        server.close()
        await server.wait_closed()
        await remote.stop()
        bus.disconnect()
