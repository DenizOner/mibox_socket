"""custom_components/mibox_socket/config_flow.py

Sağlam (hata-tolerant) config flow + options flow.
Not: async_get_options_flow statik olarak tanımlanmıştır — Home Assistant'ın çağrı modeline uyumlu.
"""

from __future__ import annotations

from typing import Any
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_NAME, CONF_MAC
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class MiBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MiBox Socket integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Kullanıcıdan MAC (zorunlu), opsiyonel isim ve media_player seçimi alır."""
        errors: dict[str, str] = {}

        try:
            if user_input is not None:
                mac = user_input.get(CONF_MAC)
                name = user_input.get(CONF_NAME)
                media_player_entity_id = user_input.get("media_player_entity_id")

                if not mac:
                    errors["base"] = "mac_required"
                else:
                    data = {
                        CONF_MAC: mac,
                        CONF_NAME: name or "",
                    }
                    if media_player_entity_id:
                        data["media_player_entity_id"] = media_player_entity_id

                    title = name or f"MiBox {mac[-5:].replace(':','')}"
                    return self.async_create_entry(title=title, data=data)

            # Formu oluştururken selector deneyelim; hata çıkarsa fallback string input ver
            try:
                media_selector = selector.EntitySelector({"domain": "media_player", "multiple": False})
                schema = vol.Schema(
                    {
                        vol.Required(CONF_MAC): str,
                        vol.Optional(CONF_NAME, default=""): str,
                        vol.Optional("media_player_entity_id", default=""): media_selector,
                    }
                )
            except Exception as sel_exc:
                _LOGGER.warning("MiBoxSocket: EntitySelector oluşturulurken hata: %s — fallback string input kullanılıyor", sel_exc)
                schema = vol.Schema(
                    {
                        vol.Required(CONF_MAC): str,
                        vol.Optional(CONF_NAME, default=""): str,
                        vol.Optional("media_player_entity_id", default=""): str,
                    }
                )

            return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

        except Exception as exc:
            # Herhangi bir beklenmeyen hata olursa logla ve kontrollü fallback form göster
            _LOGGER.exception("MiBoxSocket: async_step_user sırasında beklenmeyen hata: %s", exc)
            fallback_schema = vol.Schema(
                {
                    vol.Required(CONF_MAC): str,
                    vol.Optional(CONF_NAME, default=""): str,
                    vol.Optional("media_player_entity_id", default=""): str,
                }
            )
            return self.async_show_form(step_id="user", data_schema=fallback_schema, errors={"base": "unknown"})


    @staticmethod
    @callback
    def async_get_options_flow(entry):
        """Options flow handler'ını sınıf seviyesinde döndürür. (HA bununla çağırır.)"""
        return OptionsFlowHandler

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow — display name ve media_player seçimi için."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Options formu: display_name ve media_player_entity_id alır."""
        errors: dict[str, str] = {}
        data = dict(self.config_entry.data or {})
        current_options = dict(self.config_entry.options or {})

        default_display = current_options.get("display_name", "") or data.get(CONF_NAME, "")
        default_media = current_options.get("media_player_entity_id") or data.get("media_player_entity_id", "")

        try:
            if user_input is not None:
                new_options = {
                    "display_name": (user_input.get("display_name") or "").strip(),
                    "media_player_entity_id": user_input.get("media_player_entity_id") or "",
                }
                _LOGGER.debug("MiBoxSocket: Options kaydediliyor: %s", new_options)
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
                try:
                    await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                    _LOGGER.debug("MiBoxSocket: config entry reload edildi (entry_id=%s)", self.config_entry.entry_id)
                except Exception as reload_exc:
                    _LOGGER.exception("MiBoxSocket: config entry reload sırasında hata: %s", reload_exc)
                return self.async_create_entry(title="", data=new_options)

            # Formu oluştur (selector -> fallback string)
            try:
                media_selector = selector.EntitySelector({"domain": "media_player", "multiple": False})
                schema = vol.Schema(
                    {
                        vol.Optional("display_name", default=default_display): str,
                        vol.Optional("media_player_entity_id", default=default_media): media_selector,
                    }
                )
            except Exception as sel_exc:
                _LOGGER.warning("MiBoxSocket: OptionsFlow EntitySelector oluşturulurken hata: %s — fallback string input kullanılıyor", sel_exc)
                schema = vol.Schema(
                    {
                        vol.Optional("display_name", default=default_display): str,
                        vol.Optional("media_player_entity_id", default=default_media): str,
                    }
                )

            return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

        except Exception as exc:
            _LOGGER.exception("MiBoxSocket: OptionsFlow async_step_init sırasında beklenmeyen hata: %s", exc)
            fallback_schema = vol.Schema(
                {
                    vol.Optional("display_name", default=default_display): str,
                    vol.Optional("media_player_entity_id", default=default_media): str,
                }
            )
            return self.async_show_form(step_id="init", data_schema=fallback_schema, errors={"base": "unknown"})
