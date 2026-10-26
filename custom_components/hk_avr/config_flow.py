"""UI setup and reconfiguration, without sending commands during validation."""

from __future__ import annotations

import ipaddress
import re

try:
    import probatio as vol
except ImportError:  # Home Assistant versions before the schema-library migration.
    import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
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
            try:
                data[CONF_HOST] = normalize_host(data[CONF_HOST])
                data[CONF_NAME] = data[CONF_NAME].strip()
                if not data[CONF_NAME]:
                    raise ValueError("Empty name")
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
                if reachable:
                    return self._finish(data, entry)
                if data.get(CONF_WAKE_REMOTE):
                    self._pending = data
                    self._pending_entry = entry
                    return await self.async_step_offline()
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id=step_id, data_schema=schema(defaults), errors=errors)

    async def async_step_offline(self, user_input=None):
        """Ask before saving an unverified, sleeping endpoint; never wake on setup."""
        if user_input is not None:
            return self._finish(self._pending, self._pending_entry)
        return self.async_show_form(step_id="offline", data_schema=vol.Schema({}))

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
