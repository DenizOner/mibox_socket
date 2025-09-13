"""Options flow for MiPower."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_MAC

from .const import CONF_BACKEND, BACKEND_BLUETOOTHCTL, BACKEND_BLEAK

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = dict(self.config_entry.options or {})
        schema = vol.Schema({
            vol.Optional(CONF_NAME, default=self.config_entry.title): str,
            vol.Optional(CONF_BACKEND, default=current.get(CONF_BACKEND, self.config_entry.data.get(CONF_BACKEND, BACKEND_BLUETOOTHCTL))): vol.In([BACKEND_BLUETOOTHCTL, BACKEND_BLEAK]),
            vol.Optional("timeout_sec", default=current.get("timeout_sec", 8)): int,
            vol.Optional("retry_count", default=current.get("retry_count", 2)): int,
            vol.Optional("retry_delay_sec", default=current.get("retry_delay_sec", 2)): int,
            vol.Optional("scan_fallback", default=current.get("scan_fallback", False)): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
