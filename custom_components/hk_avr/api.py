"""Small asynchronous client for the AVR's HTTP-like TCP protocol.

The receiver does not supply reliable state/command acknowledgements through
this interface. A successful write is delivery to TCP, not confirmed execution.
Commands are deliberately never retried after a potentially successful write.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from xml.etree.ElementTree import Element, SubElement, tostring

COMMANDS = frozenset({
    "power-on", "power-off", "volume-up", "volume-down",
    "mute-toggle", "source-selection",
})


class AvrConnectionError(Exception):
    """The receiver cannot be contacted; execution may be uncertain."""


def build_request(command: str, parameter: str, port: int) -> bytes:
    """Encode the AVR Remote protocol, with a byte-correct content length."""
    if command not in COMMANDS:
        raise ValueError("Unsupported AVR command")
    root = Element("harman")
    control = SubElement(SubElement(SubElement(root, "avr"), "common"), "control")
    for key, value in (("name", command), ("zone", "Main Zone"), ("para", parameter)):
        SubElement(control, key).text = value
    body = tostring(root, encoding="utf-8", xml_declaration=True,
                    short_empty_elements=False)
    header = (
        f"POST AVR HTTP/1.1\r\nHost: :{port}\r\n"
        "User-Agent: Harman Kardon AVR Remote Controller /2.0\r\n"
        f"Content-Length: {len(body)}\r\n\r\n"
    ).encode("ascii")
    return header + body


async def _close(writer: asyncio.StreamWriter) -> None:
    writer.close()
    with suppress(OSError, TimeoutError):
        async with asyncio.timeout(1):
            await writer.wait_closed()


class AvrClient:
    """Use bounded, short-lived connections without occupying the HA loop."""

    def __init__(self, host: str, port: int = 10025, timeout: float = 3) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    async def async_probe(self) -> bool:
        """Check TCP reachability only; never send a power/heartbeat command."""
        try:
            async with asyncio.timeout(self.timeout):
                _, writer = await asyncio.open_connection(self.host, self.port)
        except (OSError, TimeoutError):
            return False
        await _close(writer)
        return True

    async def async_send(self, command: str, parameter: str = "") -> None:
        request = build_request(command, parameter, self.port)
        writer = None
        try:
            async with asyncio.timeout(self.timeout):
                _, writer = await asyncio.open_connection(self.host, self.port)
                writer.write(request)
                await writer.drain()
        except (OSError, TimeoutError) as err:
            raise AvrConnectionError(
                "AVR TCP command failed; it has not been retried"
            ) from err
        finally:
            if writer is not None:
                await _close(writer)
