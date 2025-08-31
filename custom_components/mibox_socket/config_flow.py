"""Config flow for Mibox Socket integration.

Kullanıcı arayüzünden MAC ve name girilmesini sağlar.
"""

from __future__ import annotations

import re
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_MAC

from .const import DOMAIN

# Basit MAC adresi doğrulama (AA:BB:CC:11:22:33 formatı)
_MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_MAC): str,
    }
)

class MiBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Mibox Socket."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            mac = user_input[CONF_MAC].strip().upper()
            # MAC formatı kontrolü
            if not _MAC_REGEX.match(mac):
                errors["base"] = "invalid_mac"
            else:
                # unique id olarak MAC kullan -> aynı cihaz iki kez eklenmesin
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates={CONF_NAME: user_input[CONF_NAME], CONF_MAC: mac})
                # Kaydı oluştur
                return self.async_create_entry(title=user_input[CONF_NAME], data={CONF_NAME: user_input[CONF_NAME], CONF_MAC: mac})

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
