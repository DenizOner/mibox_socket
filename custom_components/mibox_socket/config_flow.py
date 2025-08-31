"""Config flow for Mibox Socket integration with optional device selection.

Adımlar:
1) Yöntem seç (Manual veya Select existing HA device)
2a) Manual: name + mac gir
2b) Select: HA'de görünen media_player'lar listelenir -> seç -> ardından MAC ve isim gir (isim otomatik olabilir)
"""

from __future__ import annotations

import re
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_MAC
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

# Basit MAC regex
_MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

STEP_INIT_SCHEMA = vol.Schema(
    {
        vol.Required("method", default="manual"): vol.In({"manual": "Manual: enter MAC & name", "select": "Select existing HA device (media_player)"}),
    }
)

STEP_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_MAC): str,
    }
)

# select step schema is dynamic (vol.In with choices built at runtime)

class MiBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Mibox Socket."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Initial step: choose method."""
        errors = {}
        if user_input is not None:
            method = user_input.get("method")
            if method == "manual":
                return await self.async_step_manual()
            if method == "select":
                return await self.async_step_select()
        return self.async_show_form(step_id="user", data_schema=STEP_INIT_SCHEMA, errors=errors)

    async def async_step_manual(self, user_input=None):
        """Manual entry: ask for name and MAC."""
        errors = {}
        if user_input is not None:
            mac = user_input[CONF_MAC].strip().upper()
            if not _MAC_REGEX.match(mac):
                errors["base"] = "invalid_mac"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates={CONF_NAME: user_input[CONF_NAME], CONF_MAC: mac})
                return self.async_create_entry(title=user_input[CONF_NAME], data={CONF_NAME: user_input[CONF_NAME], CONF_MAC: mac})
        return self.async_show_form(step_id="manual", data_schema=STEP_MANUAL_SCHEMA, errors=errors)

    async def async_step_select(self, user_input=None):
        """Show a dropdown of candidate HA media_player devices; then request MAC (and optional name)."""
        # Build choices: device_id -> friendly name (unique)
        registry = er.async_get(self.hass)
        entities = registry.entities.values()

        # Find media_player entities that are linked to a device (device_id not None)
        choices = {}
        for ent in entities:
            if ent.domain == "media_player" and ent.device_id:
                # Friendly label: use original name or entity_id as fallback
                label = ent.original_name or ent.name or ent.entity_id
                # don't overwrite label if device already added, but prefer first
                if ent.device_id not in choices:
                    choices[ent.device_id] = label

        if not choices:
            # Eğer HA'de uygun device yoksa kullanıcıyı geri gönder
            return self.async_abort(reason="no_ha_device_found")

        schema = vol.Schema({vol.Required("device"): vol.In(choices)})

        if user_input is not None:
            device_id = user_input["device"]
            # Prefill name from chosen label
            name = choices.get(device_id, "Mibox")
            # İleri adım: MAC sor
            return await self.async_step_confirm_device({"device_id": device_id, "name": name})

        return self.async_show_form(step_id="select", data_schema=schema)

    async def async_step_confirm_device(self, user_input=None):
        """After device selected, ask for MAC and optional name (prefilled)."""
        # user_input may contain device_id and name passed from previous step
        device_id = user_input.get("device_id")
        prefill_name = user_input.get("name", "")

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=prefill_name): str,
                vol.Required(CONF_MAC): str,
            }
        )

        errors = {}
        if user_input is not None and "CONF_MAC" not in user_input:
            # This guard is just to avoid mypy confusion
            pass

        # actual submitted data arrives as user_input when this step is posted
        if user_input is not None and "CONF_MAC" not in user_input:
            # shouldn't happen
            pass

        # But when the form is submitted properly, user_input will include CONF_MAC
        # We need to fetch the real posted data from the function parameter
        if user_input is not None and CONF_MAC in user_input:
            mac = user_input[CONF_MAC].strip().upper()
            if not _MAC_REGEX.match(mac):
                errors["base"] = "invalid_mac"
            else:
                # create entry with device_id included
                title = user_input[CONF_NAME]
                data = {CONF_NAME: user_input[CONF_NAME], CONF_MAC: mac, "device_id": device_id}
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(updates=data)
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(step_id="confirm_device", data_schema=schema, errors=errors)
