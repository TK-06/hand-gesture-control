"""Where recognized actions go: ``send(action)`` on a backend chosen in the config.

- ``print``   logs the action (laptop, tests)
- ``bt_hid``  sends it to the Bluetooth remote service (``python -m gesturectl.hid``),
              which presses the matching media key on the paired phone
"""

from __future__ import annotations

import logging
import time
from typing import Protocol

from gesturectl.config import AppConfig
from gesturectl.hid.protocol import request

log = logging.getLogger(__name__)


class ActionBackend(Protocol):
    def send(self, action: str) -> None: ...

    def close(self) -> None: ...


class PrintBackend:
    def send(self, action: str) -> None:
        log.info("(print backend) %s", action)

    def close(self) -> None:
        pass


class BtHidBackend:
    """Hands actions to the Bluetooth remote service. Never raises: a missing service or
    phone is logged (at most every ``warn_every_s``) and the action is dropped, because a
    media key pressed late is worse than one not pressed at all."""

    def __init__(self, host: str, port: int, timeout: float = 0.5, warn_every_s: float = 30.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.warn_every_s = warn_every_s
        self._last_warn = -float("inf")

    def send(self, action: str) -> None:
        try:
            reply = request(action, self.host, self.port, self.timeout)
        except OSError as exc:
            self._warn(f"Bluetooth remote service not reachable ({exc}); is gesturectl-hid running?")
            return
        if reply == "ok":
            log.info("sent %s to phone", action)
        else:
            self._warn(f"{action}: {reply}")

    def close(self) -> None:
        pass

    def _warn(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_warn >= self.warn_every_s:
            log.warning(message)
            self._last_warn = now
        else:
            log.debug(message)


def make_backend(cfg: AppConfig) -> ActionBackend:
    if cfg.actions.backend == "bt_hid":
        return BtHidBackend(cfg.hid.host, cfg.hid.port)
    return PrintBackend()
