"""When the remote accepts a *new* phone. Bonded phones always reconnect; pairing a new one
is only allowed while the window is open, so nobody in the next car can pair with it.

- No phone paired yet (first setup): open until the first phone pairs.
- ``pair`` command: open for ``duration_s``, or until a new phone pairs.
"""

from __future__ import annotations

import math


class PairingWindow:
    def __init__(self) -> None:
        self._until: float | None = None  # None = closed, math.inf = until a phone pairs

    def open(self, now: float, duration_s: float | None = None) -> None:
        self._until = math.inf if duration_s is None else now + duration_s

    def close(self) -> None:
        self._until = None

    def is_open(self, now: float) -> bool:
        return self._until is not None and now < self._until

    def remaining(self, now: float) -> float | None:
        """Seconds left; math.inf until the first phone pairs; None when closed."""
        if not self.is_open(now):
            return None
        return self._until - now

    def update(self, now: float, bonded_count: int, bonded_before: int) -> bool:
        """Close after a new phone bonded or the time ran out. True if it just closed."""
        if self._until is None:
            return False
        if bonded_count > bonded_before or now >= self._until:
            self.close()
            return True
        return False
