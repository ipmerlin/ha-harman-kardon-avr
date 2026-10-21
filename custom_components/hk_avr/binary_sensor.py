"""TCP connectivity is observable independently of assumed receiver power."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AvrEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AvrConnectivity(entry.runtime_data)])


class AvrConnectivity(AvrEntity, BinarySensorEntity):
    _attr_translation_key = "ethernet"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "ethernet")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.reachable
