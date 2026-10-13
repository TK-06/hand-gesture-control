import asyncio
import logging
import socket
import threading

import pytest

from gesturectl.actions import BtHidBackend, PrintBackend, make_backend
from gesturectl.config import AppConfig
from gesturectl.hid.protocol import request, serve


class FakeRemote:
    def __init__(self, connected=True):
        self.connected = connected
        self.pressed = []
        self.pairing_opened = 0

    async def press(self, action):
        if not self.connected:
            return "error: phone not connected"
        self.pressed.append(action)
        return "ok"

    async def status(self):
        return "connected" if self.connected else "not connected"

    async def open_pairing(self):
        self.pairing_opened += 1
        return "pairing open for 120 s"


@pytest.fixture
def service():
    """Run the protocol server in a background event loop; yields (remote, port)."""
    remote = FakeRemote()
    loop = asyncio.new_event_loop()
    started = threading.Event()
    box = {}

    async def start():
        box["server"] = await serve("127.0.0.1", 0, remote)
        box["port"] = box["server"].sockets[0].getsockname()[1]
        started.set()

    thread = threading.Thread(target=lambda: (loop.run_until_complete(start()), loop.run_forever()), daemon=True)
    thread.start()
    assert started.wait(5)
    yield remote, box["port"]

    async def stop():
        box["server"].close()
        await box["server"].wait_closed()

    asyncio.run_coroutine_threadsafe(stop(), loop).result(5)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(5)


def test_action_is_pressed(service):
    remote, port = service
    assert request("volume_up", "127.0.0.1", port) == "ok"
    assert remote.pressed == ["volume_up"]


def test_status_and_pair(service):
    remote, port = service
    assert request("status", "127.0.0.1", port) == "connected"
    assert request("pair", "127.0.0.1", port) == "pairing open for 120 s"
    assert remote.pairing_opened == 1


def test_unknown_command_is_an_error(service):
    _, port = service
    assert request("explode", "127.0.0.1", port).startswith("error: unknown command")


def test_several_commands_on_one_connection(service):
    remote, port = service
    with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
        sock.sendall(b"next\nprevious\n")
        reader = sock.makefile()
        replies = reader.readline(), reader.readline()
    assert remote.pressed == ["next", "previous"]
    assert all(r.strip() == "ok" for r in replies)


def test_backend_sends_to_the_service(service, caplog):
    remote, port = service
    caplog.set_level(logging.INFO)
    BtHidBackend("127.0.0.1", port).send("play")
    assert remote.pressed == ["play"]
    assert "sent play to phone" in caplog.text


def test_backend_warns_when_the_phone_is_not_connected(service, caplog):
    remote, port = service
    remote.connected = False
    backend = BtHidBackend("127.0.0.1", port)
    backend.send("play")
    backend.send("pause")  # rate-limited: only the first warning is shown
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "phone not connected" in warnings[0].getMessage()


def test_backend_survives_a_missing_service(caplog):
    with socket.socket() as probe:  # find a port nobody listens on
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    BtHidBackend("127.0.0.1", port, timeout=0.2).send("next")  # must not raise
    assert "not reachable" in caplog.text


def test_backend_comes_from_the_config():
    cfg = AppConfig()
    assert isinstance(make_backend(cfg), PrintBackend)
    cfg.actions.backend = "bt_hid"
    assert isinstance(make_backend(cfg), BtHidBackend)
