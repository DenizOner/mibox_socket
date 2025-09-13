"""MiPower integration __init__."""

from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up integration (static). Ensure hass.data slot present as plain dict."""
    if DOMAIN not in hass.data or not isinstance(hass.data[DOMAIN], dict):
        hass.data[DOMAIN] = {}
    _LOGGER.debug("MiPower base setup complete.")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a config entry: forward to platform(s)."""
    hass.data.setdefault(DOMAIN, {})
    # forward to platform(s) (switch)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("MiPower entry %s setup forwarded to platforms", entry.entry_id)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
