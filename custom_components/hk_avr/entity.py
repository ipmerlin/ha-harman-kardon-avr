"""Shared device metadata."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AvrCoordinator


class AvrEntity(CoordinatorEntity[AvrCoordinator]):
    """Group all entities under one stable config-entry identity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AvrCoordinator, suffix: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
            manufacturer="Harman Kardon", model="AVR 151S",
        )
