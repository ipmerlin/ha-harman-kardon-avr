"""Harman Kardon AVR 151S with optional IR wake."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .api import AvrClient
from .coordinator import AvrCoordinator

PLATFORMS = [
    Platform.MEDIA_PLAYER, Platform.BUTTON, Platform.BINARY_SENSOR,
    Platform.REMOTE, Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load an existing receiver even when its Ethernet is currently asleep."""
    coordinator = AvrCoordinator(
        hass, entry, AvrClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    )
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove platforms and their polling subscriptions."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
