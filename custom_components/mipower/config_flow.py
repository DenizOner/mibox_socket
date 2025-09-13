"""Config flow for MiPower."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_MAC

from .const import DOMAIN, CONF_BACKEND, BACKEND_BLUETOOTHCTL, BACKEND_BLEAK

class MiPowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            mac = user_input.get(CONF_MAC)
            name = user_input.get(CONF_NAME)
            if not mac:
                errors["base"] = "invalid_mac"
            else:
                return self.async_create_entry(title=name, data={CONF_MAC: mac, CONF_BACKEND: user_input.get(CONF_BACKEND, BACKEND_BLUETOOTHCTL)})
        data_schema = vol.Schema({
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_MAC): str,
            vol.Optional(CONF_BACKEND, default=BACKEND_BLUETOOTHCTL): vol.In([BACKEND_BLUETOOTHCTL, BACKEND_BLEAK]),
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
