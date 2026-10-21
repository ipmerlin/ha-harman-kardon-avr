"""Exercise new commands through actual HA platforms and service schemas."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hk_avr.api import AvrConnectionError
from custom_components.hk_avr.const import DOMAIN


@pytest.fixture
async def network_receiver(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, title="AVR", data=config_data)
    entry.add_to_hass(hass)
    with (
        patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=True),
        patch("custom_components.hk_avr.api.AvrClient.async_send", new_callable=AsyncMock) as send,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        ids = {e.unique_id.removeprefix(f"{entry.entry_id}_"): e.entity_id for e in entities}
        yield entry, ids, send
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(("key", "wire"), [
    ("mute_toggle", "mute-toggle"), ("play", "play"), ("pause", "pause"),
    ("next", "next"), ("previous", "previous"), ("forward", "forward"),
    ("reverse", "reverse"), ("up", "up"), ("down", "down"), ("left", "left"),
    ("right", "right"), ("ok", "ok"), ("back", "back"), ("home", "home"),
    ("info", "info"), ("options", "options"), ("sleep", "sleep"),
])
async def test_button_sends_exact_network_command(hass, network_receiver, key, wire):
    _, ids, send = network_receiver
    await hass.services.async_call("button", "press", {"entity_id": ids[key]}, blocking=True)
    send.assert_awaited_once_with(wire, "")


@pytest.mark.parametrize(("action", "wire"), [
    ("media_play", "play"), ("media_pause", "pause"),
    ("media_next_track", "next"), ("media_previous_track", "previous"),
])
async def test_playback_services(hass, network_receiver, action, wire):
    _, ids, send = network_receiver
    await hass.services.async_call(
        "media_player", action, {"entity_id": ids["receiver"]}, blocking=True,
    )
    send.assert_awaited_once_with(wire, "")
    assert hass.states.get(ids["receiver"]).state == "unknown"


async def test_source_picker_stays_in_sync_with_media_player(hass, network_receiver):
    _, ids, send = network_receiver
    await hass.services.async_call(
        "select", "select_option", {"entity_id": ids["source"], "option": "TV"}, blocking=True,
    )
    send.assert_awaited_once_with("source-selection", "TV")
    assert hass.states.get(ids["source"]).state == "TV"
    assert hass.states.get(ids["receiver"]).attributes["source"] == "TV"
    await hass.services.async_call(
        "media_player", "select_source", {"entity_id": ids["receiver"], "source": "USB"},
        blocking=True,
    )
    assert hass.states.get(ids["source"]).state == "USB"


async def test_remote_sequence_uses_ethernet(hass, network_receiver):
    _, ids, send = network_receiver
    await hass.services.async_call("remote", "send_command", {
        "entity_id": ids["network_remote"], "command": ["up", "ok", "mute_toggle"],
        "delay_secs": .001,
    }, blocking=True)
    assert [call.args for call in send.await_args_list] == [
        ("up", ""), ("ok", ""), ("mute-toggle", ""),
    ]
    assert hass.states.get(ids["network_remote"]).attributes["transport"] == "ethernet"


@pytest.mark.parametrize("data", [
    {"command": ["up", "unsupported"]},
    {"command": "up", "num_repeats": 2},
    {"command": "up", "hold_secs": 1},
    {"command": "up", "delay_secs": 6},
])
async def test_remote_rejects_unsupported_requests_before_sending(hass, network_receiver, data):
    _, ids, send = network_receiver
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("remote", "send_command", {
            "entity_id": ids["network_remote"], **data,
        }, blocking=True)
    send.assert_not_awaited()


async def test_remote_stops_on_network_error(hass, network_receiver):
    _, ids, send = network_receiver
    send.side_effect = [None, AvrConnectionError("test"), None]
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("remote", "send_command", {
            "entity_id": ids["network_remote"], "command": ["up", "ok", "back"],
            "delay_secs": .001,
        }, blocking=True)
    assert [call.args[0] for call in send.await_args_list] == ["up", "ok"]


async def test_remote_power_is_ethernet_only(hass, network_receiver):
    entry, ids, send = network_receiver
    wake = AsyncMock()
    entry.runtime_data.controller.wake = wake
    await hass.services.async_call("remote", "turn_on", {
        "entity_id": ids["network_remote"],
    }, blocking=True)
    send.assert_awaited_once_with("power-on", "")
    wake.assert_not_awaited()
    send.reset_mock()
    await hass.services.async_call("remote", "turn_off", {
        "entity_id": ids["network_remote"],
    }, blocking=True)
    send.assert_awaited_once_with("power-off", "")


async def test_network_controls_unavailable_when_ethernet_is_lost(hass, network_receiver):
    entry, ids, _ = network_receiver
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=False):
        await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    for key in ("up", "play", "sleep", "source", "network_remote"):
        assert hass.states.get(ids[key]).state == "unavailable"


async def test_existing_mute_registry_entry_is_reused(hass, config_data):
    entry = MockConfigEntry(domain=DOMAIN, title="AVR", data=config_data)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "button", DOMAIN, f"{entry.entry_id}_mute_toggle", config_entry=entry,
        suggested_object_id="existing_mute",
    )
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(entities) == 21
        assert hass.states.get(old.entity_id) is not None
        assert len([e for e in entities if e.unique_id.endswith("_mute_toggle")]) == 1
        await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("remote_state", [None, "unavailable", "unknown"])
async def test_missing_or_unavailable_broadlink_does_not_report_wake_success(
    hass, config_data, remote_state,
):
    entry = MockConfigEntry(domain=DOMAIN, title="AVR", data={
        **config_data, "wake_remote": "remote.test_broadlink",
    })
    entry.add_to_hass(hass)
    with patch("custom_components.hk_avr.api.AvrClient.async_probe", return_value=False):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        if remote_state is not None:
            hass.states.async_set("remote.test_broadlink", remote_state)
        with pytest.raises(HomeAssistantError, match="missing or unavailable"):
            await entry.runtime_data.async_command("power-on")
        assert entry.runtime_data.data.power is None
        assert entry.runtime_data.data.reachable is False
        await hass.config_entries.async_unload(entry.entry_id)
