"""
Config Flow and Options Flow for MiPower.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    EntitySelector,
    EntitySelectorConfig,
)
from homeassistant.helpers import entity_registry as er, device_registry as dr

from .const import (
    DOMAIN,
    CONF_MAC,
    CONF_MEDIA_PLAYER_ENTITY_ID,
    CONF_TIMEOUT_SEC,
    CONF_RETRY_COUNT,
    CONF_RETRY_DELAY_SEC,
    CONF_POLLING_ENABLED,
    CONF_POLLING_INTERVAL_SEC,
    CONF_DISCONNECT_DELAY_SEC,
    CONF_SLEEP_COMMAND_TYPE,
    DEFAULT_TIMEOUT_SEC,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY_SEC,
    DEFAULT_POLLING_ENABLED,
    DEFAULT_POLLING_INTERVAL_SEC,
    DEFAULT_DISCONNECT_DELAY_SEC,
    MIN_TIMEOUT_SEC,
    MAX_TIMEOUT_SEC,
    MIN_RETRY_COUNT,
    MAX_RETRY_COUNT,
    MIN_RETRY_DELAY_SEC,
    MAX_RETRY_DELAY_SEC,
    MIN_POLLING_INTERVAL_SEC,
    MAX_POLLING_INTERVAL_SEC,
    MIN_DISCONNECT_DELAY_SEC,
    MAX_DISCONNECT_DELAY_SEC,
    SLEEP_CMD_DISCONNECT,
    SLEEP_CMD_POWER_OFF,
    normalize_mac,
    is_valid_mac,
)

_LOGGER = logging.getLogger(__name__)


def _mac_help_text(hass: HomeAssistant) -> str:
    # Localized via translations; key is mipower.config.mac_hint
    # Fallback here in case translations not loaded.
    return "Muhtemelen E0:B6:55:**:**:** ile başlar / Probably starts with E0:B6:55:**:**:**"


class MiPowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MiPower."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = normalize_mac(user_input[CONF_MAC])
            if not is_valid_mac(mac):
                errors[CONF_MAC] = "invalid_mac"
            else:
                # unique_id is normalized MAC
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_MAC: mac},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_MAC): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"mac_hint": self.hass.config.language},  # placeholder key only
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return MiPowerOptionsFlow(config_entry)


class MiPowerOptionsFlow(config_entries.OptionsFlow):
    """Options flow with a 'Gelişmiş Ayarlar' feel via grouped steps."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._options = dict(entry.options)

    async def _guess_media_player(self, hass: HomeAssistant) -> str | None:
        """
        Best-effort selection:
        - If any media_player's device registry connections contains a Bluetooth
          address starting with E0:B6:55, prefer that entity.
        - Otherwise, None.
        """
        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)

        # Iterate media_player entities
        for entity_id, entry in ent_reg.entities.items():
            if entry.domain != "media_player":
                continue
            device = dev_reg.devices.get(entry.device_id) if entry.device_id else None
            if not device:
                continue
            # Check connections for bluetooth
            for conn in device.connections:
                # connection tuple typically like ("bluetooth", "XX:YY:..")
                if len(conn) == 2 and conn[0] == "bluetooth":
                    mac = conn[1].upper()
                    if mac.startswith("E0:B6:55"):
                        return entity_id

        # Fallback: scan states for attributes (best-effort)
        for entity_id in ent_reg.entities:
            if entity_id.startswith("media_player."):
                st = hass.states.get(entity_id)
                if not st:
                    continue
                for key in ("bluetooth_address", "bt_mac", "mac", "address"):
                    val = st.attributes.get(key)
                    if isinstance(val, str) and val.upper().startswith("E0:B6:55"):
                        return entity_id

        return None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Entry point to present grouped options."""
        return await self.async_step_general()

    async def async_step_general(self, user_input: dict[str, Any] | None = None):
        """General options: timeouts, retry, disconnect delay, polling toggle."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate ranges
            timeout = float(user_input.get(CONF_TIMEOUT_SEC, DEFAULT_TIMEOUT_SEC))
            retry = int(user_input.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT))
            retry_delay = float(user_input.get(CONF_RETRY_DELAY_SEC, DEFAULT_RETRY_DELAY_SEC))
            disconnect_delay = float(user_input.get(CONF_DISCONNECT_DELAY_SEC, DEFAULT_DISCONNECT_DELAY_SEC))
            polling_enabled = bool(user_input.get(CONF_POLLING_ENABLED, DEFAULT_POLLING_ENABLED))

            if not (MIN_TIMEOUT_SEC <= timeout <= MAX_TIMEOUT_SEC):
                errors[CONF_TIMEOUT_SEC] = "out_of_range"
            if not (MIN_RETRY_COUNT <= retry <= MAX_RETRY_COUNT):
                errors[CONF_RETRY_COUNT] = "out_of_range"
            if not (MIN_RETRY_DELAY_SEC <= retry_delay <= MAX_RETRY_DELAY_SEC):
                errors[CONF_RETRY_DELAY_SEC] = "out_of_range"
            if not (MIN_DISCONNECT_DELAY_SEC <= disconnect_delay <= MAX_DISCONNECT_DELAY_SEC):
                errors[CONF_DISCONNECT_DELAY_SEC] = "out_of_range"

            if not errors:
                self._options.update(
                    {
                        CONF_TIMEOUT_SEC: timeout,
                        CONF_RETRY_COUNT: retry,
                        CONF_RETRY_DELAY_SEC: retry_delay,
                        CONF_DISCONNECT_DELAY_SEC: disconnect_delay,
                        CONF_POLLING_ENABLED: polling_enabled,
                    }
                )
                return await self.async_step_status()

        schema = vol.Schema(
            {
                vol.Required(CONF_TIMEOUT_SEC, default=self._options.get(CONF_TIMEOUT_SEC, DEFAULT_TIMEOUT_SEC)): float,
                vol.Required(CONF_RETRY_COUNT, default=self._options.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT)): int,
                vol.Required(CONF_RETRY_DELAY_SEC, default=self._options.get(CONF_RETRY_DELAY_SEC, DEFAULT_RETRY_DELAY_SEC)): float,
                vol.Required(CONF_DISCONNECT_DELAY_SEC, default=self._options.get(CONF_DISCONNECT_DELAY_SEC, DEFAULT_DISCONNECT_DELAY_SEC)): float,
                vol.Required(CONF_POLLING_ENABLED, default=self._options.get(CONF_POLLING_ENABLED, DEFAULT_POLLING_ENABLED)): bool,
            }
        )

        return self.async_show_form(
            step_id="general",
            data_schema=schema,
            errors=errors,
            description_placeholders={"mac_hint": "Muhtemelen E0:B6:55:**:**:** ile başlar"},
        )

    async def async_step_status(self, user_input: dict[str, Any] | None = None):
        """Status options: polling interval or media_player selection, sleep command."""
        errors: dict[str, str] = {}
        polling_enabled = bool(self._options.get(CONF_POLLING_ENABLED, DEFAULT_POLLING_ENABLED))

        if user_input is not None:
            if polling_enabled:
                polling_interval = float(user_input.get(CONF_POLLING_INTERVAL_SEC, DEFAULT_POLLING_INTERVAL_SEC))
                sleep_type = user_input.get(CONF_SLEEP_COMMAND_TYPE, SLEEP_CMD_DISCONNECT)
                if not (MIN_POLLING_INTERVAL_SEC <= polling_interval <= MAX_POLLING_INTERVAL_SEC):
                    errors[CONF_POLLING_INTERVAL_SEC] = "out_of_range"
                if sleep_type not in (SLEEP_CMD_DISCONNECT, SLEEP_CMD_POWER_OFF):
                    errors[CONF_SLEEP_COMMAND_TYPE] = "invalid_option"
                if not errors:
                    self._options.update(
                        {
                            CONF_POLLING_INTERVAL_SEC: polling_interval,
                            CONF_SLEEP_COMMAND_TYPE: sleep_type,
                            CONF_MEDIA_PLAYER_ENTITY_ID: None,
                        }
                    )
                    return self.async_create_entry(title="", data=self._options)
            else:
                media_player_entity_id = user_input.get(CONF_MEDIA_PLAYER_ENTITY_ID)
                sleep_type = user_input.get(CONF_SLEEP_COMMAND_TYPE, SLEEP_CMD_DISCONNECT)
                if not media_player_entity_id:
                    errors[CONF_MEDIA_PLAYER_ENTITY_ID] = "required"
                if sleep_type not in (SLEEP_CMD_DISCONNECT, SLEEP_CMD_POWER_OFF):
                    errors[CONF_SLEEP_COMMAND_TYPE] = "invalid_option"
                if not errors:
                    self._options.update(
                        {
                            CONF_MEDIA_PLAYER_ENTITY_ID: media_player_entity_id,
                            CONF_SLEEP_COMMAND_TYPE: sleep_type,
                            CONF_POLLING_INTERVAL_SEC: None,
                        }
                    )
                    return self.async_create_entry(title="", data=self._options)

        if polling_enabled:
            # Polling interval selector
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_POLLING_INTERVAL_SEC,
                        default=self._options.get(CONF_POLLING_INTERVAL_SEC, DEFAULT_POLLING_INTERVAL_SEC),
                    ): float,
                    vol.Required(
                        CONF_SLEEP_COMMAND_TYPE,
                        default=self._options.get(CONF_SLEEP_COMMAND_TYPE, SLEEP_CMD_DISCONNECT),
                    ): vol.In([SLEEP_CMD_DISCONNECT, SLEEP_CMD_POWER_OFF]),
                }
            )
        else:
            # media_player selector (required)
            suggested = self._options.get(CONF_MEDIA_PLAYER_ENTITY_ID) or (await self._guess_media_player(self.hass))
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_MEDIA_PLAYER_ENTITY_ID,
                        default=suggested or vol.UNDEFINED,
                    ): EntitySelector(EntitySelectorConfig(domain="media_player")),
                    vol.Required(
                        CONF_SLEEP_COMMAND_TYPE,
                        default=self._options.get(CONF_SLEEP_COMMAND_TYPE, SLEEP_CMD_DISCONNECT),
                    ): vol.In([SLEEP_CMD_DISCONNECT, SLEEP_CMD_POWER_OFF]),
                }
            )

        return self.async_show_form(
            step_id="status",
            data_schema=schema,
            errors=errors,
        )



