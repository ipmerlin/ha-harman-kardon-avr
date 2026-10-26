"""Network remote commands for automations, with no learned IR codes."""

from collections.abc import Iterable

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import REMOTE_COMMANDS
from .entity import AvrEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AvrNetworkRemote(entry.runtime_data)])


class AvrNetworkRemote(AvrEntity, RemoteEntity):
    """Represent the network keypad; its enabled state follows TCP availability."""

    _attr_translation_key = "network_remote"
    _attr_icon = "mdi:remote"
    _attr_assumed_state = True

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "network_remote")

    @property
    def available(self) -> bool:
        return self.coordinator.data.reachable

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.reachable

    @property
    def extra_state_attributes(self) -> dict:
        return {"transport": "ethernet", "commands": list(REMOTE_COMMANDS)}

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_network_turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_command("power-off")

    async def async_send_command(self, command: Iterable[str], **kwargs) -> None:
        keys = [command] if isinstance(command, str) else list(command)
        if kwargs.get("num_repeats", 1) != 1 or kwargs.get("hold_secs", 0):
            raise ServiceValidationError("Repeats and held keys are not supported; send explicit commands")
        if not 1 <= len(keys) <= 20 or any(key not in REMOTE_COMMANDS for key in keys):
            raise ServiceValidationError("Unknown network command or invalid sequence length")
        delay = kwargs.get("delay_secs", .4)
        if not 0 <= delay <= 5:
            raise ServiceValidationError("Network command delay must be between 0 and 5 seconds")
        await self.coordinator.async_sequence([REMOTE_COMMANDS[key] for key in keys], delay)
