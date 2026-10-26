"""Power-off state through actual HA services and coordinator polling."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hk_avr.api import AvrConnectionError
from custom_components.hk_avr.const import DOMAIN


@pytest.mark.parametrize("service_domain", ["media_player", "remote"])
async def test_successful_shutdown_remains_off_when_ethernet_sleeps(hass, config_data, service_domain):
    entry = MockConfigEntry(domain=DOMAIN, title="AVR", data={
        **config_data, "wake_remote": "remote.xiaomi_ir",
    })
    entry.add_to_hass(hass)
    with (
        patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=True) as probe,
        patch("custom_components.hk_avr.api.AvrClient.async_send", new_callable=AsyncMock) as send,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        player = next(e.entity_id for e in entities if e.domain == "media_player")
        target = next(e.entity_id for e in entities if e.domain == service_domain)
        ethernet = next(e.entity_id for e in entities if e.domain == "binary_sensor")
        await hass.services.async_call(service_domain, "turn_off", {"entity_id": target}, blocking=True)
        await hass.async_block_till_done()
        send.assert_awaited_once_with("power-off", "")
        assert hass.states.get(player).state == "off"
        for reachable in (False, True, False, True, False):
            probe.return_value = reachable
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get(player).state == "off"
            assert hass.states.get(player).attributes["network_reachable"] is reachable
            assert hass.states.get(ethernet).state == ("on" if reachable else "off")
        await hass.config_entries.async_unload(entry.entry_id)


async def test_failed_shutdown_is_unknown_and_surfaces_transport_error(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, title="AVR", data={
        **config_data, "wake_remote": "remote.xiaomi_ir",
    })
    entry.add_to_hass(hass)
    with (
        patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=True),
        patch("custom_components.hk_avr.api.AvrClient.async_send", side_effect=AvrConnectionError),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        player = next(e.entity_id for e in entities if e.domain == "media_player")
        with pytest.raises(HomeAssistantError, match="AVR TCP command failed"):
            await hass.services.async_call("media_player", "turn_off", {"entity_id": player}, blocking=True)
        await hass.async_block_till_done()
        assert hass.states.get(player).state == "unknown"
        assert hass.states.get(player).attributes["network_reachable"] is False
        await hass.config_entries.async_unload(entry.entry_id)
