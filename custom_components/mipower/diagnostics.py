"""Diagnostics for MiPower - extended."""

from __future__ import annotations

import shutil
import time
import platform
import socket
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_MAC

def _mask_mac(mac: str) -> str:
    if not mac:
        return "UNKNOWN"
    parts = mac.split(":")
    if len(parts) == 6:
        return ":".join(parts[:4] + ["**", "**"])
    return mac

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    data = dict(entry.data or {})
    opts = dict(entry.options or {})
    mac = data.get(CONF_MAC) or opts.get(CONF_MAC)
    masked_mac = _mask_mac(mac)

    store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    last_attempts = store.get("last_attempts", [])

    btctl_path = shutil.which("bluetoothctl")
    btctl_present = bool(btctl_path)
    # check mgmt_socket access by running `bluetoothctl show` non-blocking attempt (best-effort)
    mgmt_ok = True
    mgmt_error = None
    if btctl_present:
        try:
            import asyncio, subprocess
            proc = await asyncio.create_subprocess_exec(btctl_path, "show", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=2)
                if b"Unable to open mgmt_socket" in (out or b"") or b"Unable to open mgmt_socket" in (err or b""):
                    mgmt_ok = False
                    mgmt_error = "Unable to open mgmt_socket"
            except asyncio.TimeoutError:
                mgmt_ok = False
                mgmt_error = "timeout_running_bluetoothctl_show"
        except Exception as exc:
            mgmt_ok = False
            mgmt_error = str(exc)

    # bleak presence
    try:
        import importlib
        bleak_spec = importlib.util.find_spec("bleak")
        bleak_present = bool(bleak_spec)
    except Exception:
        bleak_present = False

    system_info = {
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
    }

    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "masked_mac": masked_mac,
        "backend_configured": opts.get("backend", None) or data.get("backend", "bluetoothctl"),
        "bluetoothctl": {
            "path": btctl_path,
            "present": btctl_present,
            "mgmt_socket_ok": mgmt_ok,
            "mgmt_error": mgmt_error,
        },
        "bleak": {"installed": bleak_present},
        "last_attempts": last_attempts,
        "system_info": system_info,
        "notes": [
            "If mgmt_socket_ok is False, container lacks access to BlueZ mgmt socket.",
            "To use bluetoothctl reliably for connect/disconnect your runtime must have host-level bluetooth access."
        ],
        "ts": time.time(),
    }
