"""MiPower switch platform.

- Supports two backends: bluetoothctl (default) and bleak (if installed).
- Implements optimistic toggle, retry, confirmation checks and debounce.
- Uses asyncio subprocess for bluetoothctl so we do not block the event loop.

Place this file as:
  config/custom_components/mipower/switch.py
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_MAC, CONF_NAME

from .const import (
    DOMAIN,
    CONF_BACKEND,
    BACKEND_BLUETOOTHCTL,
    BACKEND_BLEAK,
    DEFAULT_BACKEND,
    DEFAULT_TIMEOUT_SEC,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY_SEC,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up MiPower switch entity from a config entry."""
    data = entry.data or {}
    opts = entry.options or {}

    mac = data.get(CONF_MAC)
    # Friendly name is entry.title (what user named when adding integration)
    name = entry.title or opts.get(CONF_NAME) or f"MiPower {mac}"

    backend = opts.get(CONF_BACKEND, data.get(CONF_BACKEND, DEFAULT_BACKEND))

    # Create entity
    entity = MiPowerSwitch(
        hass=hass,
        entry=entry,
        name=name,
        mac=mac,
        backend=backend,
    )

    async_add_entities([entity], update_before_add=False)
    _LOGGER.debug("MiPower switch entity created for %s (backend=%s)", mac, backend)


class MiPowerSwitch(SwitchEntity):
    """Switch e
