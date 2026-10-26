"""Real config-flow progress transitions; no physical IR operations occur."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hk_avr.const import DOMAIN


@pytest.fixture
async def learner(hass):
    assert await async_setup_component(hass, "remote", {})
    for entity_id in ("remote.xiaomi_ir", "remote.broadlink"):
        hass.states.async_set(entity_id, "on")
    state = {"calls": [], "release": asyncio.Event(), "started": asyncio.Event(), "error": None}

    async def learn(call):
        state["calls"].append(call.data)
        state["started"].set()
        await state["release"].wait()
        if state["error"] is not None:
            raise state["error"]

    hass.services.async_register("remote", "learn_command", learn)
    with (
        patch("custom_components.hk_avr.config_flow.AvrClient.async_probe", return_value=True),
        patch("custom_components.hk_avr.api.AvrClient.async_send", new_callable=AsyncMock) as send,
        patch("custom_components.hk_avr.async_setup_entry", return_value=True),
    ):
        yield state
        assert not send.await_count


async def start_learning(hass, config_data, learner, remote="remote.xiaomi_ir", context=None):
    result = await hass.config_entries.flow.async_init(DOMAIN, context=context or {"source": "user"},
        data={**config_data, "wake_remote": remote, "learn_power_on": True})
    assert result["step_id"] == "learn_confirm"
    assert not learner["calls"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    await learner["started"].wait()
    return result["flow_id"]


async def finish_learning(hass, flow_id, learner):
    learner["release"].set()
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(flow_id)


@pytest.mark.parametrize("remote", ["remote.xiaomi_ir", "remote.broadlink"])
async def test_learning_is_explicit_and_saves_after_success(hass, config_data, learner, remote):
    flow_id = await start_learning(hass, config_data, learner, remote)
    assert not hass.config_entries.async_entries(DOMAIN)
    result = await finish_learning(hass, flow_id, learner)
    assert result["step_id"] == "learn_done"
    assert len(learner["calls"]) == 1
    call = learner["calls"][0]
    assert call["entity_id"] == remote
    assert call["device"] == "harman_kardon"
    assert call["command"] == "power_on"
    assert call["command_type"] == "ir"
    assert call["timeout"] == 30
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "learn_power_on" not in result["data"]


async def test_learning_unchecked_never_calls_service(hass, config_data, learner):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"},
        data={**config_data, "wake_remote": "remote.xiaomi_ir"})
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert not learner["calls"]


async def test_learning_requires_selected_remote(hass, config_data, learner):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"},
        data={**config_data, "learn_power_on": True})
    assert result["errors"] == {"base": "invalid_config"}
    assert not learner["calls"]


@pytest.mark.parametrize("error", [HomeAssistantError("test"), TimeoutError()])
async def test_failed_learning_has_no_automatic_retry(hass, config_data, learner, error):
    learner["error"] = error
    flow_id = await start_learning(hass, config_data, learner)
    result = await finish_learning(hass, flow_id, learner)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "learn_failed"
    assert not hass.config_entries.async_entries(DOMAIN)
    assert len(learner["calls"]) == 1
    # Refreshing the failure screen never relearns or saves implicitly.
    await hass.config_entries.flow.async_configure(flow_id)
    assert len(learner["calls"]) == 1
    result = await hass.config_entries.flow.async_configure(flow_id, {
        "next_step_id": "save_without_learning",
    })
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_retry_requires_another_explicit_confirmation(hass, config_data, learner):
    learner["error"] = HomeAssistantError("test")
    flow_id = await start_learning(hass, config_data, learner)
    await finish_learning(hass, flow_id, learner)
    result = await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "learn_confirm"})
    assert result["step_id"] == "learn_confirm"
    assert len(learner["calls"]) == 1
    learner["error"] = None
    learner["release"].clear()
    await hass.config_entries.flow.async_configure(flow_id, {})
    result = await finish_learning(hass, flow_id, learner)
    assert result["step_id"] == "learn_done"
    assert len(learner["calls"]) == 2
    hass.config_entries.flow.async_abort(flow_id)


async def test_abort_cancels_progress_and_does_not_save(hass, config_data, learner):
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def wait_for_code(self):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with patch("custom_components.hk_avr.config_flow.AvrConfigFlow._async_learn", wait_for_code):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"},
            data={**config_data, "wake_remote": "remote.xiaomi_ir", "learn_power_on": True})
        flow_id = result["flow_id"]
        await hass.config_entries.flow.async_configure(flow_id, {})
        await started.wait()
        hass.config_entries.flow.async_abort(flow_id)
        await hass.async_block_till_done()
    assert cancelled.is_set()
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_learning_error_preserves_reconfigured_entry(hass, config_data, learner):
    entry = MockConfigEntry(domain=DOMAIN, title="Old", data=config_data)
    entry.add_to_hass(hass)
    learner["error"] = HomeAssistantError("test")
    flow_id = await start_learning(hass, config_data, learner, context={
        "source": "reconfigure", "entry_id": entry.entry_id,
    })
    await finish_learning(hass, flow_id, learner)
    assert entry.data == config_data
    assert entry.title == "Old"
    hass.config_entries.flow.async_abort(flow_id)


async def test_learning_service_timeout_is_bounded(hass, config_data, learner):
    with patch("custom_components.hk_avr.config_flow.LEARN_SERVICE_TIMEOUT", .03):
        flow_id = await start_learning(hass, config_data, learner)
        # Release the provider only after the wait timeout, to avoid a leaked service task.
        await asyncio.sleep(.05)
        learner["release"].set()
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["step_id"] == "learn_failed"
    assert len(learner["calls"]) == 1
    hass.config_entries.flow.async_abort(flow_id)
