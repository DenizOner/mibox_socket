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
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up MiPower from a config entry.

    Environment check: bluetoothctl must be available on PATH.
    If missing, we reject the setup and show a persistent notification with guidance.
    """
    if shutil.which("bluetoothctl") is None:
        _LOGGER.critical("bluetoothctl not found on system PATH. Cannot set up MiPower.")
        # Persistent Notification with TR/EN hint
        hass.components.persistent_notification.create(
            title="MiPower",
            message=(
                "bluetoothctl bulunamadı. Lütfen BlueZ paketini kurun ve Home Assistant'ı yeniden başlatın.\n"
                "- Debian/Ubuntu: sudo apt install bluez\n"
                "- Docker: Host üzerinde BlueZ/DBus ve uygun izinler gerekebilir.\n\n"
                "bluetoothctl not found. Please install BlueZ and restart Home Assistant.\n"
                "- Debian/Ubuntu: sudo apt install bluez\n"
                "- Docker: Ensure host BlueZ/DBus and permissions."
            ),
            notification_id=f"{DOMAIN}_missing_bluetoothctl",
        )
        # Reject setup
        return False

    # ✅ Hub cihazını device registry'ye ekle (hub:<MAC> olarak ayrı bir cihaz)
    mac = entry.data.get("mac", "UNKNOWN")
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"hub:{mac}")},
        manufacturer="Xiaomi / Bluetooth",
        model="MiPower",
        name=f"MiPower {mac}",  # Hub adı otomatik: MiPower + MAC
        sw_version="",
        entry_type="service",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload MiPower config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok



