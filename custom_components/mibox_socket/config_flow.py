"""Config flow for Mibox Socket integration.

Bu dosya Home Assistant UI içinden entegrasyonun eklenmesini sağlar.
Kullanıcıdan iki bilgi alıyoruz:
 - mac: Bluetooth MAC adresi (ör. AA:BB:CC:11:22:33)
 - name: Cihaza verilecek kullanıcı dostu isim
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_MAC

from .const import DOMAIN

# Form alanları için schema
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
        """Kullanıcı GUI formu gösterme / işle."""
        errors = {}
        if user_input is not None:
            mac = user_input[CONF_MAC].upper()
            # Basit MAC doğrulama: iki hex, iki nokta vb. (çok katı değil)
            if len(mac) < 11:
                errors["base"] = "invalid_mac"
            else:
                # UNIQUE ID olarak mac'i kullanıyoruz -> bir cihazın iki kez eklenmesini engeller.
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
