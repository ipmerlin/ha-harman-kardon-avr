"""Exercise flow logic with real schema libraries and a minimal HA adapter.

This is explicitly not an actual HA test: tests/ha provides that separate suite.
Run with --voluptuous to test the old schema backend as well.
"""

import importlib
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".test-deps"))
if "--voluptuous" in sys.argv:
    sys.modules["probatio"] = None
    sys.argv.remove("--voluptuous")


class FlowAdapter:
    """Record public flow return values without a running HA instance."""

    def __init_subclass__(cls, **kwargs):
        pass

    def __init__(self):
        self.entries = []
        self.entry = None

    def _async_current_entries(self):
        return self.entries

    def _get_reconfigure_entry(self):
        return self.entry

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_update_reload_and_abort(self, entry, **kwargs):
        return {"type": "update", "entry_id": entry.entry_id, **kwargs}


class EntitySelectorAdapter:
    def __init__(self, config):
        self.config = config

    def __call__(self, value):
        if not isinstance(value, str) or not value.startswith("remote."):
            raise ValueError("Remote entity expected")
        return value


for name in ("homeassistant", "homeassistant.config_entries", "homeassistant.const",
             "homeassistant.helpers", "homeassistant.helpers.selector"):
    sys.modules[name] = ModuleType(name)
sys.modules["homeassistant.config_entries"].ConfigFlow = FlowAdapter
const = sys.modules["homeassistant.const"]
const.CONF_HOST, const.CONF_PORT, const.CONF_NAME = "host", "port", "name"
selectors = sys.modules["homeassistant.helpers.selector"]
selectors.EntitySelector = EntitySelectorAdapter
selectors.EntitySelectorConfig = dict
sys.modules["homeassistant.helpers"].selector = selectors
package = ModuleType("avr_flow_check")
package.__path__ = [str(ROOT / "custom_components/hk_avr")]
sys.modules[package.__name__] = package
flow_module = importlib.import_module("avr_flow_check.config_flow")


class FlowContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.flow = flow_module.AvrConfigFlow()
        self.data = {"name": "AVR", "host": "192.0.2.15", "port": 10025,
                     "wake_device": "harman_kardon", "wake_command": "power_on",
                     "wake_timeout": 45}
        self.patch = patch.object(flow_module.AvrClient, "async_probe", new_callable=AsyncMock)
        self.probe = self.patch.start()
        self.probe.return_value = True
        self.addCleanup(self.patch.stop)

    async def test_form_fields(self):
        result = await self.flow.async_step_user()
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(len(result["data_schema"].schema), 7)

    async def test_schema_populates_defaults(self):
        result = await self.flow.async_step_user()
        data = result["data_schema"]({"host": "192.0.2.15"})
        self.assertEqual(data["port"], 10025)
        self.assertEqual(data["wake_command"], "power_on")
        self.assertNotIn("wake_remote", data)

    async def test_schema_rejects_invalid_port(self):
        with self.assertRaises(flow_module.vol.Invalid):
            flow_module.schema({})({"host": "192.0.2.15", "port": 65536})

    async def test_online_creates_entry(self):
        result = await self.flow.async_step_user(self.data)
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "AVR")

    async def test_offline_without_remote_reports_error(self):
        self.probe.return_value = False
        result = await self.flow.async_step_user(self.data)
        self.assertEqual(result["errors"], {"base": "cannot_connect"})

    async def test_sleeping_receiver_confirmation(self):
        self.probe.return_value = False
        result = await self.flow.async_step_user({**self.data, "wake_remote": "remote.rm"})
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "offline")
        result = await self.flow.async_step_offline({})
        self.assertEqual(result["type"], "create_entry")

    async def test_duplicate_checked_before_probe(self):
        self.flow.entries = [SimpleNamespace(entry_id="other", data=self.data)]
        result = await self.flow.async_step_user(self.data)
        self.assertEqual(result["reason"], "already_configured")
        self.probe.assert_not_awaited()

    async def test_duplicate_checked_again_after_offline_confirmation(self):
        self.probe.return_value = False
        await self.flow.async_step_user({**self.data, "wake_remote": "remote.rm"})
        self.flow.entries = [SimpleNamespace(entry_id="other", data=self.data)]
        result = await self.flow.async_step_offline({})
        self.assertEqual(result["reason"], "already_configured")

    async def test_reconfigure_can_remove_remote_and_change_host(self):
        self.flow.entry = SimpleNamespace(entry_id="stable", data={
            **self.data, "wake_remote": "remote.rm",
        })
        self.flow.entries = [self.flow.entry]
        new = {**self.data, "host": "192.0.2.16"}
        result = await self.flow.async_step_reconfigure(new)
        self.assertEqual(result["entry_id"], "stable")
        self.assertEqual(result["data"]["host"], "192.0.2.16")
        self.assertNotIn("wake_remote", result["data"])
        self.assertNotIn("data_updates", result)

    async def test_invalid_hosts_do_not_connect(self):
        for host in ("http://avr", "192.168.999.1", "avr:10025", "two hosts", "", "-bad"):
            result = await self.flow.async_step_user({**self.data, "host": host})
            self.assertEqual(result["errors"], {"base": "invalid_config"}, host)
        self.probe.assert_not_awaited()

    async def test_addresses_normalized(self):
        for host, expected in ((" AVR.Local. ", "avr.local"), ("2001:0db8::1", "2001:db8::1")):
            result = await self.flow.async_step_user({**self.data, "host": host})
            self.assertEqual(result["data"]["host"], expected)

    async def test_empty_wake_command_rejected(self):
        result = await self.flow.async_step_user({
            **self.data, "wake_remote": "remote.rm", "wake_command": " ",
        })
        self.assertEqual(result["errors"], {"base": "invalid_config"})
        self.probe.assert_not_awaited()


if __name__ == "__main__":
    print(f"Schema backend: {flow_module.vol.__name__}")
    unittest.main(verbosity=2)
