"""Actual HA platform loading and Broadlink service dispatch contracts."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hk_avr.const import DOMAIN


async def test_online_platforms_and_unload(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, title="AVR", data=config_data)
    entry.add_to_hass(hass)
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert {e.domain for e in entities} == {"media_player", "button", "binary_sensor"}
        player = next(e.entity_id for e in entities if e.domain == "media_player")
        assert hass.states.get(player).state == "unknown"
        with patch("custom_components.hk_avr.api.AvrClient.async_send", new_callable=AsyncMock) as send:
            await hass.services.async_call(
                "media_player", "volume_up", {"entity_id": player}, blocking=True,
            )
            send.assert_awaited_once_with("volume-up", "")
        assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_sleeping_player_remains_callable_and_dispatches_broadlink(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, title="AVR", data={
        **config_data, "wake_remote": "remote.test_broadlink",
    })
    entry.add_to_hass(hass)
    received = []

    async def remote_send(call):
        received.append(call.data)

    hass.services.async_register("remote", "send_command", remote_send)
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=False):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    player = next(e.entity_id for e in entities if e.domain == "media_player")
    assert hass.states.get(player).state == "unknown"
    assert hass.states.get(player).attributes["network_reachable"] is False
    assert received == []
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", side_effect=[False, True]):
        await hass.services.async_call(
            "media_player", "turn_on", {"entity_id": player}, blocking=True,
        )
    assert len(received) == 1
    assert received[0]["entity_id"] == "remote.test_broadlink"
    assert received[0]["command"] == "power_on"
    assert received[0]["device"] == "harman_kardon"
    assert received[0]["num_repeats"] == 1
    assert hass.states.get(player).state == "on"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unreachable_without_wake_retries_setup(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=False):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY
