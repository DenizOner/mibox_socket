"""MiPower integration root.

This module only defines the async setup/unload entry points and lightweight
constants. Heavy or blocking work must not run at import time.

The integration:
 - Validates environment (bluetoothctl presence) during setup
 - Registers/unregisters platforms and services
 - Does not initiate pairing at import time
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

# Platforms this integration provides
PLATFORMS = ["switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MiPower from a config entry.

    We perform a runtime check for `bluetoothctl` (BlueZ) and show a persistent
    notification if it's missing so the user can take action. This check runs
    during setup, not at import time, to avoid blocking Home Assistant's event loop.
    """
    _LOGGER.debug("Setting up MiPower integration for entry %s", entry.entry_id)

    # Environment check: bluetoothctl must be available on PATH. If missing, we
    # reject the setup and show a persistent notification with guidance.
    if shutil.which("bluetoothctl") is None:
        _LOGGER.critical("bluetoothctl not found on system PATH. Cannot set up MiPower.")
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
        # Reject setup; user must install the missing dependency.
        return False

    # Register a device entry in Home Assistant device registry
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

    # Forward setup to platform(s)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a MiPower config entry and its platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok
