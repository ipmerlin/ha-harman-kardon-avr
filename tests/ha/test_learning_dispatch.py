"""Exercise the HA remote entity service schema and dispatcher, without IR hardware."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.hk_avr.const import DOMAIN


class LearningRemote(RemoteEntity):
    _attr_name = "Learning test"
    _attr_unique_id = "learning_test"
    _attr_is_on = True
    _attr_should_poll = False
    _attr_supported_features = RemoteEntityFeature.LEARN_COMMAND

    def __init__(self, error):
        self.error = error
        self.calls = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def async_learn_command(self, **kwargs):
        self.calls.append(kwargs)
        self.started.set()
        await self.release.wait()
        if self.error:
            raise self.error


@pytest.mark.parametrize("error", [None, HomeAssistantError("provider refused"), ValueError("bad response")])
async def test_entity_learning_dispatch(hass, config_data, error):
    assert await async_setup_component(hass, "remote", {})
    remote = LearningRemote(error)
    await hass.data["remote"].async_add_entities([remote])
    await hass.async_block_till_done()
    with patch("custom_components.hk_avr.config_flow.AvrClient.async_probe", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"},
            data={**config_data, "wake_remote": remote.entity_id, "learn_power_on": True})
        flow_id = result["flow_id"]
        result = await hass.config_entries.flow.async_configure(flow_id, {})
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        await remote.started.wait()
        assert len(remote.calls) == 1
        assert remote.calls[0]["command"] == ["power_on"]
        assert remote.calls[0]["device"] == "harman_kardon"
        assert remote.calls[0]["timeout"] == 30
        assert remote.calls[0]["command_type"] == "ir"
        # Refreshing the spinner must not start another learning request.
        result = await hass.config_entries.flow.async_configure(flow_id)
        assert result["type"] == FlowResultType.SHOW_PROGRESS
        assert len(remote.calls) == 1
        remote.release.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(flow_id)
        assert result["step_id"] == ("learn_failed" if error else "learn_done")
        if error:
            assert result["errors"] == {"base": "learn_service_failed"}
        hass.config_entries.flow.async_abort(flow_id)
