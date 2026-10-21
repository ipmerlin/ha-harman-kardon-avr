"""Config flow, offline confirmation, duplicates and stable reconfiguration."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hk_avr.const import DOMAIN


async def test_user_form(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_online_creates_entry_without_power_commands(hass, config_data):
    with (
        patch("custom_components.hk_avr.config_flow.AvrClient.async_probe", return_value=True),
        patch("custom_components.hk_avr.api.AvrClient.async_send", new_callable=AsyncMock) as send,
        patch("custom_components.hk_avr.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=config_data,
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == "192.0.2.15"
    send.assert_not_awaited()


async def test_unreachable_without_broadlink(hass, config_data):
    with patch("custom_components.hk_avr.config_flow.AvrClient.async_probe", return_value=False):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=config_data,
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_sleeping_receiver_requires_confirmation(hass, config_data):
    config_data["wake_remote"] = "remote.test_broadlink"
    with (
        patch("custom_components.hk_avr.config_flow.AvrClient.async_probe", return_value=False),
        patch("custom_components.hk_avr.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=config_data,
        )
        assert result["step_id"] == "offline"
        assert not hass.config_entries.async_entries(DOMAIN)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_duplicate_is_aborted(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)
    with patch("custom_components.hk_avr.config_flow.AvrClient.async_probe") as probe:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=config_data,
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    probe.assert_not_called()


async def test_bad_host_never_connects(hass, config_data):
    config_data["host"] = "http://receiver:10025"
    with patch("custom_components.hk_avr.config_flow.AvrClient.async_probe") as probe:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=config_data,
        )
    assert result["errors"] == {"base": "invalid_config"}
    probe.assert_not_called()


async def test_reconfigure_replaces_data_and_keeps_identity(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, title="Old", data={
        **config_data, "wake_remote": "remote.test_broadlink",
    })
    entry.add_to_hass(hass)
    data = {**config_data, "host": "192.0.2.16", "name": "New"}
    original_id = entry.entry_id
    with (
        patch("custom_components.hk_avr.config_flow.AvrClient.async_probe", return_value=True),
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE,
                             "entry_id": entry.entry_id}, data=data,
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.entry_id == original_id
    assert entry.title == "New"
    assert entry.data["host"] == "192.0.2.16"
    assert "wake_remote" not in entry.data
    reload_entry.assert_called_once_with(original_id)
