"""MiPower switch platform."""

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

def _ensure_hass_data_dict(hass: HomeAssistant) -> dict:
    existing = hass.data.get(DOMAIN)
    if existing is None or not isinstance(existing, dict):
        hass.data[DOMAIN] = {}
    return hass.data[DOMAIN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up switch for the config entry."""
    data = entry.data or {}
    opts = entry.options or {}
    mac = data.get(CONF_MAC)
    name = entry.title or opts.get(CONF_NAME) or f"MiPower {mac}"
    backend = opts.get(CONF_BACKEND, data.get(CONF_BACKEND, DEFAULT_BACKEND))
    scan_fallback = entry.options.get("scan_fallback", False)

    entity = MiPowerSwitch(hass=hass, entry=entry, name=name, mac=mac, backend=backend, scan_fallback=bool(scan_fallback))
    async_add_entities([entity], update_before_add=False)
    _LOGGER.debug("Added MiPower switch for %s (backend=%s scan_fallback=%s)", mac, backend, scan_fallback)


class MiPowerSwitch(SwitchEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, name: str, mac: str, backend: str, scan_fallback: bool = False):
        self.hass = hass
        self._entry = entry
        self._name = name
        self._mac = (mac or "").upper()
        self._backend = backend or DEFAULT_BACKEND
        self._scan_fallback = bool(scan_fallback)

        self._is_on = False
        self._available = True

        self._debounce_seconds = 4.0
        self._last_user_action_ts = 0.0

        self._timeout = entry.options.get("timeout_sec", DEFAULT_TIMEOUT_SEC)
        self._retry_count = entry.options.get("retry_count", DEFAULT_RETRY_COUNT)
        self._retry_delay = entry.options.get("retry_delay_sec", DEFAULT_RETRY_DELAY_SEC)

        store = _ensure_hass_data_dict(hass)
        store.setdefault(entry.entry_id, {})
        store_entry = store[entry.entry_id]
        store_entry.setdefault("last_attempts", [])
        self._store = store_entry

        self._unique_id = f"mipower_{self._mac.replace(':','').lower()}"
        self._entity_icon = "mdi:power"

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def available(self) -> bool:
        return self._available

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def icon(self) -> str:
        return self._entity_icon

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._name,
            manufacturer="MiPower",
            model="Mi Box (Bluetooth)",
        )

    def _append_attempt(self, success: bool, details: str | None = None):
        rec = {"ts": time.time(), "success": bool(success), "details": details}
        lst = self._store.setdefault("last_attempts", [])
        lst.insert(0, rec)
        if len(lst) > 20:
            del lst[20:]

    @callback
    def _set_state_and_publish(self, on: bool):
        self._is_on = bool(on)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        now = time.time()
        if now - self._last_user_action_ts < self._debounce_seconds:
            _LOGGER.debug("Debounce active for %s: ignoring turn_on", self._mac)
            return
        self._last_user_action_ts = now

        self._set_state_and_publish(True)
        self.hass.async_create_task(self._attempt_wake())

    async def async_turn_off(self, **kwargs: Any) -> None:
        now = time.time()
        if now - self._last_user_action_ts < self._debounce_seconds:
            _LOGGER.debug("Debounce active for %s: ignoring turn_off", self._mac)
            return
        self._last_user_action_ts = now

        self._set_state_and_publish(False)
        self.hass.async_create_task(self._attempt_sleep())

    async def _attempt_wake(self):
        mac = self._mac
        attempts = 0
        success = False
        last_err = None

        _LOGGER.debug("Wake start %s backend=%s scan_fallback=%s", mac, self._backend, self._scan_fallback)

        while attempts <= self._retry_count and not success:
            attempts += 1
            try:
                if self._backend == BACKEND_BLUETOOTHCTL:
                    rc, out, err = await self._bluetoothctl_connect(mac, timeout=self._timeout)
                    out_l = (out or "").lower()
                    if rc == 0 and "not available" not in out_l:
                        success = True
                        _LOGGER.debug("bluetoothctl connect ok for %s (attempt %d)", mac, attempts)
                    else:
                        last_err = f"rc={rc} out={out!r} err={err!r}"
                        _LOGGER.debug("bluetoothctl connect attempt %d failed: %s", attempts, last_err)
                        if "not available" in out_l and self._scan_fallback:
                            _LOGGER.debug("Attempting short scan fallback for %s", mac)
                            await self._bluetoothctl_command(["scan", "on"], timeout=1.5)
                            await asyncio.sleep(2.2)
                            await self._bluetoothctl_command(["scan", "off"], timeout=1.5)
                            rc2, out2, err2 = await self._bluetoothctl_connect(mac, timeout=self._timeout)
                            if rc2 == 0 and "not available" not in (out2 or "").lower():
                                success = True
                                last_err = None
                                _LOGGER.debug("scan fallback succeeded for %s", mac)
                else:
                    ok, msg = await self._bleak_connect_once(mac, timeout=self._timeout)
                    if ok:
                        success = True
                    else:
                        last_err = msg
            except Exception as exc:
                last_err = str(exc)
                _LOGGER.exception("Exception during wake attempt for %s attempt %d: %s", mac, attempts, exc)

            if not success and attempts <= self._retry_count:
                await asyncio.sleep(self._retry_delay)

        self._append_attempt(success, last_err)

        if success:
            await asyncio.sleep(1.0)
            reachable = await self._is_device_reachable()
            if reachable:
                self._set_state_and_publish(True)
            else:
                async_call_later(self.hass, 6, self._confirm_off_if_unreachable)
                self._set_state_and_publish(True)
        else:
            _LOGGER.warning("Wake failed for %s after %d attempts: %s", mac, attempts, last_err)
            self._set_state_and_publish(False)

    async def _attempt_sleep(self):
        mac = self._mac
        try:
            if self._backend == BACKEND_BLUETOOTHCTL:
                rc, out, err = await self._bluetoothctl_command(["disconnect", mac], timeout=self._timeout)
                _LOGGER.debug("bluetoothctl disconnect rc=%s out=%s", rc, out)
            else:
                ok, msg = await self._bleak_disconnect_once(mac, timeout=self._timeout)
                _LOGGER.debug("bleak disconnect ok=%s msg=%s", ok, msg)
        except Exception as exc:
            _LOGGER.exception("Exception during sleep for %s: %s", mac, exc)

        self._append_attempt(False, "sleep_requested")
        self._set_state_and_publish(False)

    async def _confirm_off_if_unreachable(self, now=None):
        reachable = await self._is_device_reachable()
        if not reachable:
            self._set_state_and_publish(False)
            self._append_attempt(False, "unreachable_after_wake")

    async def _is_device_reachable(self) -> bool:
        mac = self._mac
        if self._backend == BACKEND_BLUETOOTHCTL:
            try:
                rc, out, err = await self._bluetoothctl_command(["info", mac], timeout=3)
                out_low = (out or "").lower()
                if "connected: yes" in out_low:
                    return True
                if "not available" in out_low:
                    return False
                return False
            except Exception:
                return False
        else:
            ok, _ = await self._bleak_connect_once(mac, timeout=3)
            if ok:
                await asyncio.sleep(0.1)
                await self._bleak_disconnect_once(mac, timeout=1)
                return True
            return False

    async def _bluetoothctl_command(self, args: list[str], timeout: float = 8.0):
        bt = shutil.which("bluetoothctl")
        if not bt:
            raise RuntimeError("bluetoothctl not found")
        cmd = [bt] + args
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out_bytes, err_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            out_bytes, err_bytes = await proc.communicate()
            return proc.returncode or 1, (out_bytes or b"").decode(errors="ignore"), (err_bytes or b"").decode(errors="ignore")
        out = (out_bytes or b"").decode(errors="ignore")
        err = (err_bytes or b"").decode(errors="ignore")
        rc = proc.returncode if proc.returncode is not None else 0
        return rc, out, err

    async def _bluetoothctl_connect(self, mac: str, timeout: float = 8.0):
        return await self._bluetoothctl_command(["connect", mac], timeout=timeout)

    # Bleak helpers: use bleak-retry-connector if available
    async def _bleak_connect_once(self, mac: str, timeout: float = 8.0):
        try:
            from bleak import BleakClient
        except Exception as exc:
            return False, f"bleak not installed: {exc}"

        # Try bleak-retry-connector if available
        try:
            from bleak_retry_connector import establish_connection
        except Exception:
            establish_connection = None

        if establish_connection:
            try:
                client = await establish_connection(BleakClient, mac, timeout=timeout)
                # establish_connection returns a connected client
                await asyncio.sleep(0.2)
                await client.disconnect()
                return True, None
            except Exception as exc:
                return False, f"bleak_retry_connector error: {exc}"
        else:
            # fallback to plain BleakClient
            try:
                client = BleakClient(mac, timeout=timeout)
                await client.connect()
                await asyncio.sleep(0.25)
                await client.disconnect()
                return True, None
            except Exception as exc:
                return False, str(exc)

    async def _bleak_disconnect_once(self, mac: str, timeout: float = 5.0):
        ok, msg = await self._bleak_connect_once(mac, timeout=timeout)
        if ok:
            return True, None
        return False, msg
