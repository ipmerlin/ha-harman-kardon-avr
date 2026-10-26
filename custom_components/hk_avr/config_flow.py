"""UI setup and reconfiguration, without sending commands during validation."""

from __future__ import annotations

import asyncio
import ipaddress
import re

try:
    import probatio as vol
except ImportError:  # Home Assistant versions before the schema-library migration.
    import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .api import AvrClient
from .const import (
    CONF_WAKE_COMMAND,
    CONF_WAKE_DEVICE,
    CONF_WAKE_REMOTE,
    CONF_WAKE_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_WAKE_COMMAND,
    DEFAULT_WAKE_DEVICE,
    DEFAULT_WAKE_TIMEOUT,
    DOMAIN,
    WAKE_REMOTE_INTEGRATIONS,
)

CONF_LEARN_POWER_ON = "learn_power_on"
LEARN_SERVICE_TIMEOUT = 45


def normalize_host(host: str) -> str:
    """Accept a plain IP or DNS name; reject URLs, embedded ports and whitespace."""
    value = host.strip().lower().rstrip(".")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        if (len(value) > 253 or not value or ":" in value
                or re.fullmatch(r"[0-9.]+", value)):
            raise ValueError("Invalid host") from None
        if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                   for label in value.split(".")):
            raise ValueError("Invalid host") from None
        return value


def schema(defaults: dict) -> vol.Schema:
    """Keep connection and optional supported IR remotes in one form."""
    remote_default = defaults.get(CONF_WAKE_REMOTE)
    remote_key = (vol.Optional(CONF_WAKE_REMOTE, default=remote_default)
                  if remote_default else vol.Optional(CONF_WAKE_REMOTE))
    return vol.Schema({
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        remote_key: selector.EntitySelector(
            selector.EntitySelectorConfig(filter=[
                {"domain": "remote", "integration": integration}
                for integration in WAKE_REMOTE_INTEGRATIONS
            ])),
        vol.Required(CONF_WAKE_DEVICE, default=defaults.get(
            CONF_WAKE_DEVICE, DEFAULT_WAKE_DEVICE)): str,
        vol.Required(CONF_WAKE_COMMAND, default=defaults.get(
            CONF_WAKE_COMMAND, DEFAULT_WAKE_COMMAND)): str,
        vol.Required(CONF_WAKE_TIMEOUT, default=defaults.get(
            CONF_WAKE_TIMEOUT, DEFAULT_WAKE_TIMEOUT)):
            vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
        vol.Optional(CONF_LEARN_POWER_ON, default=False): bool,
    })


class AvrConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return await self._async_form("user", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._async_form("reconfigure", user_input)

    async def _async_form(self, step_id, user_input):
        entry = self._get_reconfigure_entry() if step_id == "reconfigure" else None
        defaults = dict(entry.data) if entry else {}
        errors = {}
        if user_input is not None:
            defaults = dict(user_input)
            data = dict(user_input)
            self._learn_requested = data.pop(CONF_LEARN_POWER_ON, False)
            try:
                data[CONF_HOST] = normalize_host(data[CONF_HOST])
                data[CONF_NAME] = data[CONF_NAME].strip()
                if not data[CONF_NAME]:
                    raise ValueError("Empty name")
                if self._learn_requested and not data.get(CONF_WAKE_REMOTE):
                    raise ValueError("Select an IR remote to learn")
                for field in (CONF_WAKE_DEVICE, CONF_WAKE_COMMAND):
                    data[field] = data[field].strip()
                    if data.get(CONF_WAKE_REMOTE) and not data[field]:
                        raise ValueError("Empty wake configuration")
            except ValueError:
                errors["base"] = "invalid_config"
            else:
                # No hardware serial is available: deduplicate connection addresses,
                # and use the stable entry ID for entity/device identifiers.
                for other in self._async_current_entries():
                    if (entry is None or other.entry_id != entry.entry_id) and (
                        other.data[CONF_HOST] == data[CONF_HOST]
                        and other.data[CONF_PORT] == data[CONF_PORT]
                    ):
                        return self.async_abort(reason="already_configured")
                reachable = await AvrClient(data[CONF_HOST], data[CONF_PORT]).async_probe()
                self._pending = data
                self._pending_entry = entry
                if reachable:
                    return await self._async_ready()
                if data.get(CONF_WAKE_REMOTE):
                    self._pending = data
                    self._pending_entry = entry
                    return await self.async_step_offline()
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id=step_id, data_schema=schema(defaults), errors=errors)

    async def async_step_offline(self, user_input=None):
        """Ask before saving an unverified, sleeping endpoint; never wake on setup."""
        if user_input is not None:
            return await self._async_ready()
        return self.async_show_form(step_id="offline", data_schema=vol.Schema({}))

    async def _async_ready(self):
        if self._learn_requested:
            return await self.async_step_learn_confirm()
        return self._finish(self._pending, self._pending_entry)

    async def async_step_learn_confirm(self, user_input=None):
        """Only an explicit submission starts the remote's learning mode."""
        if user_input is not None:
            self._learn_task = None
            return await self.async_step_learn_progress()
        return self.async_show_form(
            step_id="learn_confirm", data_schema=vol.Schema({}),
            description_placeholders={
                "remote": self._pending[CONF_WAKE_REMOTE],
                "device": self._pending[CONF_WAKE_DEVICE],
                "command": self._pending[CONF_WAKE_COMMAND],
            },
        )

    async def _async_learn(self) -> bool:
        """Bound the learning service; never transmit or retry automatically."""
        remote = self.hass.states.get(self._pending[CONF_WAKE_REMOTE])
        if remote is None or remote.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, "off"):
            return False
        try:
            async with asyncio.timeout(LEARN_SERVICE_TIMEOUT):
                await self.hass.services.async_call("remote", "learn_command", {
                    "entity_id": self._pending[CONF_WAKE_REMOTE],
                    "device": self._pending[CONF_WAKE_DEVICE],
                    "command": self._pending[CONF_WAKE_COMMAND],
                    "command_type": "ir", "timeout": 30,
                }, blocking=True)
        except (HomeAssistantError, TimeoutError):
            return False
        return True

    async def async_step_learn_progress(self, user_input=None):
        if self._learn_task is None:
            self._learn_task = self.hass.async_create_task(self._async_learn())
        if not self._learn_task.done():
            return self.async_show_progress(
                step_id="learn_progress", progress_action="learn_power_on",
                progress_task=self._learn_task,
            )
        success = not self._learn_task.cancelled() and self._learn_task.result()
        return self.async_show_progress_done(
            next_step_id="learn_done" if success else "learn_failed",
        )

    async def async_step_learn_done(self, user_input=None):
        if user_input is not None:
            return self._finish(self._pending, self._pending_entry)
        return self.async_show_form(step_id="learn_done", data_schema=vol.Schema({}))

    async def async_step_learn_failed(self, user_input=None):
        return self.async_show_menu(
            step_id="learn_failed", menu_options=["learn_confirm", "save_without_learning"],
        )

    async def async_step_save_without_learning(self, user_input=None):
        return self._finish(self._pending, self._pending_entry)

    def _finish(self, data, entry):
        for other in self._async_current_entries():
            if (entry is None or other.entry_id != entry.entry_id) and (
                other.data[CONF_HOST] == data[CONF_HOST]
                and other.data[CONF_PORT] == data[CONF_PORT]
            ):
                return self.async_abort(reason="already_configured")
        if entry is not None:
            return self.async_update_reload_and_abort(
                entry, data=data, title=data[CONF_NAME],
            )
        return self.async_create_entry(title=data[CONF_NAME], data=data)
