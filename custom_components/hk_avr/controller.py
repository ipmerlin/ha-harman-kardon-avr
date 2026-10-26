"""Transport-independent command/wake state machine, also tested offline."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from .api import AvrClient, AvrConnectionError
from .const import REMOTE_COMMANDS, SOURCES


class WakeRequiredError(Exception):
    """Ethernet is asleep and no IR wake action is configured."""


class WakeTimeoutError(Exception):
    """IR was sent, but TCP did not return within the deadline."""


@dataclass(frozen=True)
class Snapshot:
    """Only TCP reachability is measured; other state is optimistic."""

    reachable: bool = False
    power: str | None = None
    source: str | None = None
    last_transport: str | None = None


class AvrController:
    """Serialize user commands and send at most one IR wake per request."""

    def __init__(
        self, client: AvrClient, wake: Callable[[], Awaitable[None]] | None = None,
        wake_timeout: float = 45, poll_interval: float = 1,
    ) -> None:
        self.client = client
        self.wake = wake
        self.wake_timeout = wake_timeout
        self.poll_interval = poll_interval
        self.snapshot = Snapshot()
        self._lock = asyncio.Lock()

    def _offline(self) -> None:
        # Unreachable is not proof of standby or of a successful shutdown.
        self.snapshot = replace(
            self.snapshot, reachable=False, source=None,
            power="off" if self.snapshot.power == "off" else None,
        )

    async def async_refresh(self) -> Snapshot:
        async with self._lock:
            if await self.client.async_probe():
                self.snapshot = replace(
                    self.snapshot, reachable=True,
                    power=self.snapshot.power if self.snapshot.reachable else None,
                )
            else:
                self._offline()
            return self.snapshot

    async def _send(self, command: str, parameter: str = "") -> None:
        try:
            await self.client.async_send(command, parameter)
        except AvrConnectionError:
            self._offline()
            raise
        self.snapshot = replace(self.snapshot, reachable=True, last_transport="ethernet")

    async def async_turn_on(self) -> None:
        async with self._lock:
            if await self.client.async_probe():
                await self._send("power-on")
            else:
                self._offline()
                if self.wake is None:
                    raise WakeRequiredError
                # No retries: learn a discrete POWER ON, never a power toggle.
                await self.wake()
                self.snapshot = replace(self.snapshot, last_transport="infrared")
                try:
                    async with asyncio.timeout(self.wake_timeout):
                        while not await self.client.async_probe():
                            await asyncio.sleep(self.poll_interval)
                except TimeoutError as err:
                    raise WakeTimeoutError from err
                self.snapshot = replace(self.snapshot, reachable=True)
            self.snapshot = replace(self.snapshot, power="on")

    async def async_command(self, command: str, parameter: str = "") -> None:
        if command == "power-on":
            raise ValueError("Use async_turn_on for wake-aware power on")
        if command == "source-selection" and parameter not in SOURCES:
            raise ValueError("Unknown input source")
        async with self._lock:
            await self._send(command, parameter)
            if command == "power-off":
                self.snapshot = replace(self.snapshot, power="off", source=None)
            elif command == "source-selection":
                self.snapshot = replace(self.snapshot, source=parameter)

    async def async_network_turn_on(self) -> None:
        """Explicit Ethernet-only power on, without IR fallback."""
        async with self._lock:
            await self._send("power-on")
            self.snapshot = replace(self.snapshot, power="on")

    async def async_sequence(self, commands: list[str], delay: float = .4) -> None:
        """Validate the entire sequence, serialize it and stop on the first failure."""
        if (not 1 <= len(commands) <= 20 or not 0 <= delay <= 5
                or any(command not in REMOTE_COMMANDS.values() for command in commands)):
            raise ValueError("Invalid network remote sequence")
        async with self._lock:
            for index, command in enumerate(commands):
                if index:
                    await asyncio.sleep(delay)
                await self._send(command)
