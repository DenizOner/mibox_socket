"""Diagnostics for MiPower integration.

This returns:
- config entry info (masked MAC)
- runtime status: backend, bluetoothctl presence, bleak availability
- last_attempt info from entity (if present)
- last few log-like messages maintained in hass.data (if any)

Place as: config/custom_components/mipower/diagnostics.py
"""

from __future__ import annotations

import shutil
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MAC, CONF_BACKEND, BACKEND_BLUETOOTHCTL, BACKEND_BLEAK, DOMAIN


def _mask_mac(mac: str) -> str:
    if not mac:
        return "UNKNOWN"
    mac = mac.upper()
    parts = mac.split(":")
    if len(parts) == 6:
        return ":".join(parts[:4] + ["**", "**"])
    return mac[:8] + "**:**"


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return comprehensive diagnostics for a config entry."""
    data = dict(entry.data or {})
    opts = dict(entry.options or {})

    mac = data.get(CONF_MAC) or opts.get(CONF_MAC)
    masked_mac = _mask_mac(mac)

    entry_store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    # backend checks
    backend = opts.get(CONF_BACKEND, data.get(CONF_BACKEND, None)) or "bluetoothctl"
    btctl_present = bool(shutil.which("bluetoothctl"))

    # bleak availability
    try:
        import importlib

        bleak_spec = importlib.util.find_spec("bleak")
        bleak_present = bool(bleak_spec)
    except Exception:
        bleak_present = False

    last_attempt = entry_store.get("last_attempt", None)

    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "data": {
            "mac_masked": masked_mac,
            "backend_configured": backend,
        },
        "runtime": {
            "bluetoothctl_present_on_host": btctl_present,
            "bleak_installed": bleak_present,
            "last_attempt": last_attempt,
            "timestamp_utc": time.time(),
        },
        "options": opts,
        "notes": "Diagnostics show local data only. For more details, check HA logs (custom_components.mipower).",
    }
