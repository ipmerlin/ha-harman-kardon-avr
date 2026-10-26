"""HA service contracts shared by Broadlink and the Xiaomi IR Local project."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.remote import RemoteEntity
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hk_avr.config_flow import schema
from custom_components.hk_avr.const import DOMAIN


def test_remote_selector_includes_both_integrations_and_excludes_avr():
    form = schema({})
    selector = next(value for key, value in form.schema.items() if key.schema == "wake_remote")
    filters = selector.config["filter"]
    assert {item["integration"] for item in filters} == {"broadlink", "xiaomi_ir"}
    assert all(item["domain"] in ("remote", ["remote"]) for item in filters)


@pytest.mark.parametrize("remote_id", ["remote.broadlink", "remote.xiaomi_ir"])
async def test_setup_accepts_either_remote_without_waking(hass, config_data, remote_id):
    data = {**config_data, "wake_remote": remote_id}
    with (
        patch("custom_components.hk_avr.config_flow.AvrClient.async_probe", return_value=False),
        patch("custom_components.hk_avr.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=data,
        )
        assert result["step_id"] == "offline"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result["data"]["wake_remote"] == remote_id


class NamedIRRemote(RemoteEntity):
    """Model Xiaomi's learned device/command contract, not its UDP transport."""

    _attr_name = "Xiaomi IR test"
    _attr_unique_id = "xiaomi_ir_test"
    _attr_is_on = True

    def __init__(self):
        self.sent = []
        self.fail_send = False

    async def async_send_command(self, command, **kwargs):
        if not self.is_on:
            raise ServiceValidationError("The remote is disabled; turn it on first")
        assert kwargs.get("device") == "harman_kardon"
        assert list(command) == ["power_on"]
        assert kwargs.get("num_repeats", 1) == 1
        self.sent.append((list(command), kwargs))
        if self.fail_send:
            raise HomeAssistantError("IR transmission failed")


@pytest.fixture
async def xiaomi_receiver(hass, config_data):
    assert await async_setup_component(hass, "remote", {})
    remote = NamedIRRemote()
    await hass.data["remote"].async_add_entities([remote])
    await hass.async_block_till_done()
    entry = MockConfigEntry(domain=DOMAIN, title="AVR", data={
        **config_data, "wake_remote": remote.entity_id,
    })
    entry.add_to_hass(hass)
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=False):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    yield entry, remote
    await hass.config_entries.async_unload(entry.entry_id)


async def test_xiaomi_wake_uses_learned_command_once_and_waits_for_tcp(hass, xiaomi_receiver):
    entry, remote = xiaomi_receiver
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", side_effect=[False, True]):
        await entry.runtime_data.async_command("power-on")
    assert len(remote.sent) == 1
    assert entry.runtime_data.data.power == "on"
    assert entry.runtime_data.data.last_transport == "infrared"
    assert entry.runtime_data.data.reachable is True


async def test_disabled_xiaomi_returns_error_without_false_success(hass, xiaomi_receiver):
    entry, remote = xiaomi_receiver
    remote._attr_is_on = False
    remote.async_write_ha_state()
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=False):
        with pytest.raises(HomeAssistantError, match="disabled"):
            await entry.runtime_data.async_command("power-on")
    assert not remote.sent
    assert entry.runtime_data.data.power is None


async def test_xiaomi_error_is_not_retried(hass, xiaomi_receiver):
    entry, remote = xiaomi_receiver
    remote.fail_send = True
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=False):
        with pytest.raises(HomeAssistantError, match="IR transmission failed"):
            await entry.runtime_data.async_command("power-on")
    assert len(remote.sent) == 1
    assert entry.runtime_data.data.power is None


async def test_online_avr_does_not_send_xiaomi_command(hass, xiaomi_receiver):
    entry, remote = xiaomi_receiver
    with (
        patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=True),
        patch("custom_components.hk_avr.api.AvrClient.async_send", new_callable=AsyncMock) as send,
    ):
        await entry.runtime_data.async_command("power-on")
    send.assert_awaited_once_with("power-on", "")
    assert not remote.sent


async def test_reconfigure_to_xiaomi_preserves_entry_and_other_parameters(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, data={
        **config_data, "wake_remote": "remote.broadlink",
    })
    entry.add_to_hass(hass)
    with (
        patch("custom_components.hk_avr.config_flow.AvrClient.async_probe", return_value=True),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={
            "source": "reconfigure", "entry_id": entry.entry_id,
        }, data={**config_data, "wake_remote": "remote.xiaomi_ir"})
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {**config_data, "wake_remote": "remote.xiaomi_ir"}
