"""Diagnostics for MiPower (opt-in in HA UI). Sensitive values (MAC) are partially masked."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_MAC,
    CONF_MEDIA_PLAYER_ENTITY_ID,
    CONF_TIMEOUT_SEC,
    CONF_RETRY_COUNT,
    CONF_RETRY_DELAY_SEC,
    CONF_POLLING_ENABLED,
    CONF_POLLING_INTERVAL_SEC,
    CONF_DISCONNECT_DELAY_SEC,
    CONF_SLEEP_COMMAND_TYPE,
)


def _mask_mac(mac: str) -> str:
    """Show vendor + first bytes; mask rest for privacy."""
    if not mac:
        return "UNKNOWN"
    mac = mac.upper()
    parts = mac.split(":")
    if len(parts) == 6:
        return ":".join(parts[:4] + ["**", "**"])
    # fallback
    return mac[:8] + "**:**"


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    """Return diagnostics for a config entry (non-sensitive)."""
    data = dict(entry.data or {})
    opts = dict(entry.options or {})

    mac = data.get(CONF_MAC, "UNKNOWN")
    masked_mac = _mask_mac(mac)

    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "data": {
            CONF_MAC: masked_mac,
        },
        "options": {
            CONF_MEDIA_PLAYER_ENTITY_ID: opts.get(CONF_MEDIA_PLAYER_ENTITY_ID),
            CONF_TIMEOUT_SEC: opts.get(CONF_TIMEOUT_SEC),
            CONF_RETRY_COUNT: opts.get(CONF_RETRY_COUNT),
            CONF_RETRY_DELAY_SEC: opts.get(CONF_RETRY_DELAY_SEC),
            CONF_POLLING_ENABLED: opts.get(CONF_POLLING_ENABLED),
            CONF_POLLING_INTERVAL_SEC: opts.get(CONF_POLLING_INTERVAL_SEC),
            CONF_DISCONNECT_DELAY_SEC: opts.get(CONF_DISCONNECT_DELAY_SEC),
            CONF_SLEEP_COMMAND_TYPE: opts.get(CONF_SLEEP_COMMAND_TYPE),
        },
    }
