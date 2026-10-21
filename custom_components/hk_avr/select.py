"""Expose the source picker directly on the HA device page."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SOURCES
from .entity import AvrEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AvrSourceSelect(entry.runtime_data)])


class AvrSourceSelect(AvrEntity, SelectEntity):
    _attr_translation_key = "source"
    _attr_icon = "mdi:audio-input-rca"
    _attr_options = list(SOURCES)
    _attr_assumed_state = True

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "source")

    @property
    def available(self) -> bool:
        return self.coordinator.data.reachable

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.source

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_command("source-selection", option)
