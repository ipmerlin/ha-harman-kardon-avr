"""Bridge HA, the AVR transport and Broadlink's existing HA integration."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AvrClient, AvrConnectionError
from .const import (
    CONF_WAKE_COMMAND,
    CONF_WAKE_DEVICE,
    CONF_WAKE_REMOTE,
    CONF_WAKE_TIMEOUT,
    DOMAIN,
)
from .controller import AvrController, Snapshot, WakeRequiredError, WakeTimeoutError

_LOGGER = logging.getLogger(__name__)


class AvrCoordinator(DataUpdateCoordinator[Snapshot]):
    """Polling measures network reachability, never invents receiver state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: AvrClient) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=30))
        self.entry = entry
        self.controller = AvrController(
            client,
            self._async_ir_wake if entry.data.get(CONF_WAKE_REMOTE) else None,
            entry.data[CONF_WAKE_TIMEOUT],
        )

    async def _async_ir_wake(self) -> None:
        try:
            async with asyncio.timeout(15):
                await self.hass.services.async_call(
                    "remote", "send_command",
                    {ATTR_ENTITY_ID: self.entry.data[CONF_WAKE_REMOTE],
                     "device": self.entry.data[CONF_WAKE_DEVICE],
                     "command": self.entry.data[CONF_WAKE_COMMAND], "num_repeats": 1},
                    blocking=True,
                )
        except TimeoutError as err:
            raise HomeAssistantError(
                "Broadlink did not finish sending within 15 seconds. Check Broadlink availability."
            ) from err

    async def _async_update_data(self) -> Snapshot:
        return await self.controller.async_refresh()

    async def async_command(self, command: str, parameter: str = "") -> None:
        """Surface failures and publish only the resulting optimistic state."""
        try:
            if command == "power-on":
                await self.controller.async_turn_on()
            else:
                await self.controller.async_command(command, parameter)
        except WakeRequiredError as err:
            raise HomeAssistantError(
                "Ethernet is unavailable. Configure Broadlink wake or use the physical remote."
            ) from err
        except WakeTimeoutError as err:
            raise HomeAssistantError(
                "Broadlink command sent, but AVR Ethernet did not return. "
                "Check the learned Power On command, IR visibility and receiver IP."
            ) from err
        except AvrConnectionError as err:
            raise HomeAssistantError(
                "AVR TCP command failed. Execution is uncertain; command was not repeated."
            ) from err
        finally:
            self.async_set_updated_data(self.controller.snapshot)
