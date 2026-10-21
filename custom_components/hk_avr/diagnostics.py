"""Diagnostics contain no addresses, remote identifiers or learned commands."""

from dataclasses import asdict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_WAKE_REMOTE, CONF_WAKE_TIMEOUT


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    return {"model": "AVR 151S", "wake_configured": bool(entry.data.get(CONF_WAKE_REMOTE)),
            "wake_timeout": entry.data[CONF_WAKE_TIMEOUT],
            "state_feedback": "optimistic",
            "runtime": asdict(entry.runtime_data.controller.snapshot)}
