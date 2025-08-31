"""custom_components/mibox_socket/config_flow.py

Config flow ve Options flow.

Amaç:
- Kullanıcı integration eklerken MAC ve opsiyonel media_player seçim yapabilsin.
- Sonradan Integrations → Configure (Options) ile display_name (görünen ad) ve
  media_player entity'sini değiştirebilsin.
- Options kaydedildiğinde integration otomatik olarak reload edilsin, böylece
  switch entity'si yeni display name ve media_player seçimlerine göre hemen güncellensin.

NOT: Home Assistant'ın modern sürümlerinde `selector` API'si kullanılıyor; eğer sizin HA sürümünüz
çok eski ise ufak değişiklik gerekebilir. Ben yaygın HA sürümleriyle uyumlu ve HACS accepted
yaklaşıma uygun bir config_flow yazdım.
"""

from __future__ import annotations

from typing import Any
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
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
        """
        İlk adım: kullanıcıdan MAC (zorunlu) ve opsiyonel name / media_player seçimi al.
        media_player alanı entity selector olarak sunulur (isterseniz bu alanı boş bırakabilirsiniz).
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Kullanıcı formu gönderdi — create entry
            mac = user_input.get(CONF_MAC)
            name = user_input.get(CONF_NAME)
            media_player_entity_id = user_input.get("media_player_entity_id")

            # Basit validasyon: MAC sağlanmalı
            if not mac:
                errors["base"] = "mac_required"
            else:
                # Kaydet: data içinde MAC ve (isteğe bağlı) media_player_entity_id tutuyoruz.
                data = {
                    CONF_MAC: mac,
                    CONF_NAME: name or "",
                }
                if media_player_entity_id:
                    # Bu alanı data'ya koyuyoruz (switch.setup_entry code bundan faydalanıyor)
                    data["media_player_entity_id"] = media_player_entity_id

                # Create the config entry (title = name if provided, else domain + mac)
                title = name or f"MiBox {mac[-5:].replace(':','')}"
                return self.async_create_entry(title=title, data=data)

        # Formu göster
        # media_player için entity selector — kullanıcı varolan media_player entity'lerinden seçebilecek.
        schema = vol.Schema(
            {
                vol.Required(CONF_MAC): str,
                vol.Optional(CONF_NAME, default=""): str,
                vol.Optional("media_player_entity_id", default=""): selector.EntitySelector(
                    {"domain": "media_player", "multiple": False}
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    # Options flow handler
    async def async_get_options_flow(self, entry) -> "OptionsFlowHandler":
        return OptionsFlowHandler(self.hass, entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for MiBox integration (display name, media_player selection)."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """
        Options ana ekranı: display_name ve media_player_entity_id.
        Varsayılanlar mevcut entry.options veya entry.data değerlerinden alınır.
        """
        errors: dict[str, str] = {}

        # Varsayılan değerleri al
        current_options = dict(self.config_entry.options or {})
        data = dict(self.config_entry.data or {})

        default_display = current_options.get("display_name", "")
        # Eğer options'da yoksa data'dan (kurulum sırasında name alanına koyulmuş olabilir)
        if not default_display:
            default_display = data.get(CONF_NAME, "")

        default_media_player = current_options.get("media_player_entity_id") or data.get("media_player_entity_id", "")

        if user_input is not None:
            # Kullanıcı kaydetti — entry.options güncelle ve integration'ı reload et
            new_options = {
                "display_name": user_input.get("display_name", "").strip(),
                "media_player_entity_id": user_input.get("media_player_entity_id", "") or "",
            }

            _LOGGER.debug("MiBoxSocket: Options kaydediliyor: %s", new_options)

            # Update config entry options
            self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)

            # Reload the entry so async_setup_entry okuyup entity'leri güncelleyebilsin
            try:
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                _LOGGER.debug("MiBoxSocket: config entry reload edildi (entry_id=%s)", self.config_entry.entry_id)
            except Exception as exc:
                _LOGGER.exception("MiBoxSocket: config entry reload sırasında hata: %s", exc)

            return self.async_create_entry(title="", data=new_options)

        # Form göster
        schema = vol.Schema(
            {
                vol.Optional("display_name", default=default_display): str,
                vol.Optional("media_player_entity_id", default=default_media_player): selector.EntitySelector(
                    {"domain": "media_player", "multiple": False}
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
