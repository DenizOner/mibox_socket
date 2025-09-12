"""Config flow for MiPower integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_MAC,
    CONF_NAME,
    CONF_BACKEND,
    BACKEND_BLUETOOTHCTL,
    BACKEND_BLEAK,
)

_LOGGER = logging.getLogger(__name__)


class MiPowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MiPower."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Step when user starts the flow from UI."""
        errors = {}
        if user_input is not None:
            # Basic validation: require MAC
            mac = user_input.get(CONF_MAC)
            if not mac:
                errors["base"] = "invalid_mac"
            else:
                # create entry
                return self.async_create_entry(title=user_input.get(CONF_NAME) or mac, data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_MAC): str,
                vol.Optional(CONF_NAME, default="MiPower"): str,
                vol.Optional(CONF_BACKEND, default=BACKEND_BLUETOOTHCTL): vol.In(
                    [BACKEND_BLUETOOTHCTL, BACKEND_BLEAK]
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
