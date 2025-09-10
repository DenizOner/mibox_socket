"""
MiPower integration root.

- Validates environment (bluetoothctl presence)
- Registers/unregisters platforms and services
- No pairing is initiated by the integration at any time
"""

from __future__ import annotations

import logging
import shutil

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.components import persistent_notification

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up MiPower from a config entry.

    Environment check: bluetoothctl must be available on PATH.
    If missing, we reject the setup and show a persistent notification with guidance.
    """
    _LOGGER.debug("Setting up MiPower integration")
    
    if shutil.which("bluetoothctl") is None:
    _LOGGER.critical(
        "bluetoothctl not found on system PATH. Cannot set up MiPower."
    )
    message = (
        "bluetoothctl bulunamadı / bluetoothctl not found on PATH.\n\n"
        "Lütfen sisteminizde BlueZ (bluetoothctl) kurulu olduğundan emin olun.\n"
        "Please ensure BlueZ (bluetoothctl) is installed on the host."
    )
    persistent_notification.create(
        hass,
        message=message,
        title="MiPower",
        notification_id="mipower_bluetoothctl_missing",
    )
    return False
    
    mac = entry.data.get("mac", "UNKNOWN")
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, mac)},
        manufacturer="Xiaomi / Bluetooth",
        model="MiPower",
        name=f"MiPower {mac}",
        sw_version="",
        entry_type="service",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload MiPower config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok











