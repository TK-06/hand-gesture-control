"""The local line protocol between the gesture program and the Bluetooth remote service.

One command per line over TCP on 127.0.0.1, one reply line back:

    volume_up        -> "ok" | "error: phone not connected" | "error: no media key for ..."
    status           -> e.g. "connected to iPhone; pairing closed"
    pair             -> opens the pairing window for a new phone

TCP on localhost (not a Unix socket) so the same code runs and is tested on Windows.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Protocol

from gesturectl.config import ACTIONS

log = logging.getLogger(__name__)


class Remote(Protocol):
    async def press(self, action: str) -> str: ...

    async def status(self) -> str: ...

    async def open_pairing(self) -> str: ...


async def handle_command(line: str, remote: Remote) -> str:
    command = line.strip()
    if command == "status":
        return await remote.status()
    if command == "pair":
        return await remote.open_pairing()
    if command in ACTIONS:
        return await remote.press(command)
    return f"error: unknown command {command!r}"


async def serve(host: str, port: int, remote: Remote) -> asyncio.Server:
    """Accept commands from local clients until the returned server is closed."""

    async def client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while line := await reader.readline():
                reply = await handle_command(line.decode("utf-8", "replace"), remote)
                writer.write((reply + "\n").encode())
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    return await asyncio.start_server(client, host, port)


def request(command: str, host: str, port: int, timeout: float = 1.0) -> str:
    """Send one command and return the reply line. Raises OSError if the service isn't
    running or doesn't answer within ``timeout``."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall((command + "\n").encode())
        reply = b""
        while not reply.endswith(b"\n"):
            chunk = sock.recv(256)
            if not chunk:
                break
            reply += chunk
    return reply.decode("utf-8", "replace").strip()
