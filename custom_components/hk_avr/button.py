"""Explicit one-shot network commands, without invented feedback state."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NETWORK_BUTTONS
from .entity import AvrEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AvrNetworkButton(entry.runtime_data, key) for key in NETWORK_BUTTONS])


class AvrNetworkButton(AvrEntity, ButtonEntity):
    """Keep the original mute entity ID while adding the remaining remote keys."""

    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._command, self._attr_icon = NETWORK_BUTTONS[key]
        self._attr_translation_key = key

    @property
    def available(self) -> bool:
        return self.coordinator.data.reachable

    async def async_press(self) -> None:
        await self.coordinator.async_command(self._command)
