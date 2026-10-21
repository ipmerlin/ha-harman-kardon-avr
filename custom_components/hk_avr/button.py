"""Mute is a toggle: expose it honestly without an invented mute state."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AvrEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AvrMuteButton(entry.runtime_data)])


class AvrMuteButton(AvrEntity, ButtonEntity):
    _attr_translation_key = "mute_toggle"
    _attr_icon = "mdi:volume-mute"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "mute_toggle")

    @property
    def available(self) -> bool:
        return self.coordinator.data.reachable

    async def async_press(self) -> None:
        await self.coordinator.async_command("mute-toggle")
