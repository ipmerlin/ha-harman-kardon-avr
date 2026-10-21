"""State-machine and real local TCP tests; no receiver is contacted."""

import asyncio
import importlib
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
# Load the pure runtime modules without importing the HA entry point.
package = ModuleType("avr_offline")
package.__path__ = [str(ROOT / "custom_components/hk_avr")]
sys.modules.setdefault("avr_offline", package)
api = importlib.import_module("avr_offline.api")
controller = importlib.import_module("avr_offline.controller")


class ProtocolTests(unittest.TestCase):
    def test_extended_remote_wire_names(self):
        for command in (
            "play", "pause", "next", "previous", "forward", "reverse", "sleep",
            "up", "down", "left", "right", "ok", "back", "home", "info", "options",
        ):
            with self.subTest(command=command):
                body = api.build_request(command, "", 10025).split(b"\r\n\r\n", 1)[1]
                root = ElementTree.fromstring(body)
                self.assertEqual(root.findtext("avr/common/control/name"), command)
                self.assertEqual(root.findtext("avr/common/control/para"), "")

    def test_utf8_content_length_and_xml_escaping(self):
        request = api.build_request("source-selection", "ТВ & <input>", 10025)
        header, body = request.split(b"\r\n\r\n", 1)
        self.assertIn(f"Content-Length: {len(body)}".encode(), header)
        self.assertEqual(ElementTree.fromstring(body).findtext("avr/common/control/para"),
                         "ТВ & <input>")
        self.assertTrue(header.startswith(b"POST AVR HTTP/1.1\r\n"))

    def test_unknown_commands_rejected(self):
        with self.assertRaises(ValueError):
            api.build_request("factory-reset", "", 10025)


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = AsyncMock(spec=api.AvrClient)
        self.client.async_probe.return_value = True
        self.wake = AsyncMock()
        self.avr = controller.AvrController(self.client, self.wake, 1, .001)

    async def test_reachable_uses_tcp_without_ir(self):
        await self.avr.async_turn_on()
        self.wake.assert_not_awaited()
        self.client.async_send.assert_awaited_once_with("power-on", "")
        self.assertEqual(self.avr.snapshot.power, "on")

    async def test_sleeping_wakes_once_and_waits_for_network(self):
        self.client.async_probe.side_effect = [False, False, False, True]
        await self.avr.async_turn_on()
        self.wake.assert_awaited_once()
        self.client.async_send.assert_not_awaited()
        self.assertTrue(self.avr.snapshot.reachable)
        self.assertEqual(self.avr.snapshot.last_transport, "broadlink")

    async def test_wake_timeout_is_not_success(self):
        self.client.async_probe.return_value = False
        self.avr.wake_timeout = .03
        with self.assertRaises(controller.WakeTimeoutError):
            await self.avr.async_turn_on()
        self.wake.assert_awaited_once()
        self.assertFalse(self.avr.snapshot.reachable)
        self.assertIsNone(self.avr.snapshot.power)

    async def test_unreachable_without_remote_needs_wake(self):
        self.client.async_probe.return_value = False
        avr = controller.AvrController(self.client)
        with self.assertRaises(controller.WakeRequiredError):
            await avr.async_turn_on()
        self.client.async_send.assert_not_awaited()

    async def test_failed_ir_is_not_retried(self):
        self.client.async_probe.return_value = False
        self.wake.side_effect = RuntimeError("Broadlink offline")
        with self.assertRaises(RuntimeError):
            await self.avr.async_turn_on()
        self.wake.assert_awaited_once()
        self.client.async_send.assert_not_awaited()
        self.assertIsNone(self.avr.snapshot.power)

    async def test_failed_tcp_is_never_retried_or_replaced_with_ir(self):
        self.client.async_send.side_effect = api.AvrConnectionError
        with self.assertRaises(api.AvrConnectionError):
            await self.avr.async_turn_on()
        self.client.async_send.assert_awaited_once()
        self.wake.assert_not_awaited()
        self.assertIsNone(self.avr.snapshot.power)

    async def test_refresh_measures_connectivity_not_power(self):
        snapshot = await self.avr.async_refresh()
        self.assertTrue(snapshot.reachable)
        self.assertIsNone(snapshot.power)
        self.client.async_send.assert_not_awaited()

    async def test_connection_loss_clears_assumed_on_and_source(self):
        await self.avr.async_turn_on()
        await self.avr.async_command("source-selection", "TV")
        self.client.async_probe.return_value = False
        snapshot = await self.avr.async_refresh()
        self.assertIsNone(snapshot.power)
        self.assertIsNone(snapshot.source)

    async def test_sent_off_is_retained_when_network_drops(self):
        await self.avr.async_command("power-off")
        self.client.async_probe.return_value = False
        snapshot = await self.avr.async_refresh()
        self.assertEqual(snapshot.power, "off")
        self.assertFalse(snapshot.reachable)

    async def test_reconnection_clears_stale_power_off_assumption(self):
        await self.avr.async_command("power-off")
        self.client.async_probe.return_value = False
        await self.avr.async_refresh()
        self.client.async_probe.return_value = True
        snapshot = await self.avr.async_refresh()
        self.assertTrue(snapshot.reachable)
        self.assertIsNone(snapshot.power)

    async def test_unknown_source_is_not_sent(self):
        with self.assertRaises(ValueError):
            await self.avr.async_command("source-selection", "Nonexistent")
        self.client.async_send.assert_not_awaited()

    async def test_mute_is_always_a_single_explicit_toggle(self):
        await self.avr.async_command("mute-toggle")
        self.client.async_send.assert_awaited_once_with("mute-toggle", "")

    async def test_cancel_wake_does_not_mark_receiver_on(self):
        self.client.async_probe.return_value = False
        task = asyncio.create_task(self.avr.async_turn_on())
        await asyncio.sleep(.005)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(self.avr.snapshot.power)
        self.wake.assert_awaited_once()

    async def test_concurrent_turn_on_does_not_repeat_ir(self):
        sleeping = True

        async def probe():
            return not sleeping

        async def wake():
            nonlocal sleeping
            await asyncio.sleep(.001)
            sleeping = False

        self.client.async_probe.side_effect = probe
        self.wake.side_effect = wake
        await asyncio.gather(self.avr.async_turn_on(), self.avr.async_turn_on())
        self.wake.assert_awaited_once()
        self.client.async_send.assert_awaited_once_with("power-on", "")

    async def test_network_power_on_does_not_fall_back_to_ir(self):
        self.client.async_send.side_effect = api.AvrConnectionError
        with self.assertRaises(api.AvrConnectionError):
            await self.avr.async_network_turn_on()
        self.wake.assert_not_awaited()
        self.client.async_send.assert_awaited_once_with("power-on", "")

    async def test_network_sequence_preserves_order(self):
        await self.avr.async_sequence(["up", "ok", "back"], 0)
        self.assertEqual([call.args for call in self.client.async_send.await_args_list],
                         [("up", ""), ("ok", ""), ("back", "")])
        self.wake.assert_not_awaited()

    async def test_invalid_sequence_does_not_send_valid_prefix(self):
        for commands in (["up", "factory-reset"], [], ["up"] * 21, ["power-on"]):
            with self.assertRaises(ValueError):
                await self.avr.async_sequence(commands, 0)
        self.client.async_send.assert_not_awaited()

    async def test_sequence_stops_after_uncertain_delivery(self):
        self.client.async_send.side_effect = [None, api.AvrConnectionError, None]
        with self.assertRaises(api.AvrConnectionError):
            await self.avr.async_sequence(["up", "ok", "back"], 0)
        self.assertEqual([call.args for call in self.client.async_send.await_args_list],
                         [("up", ""), ("ok", "")])
        self.wake.assert_not_awaited()
        self.assertFalse(self.avr.snapshot.reachable)

    async def test_concurrent_sequences_are_not_interleaved(self):
        await asyncio.gather(self.avr.async_sequence(["up", "ok"], .001),
                             self.avr.async_sequence(["down", "back"], .001))
        self.assertEqual([call.args[0] for call in self.client.async_send.await_args_list],
                         ["up", "ok", "down", "back"])

    async def test_sleep_does_not_pretend_receiver_is_off(self):
        await self.avr.async_network_turn_on()
        await self.avr.async_command("sleep")
        self.assertEqual(self.avr.snapshot.power, "on")


class TcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_arrives_at_local_server(self):
        received = asyncio.get_running_loop().create_future()

        async def handler(reader, writer):
            header = await reader.readuntil(b"\r\n\r\n")
            size = int(next(line.split(b":", 1)[1] for line in header.split(b"\r\n")
                            if line.startswith(b"Content-Length:")))
            body = await reader.readexactly(size)
            received.set_result(header + body)
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        async with server:
            port = server.sockets[0].getsockname()[1]
            client = api.AvrClient("127.0.0.1", port, .5)
            await client.async_send("volume-up")
            request = await asyncio.wait_for(received, .5)
            self.assertIn(b"<name>volume-up</name>", request)

    async def test_probe_sends_no_payload(self):
        received = asyncio.get_running_loop().create_future()

        async def handler(reader, writer):
            received.set_result(await reader.read())
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        async with server:
            client = api.AvrClient("127.0.0.1", server.sockets[0].getsockname()[1], .5)
            self.assertTrue(await client.async_probe())
            self.assertEqual(await asyncio.wait_for(received, .5), b"")

    async def test_closed_port_returns_false_and_command_raises(self):
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()
        client = api.AvrClient("127.0.0.1", port, .1)
        self.assertFalse(await client.async_probe())
        with self.assertRaises(api.AvrConnectionError):
            await client.async_send("volume-up")

    async def test_probe_timeout_is_bounded(self):
        async def stall(*args):
            await asyncio.sleep(60)

        with patch.object(api.asyncio, "open_connection", side_effect=stall):
            self.assertFalse(await api.AvrClient("unused", timeout=.01).async_probe())

    async def test_write_failure_does_not_reconnect(self):
        writer = AsyncMock()
        writer.write = unittest.mock.Mock()
        writer.close = unittest.mock.Mock()
        writer.drain.side_effect = BrokenPipeError
        with patch.object(api.asyncio, "open_connection", new_callable=AsyncMock) as connect:
            connect.return_value = (AsyncMock(), writer)
            with self.assertRaises(api.AvrConnectionError):
                await api.AvrClient("unused").async_send("mute-toggle")
            connect.assert_awaited_once()
            writer.close.assert_called_once()
