"""MiPower Switch entity.

This file provides the SwitchEntity that controls/wakes/sleeps the target device.
It is backend-agnostic: uses either bluetoothctl wrapper or bleak wrapper depending on config.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CONF_MAC,
    CONF_NAME,
    CONF_BACKEND,
    CONF_MEDIA_PLAYER_ENTITY_ID,
    BACKEND_BLUETOOTHCTL,
    BACKEND_BLEAK,
    DEFAULT_BACKEND,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY_SEC,
    DEFAULT_DISCONNECT_DELAY_SEC,
    DEFAULT_POLLING_ENABLED,
)
from . import bluetoothctl as bluetoothctl_mod
from . import bleak as bleak_mod

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up switch from config entry."""
    data = entry.data
    options = entry.options or {}

    mac = data.get(CONF_MAC)
    name = data.get(CONF_NAME) or options.get(CONF_NAME) or f"MiPower {mac}"
    backend = options.get(CONF_BACKEND, data.get(CONF_BACKEND, DEFAULT_BACKEND))
    media_player_entity_id = options.get(CONF_MEDIA_PLAYER_ENTITY_ID)

    # client factory selects backend at runtime
    def client_factory():
        if backend == BACKEND_BLUETOOTHCTL:
            return "bluetoothctl"
        return "bleak"

    switch = MiPowerSwitch(
        hass=hass,
        entry=entry,
        mac=mac,
        name=name,
        client_factory=client_factory,
        backend=backend,
        media_player_entity_id=media_player_entity_id,
    )

    async_add_entities([switch], update_before_add=True)


class MiPowerSwitch(SwitchEntity):
    """Single toggle switch for MiPower."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        mac: str,
        name: str,
        client_factory: Callable[[], str],
        backend: str,
        media_player_entity_id: Optional[str] = None,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._mac = mac
        self._name = name
        self._client_factory = client_factory
        self._backend = backend
        self._media_player_entity_id = media_player_entity_id

        sanitized_mac = str(self._mac).lower().replace(":", "_")
        self._attr_unique_id = f"{DOMAIN}_{sanitized_mac}"
        self._attr_name = name
        self._attr_icon = "mdi:power-settings"

        self._available = True
        # cache boolean state; start with False so UI shows off rather than unknown
        self._is_on_cached: bool = False
        self._last_error: Optional[str] = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._name,
            manufacturer="Custom Integration",
            model="MiPower",
        )

    @property
    def is_on(self) -> bool:
        """Return on/off state."""
        # Prefer cached boolean; external polling/coordinator can update
        return bool(self._is_on_cached)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        if self._last_error:
            attrs["last_error"] = self._last_error
        attrs["backend"] = self._backend
        attrs["mac"] = self._mac
        return attrs

    async def async_update(self) -> None:
        """Fetch current device status (best-effort)."""
        try:
            if self._backend == BACKEND_BLUETOOTHCTL:
                info = await bluetoothctl_mod.info(self._mac)
                connected_raw = info.get("connected")
                self._is_on_cached = connected_raw in (True, "yes", "true", "1", "True")
            else:
                info = await bleak_mod.info(self._mac)
                self._is_on_cached = info.get("connected", False)
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            # keep old cached value; mark available True so UI can toggle
            _LOGGER.debug("async_update exception for %s: %s", self._mac, exc)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake / connect to the device."""
        self._last_error = None
        try:
            if self._backend == BACKEND_BLUETOOTHCTL:
                # First attempt: direct connect
                await bluetoothctl_mod.connect(self._mac)
                # small pause to let BlueZ update state
                await asyncio.sleep(1.0)
                info = await bluetoothctl_mod.info(self._mac)
                connected_raw = info.get("connected")
                self._is_on_cached = connected_raw in (True, "yes", "true", "1", "True")
            else:
                # Bleak path: get client via bleak.connect (which may use retry connector)
                client = await bleak_mod.connect(self._mac)
                # if we have a client, assume device awake; then disconnect after short wait
                try:
                    await asyncio.sleep(1.0)
                    self._is_on_cached = await client.is_connected()
                finally:
                    await bleak_mod.disconnect(client)
        except Exception as exc:
            _LOGGER.warning("Wake failed for %s: %s", self._mac, exc)
            self._last_error = str(exc)
            # Keep cached state unchanged
        finally:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Sleep / disconnect."""
        self._last_error = None
        try:
            if self._backend == BACKEND_BLUETOOTHCTL:
                await bluetoothctl_mod.disconnect(self._mac)
                await asyncio.sleep(0.6)
                info = await bluetoothctl_mod.info(self._mac)
                connected_raw = info.get("connected")
                self._is_on_cached = connected_raw in (True, "yes", "true", "1", "True")
                if self._is_on_cached:
                    # still connected -> treat as off attempt failed
                    self._last_error = "Disconnect reported still connected"
            else:
                # For Bleak, attempt a direct connection then disconnect (best-effort)
                try:
                    client = await bleak_mod.connect(self._mac)
                except Exception:
                    client = None
                if client:
                    await bleak_mod.disconnect(client)
                    self._is_on_cached = False
        except Exception as exc:
            _LOGGER.warning("Sleep failed for %s: %s", self._mac, exc)
            self._last_error = str(exc)
        finally:
            self.async_write_ha_state()
