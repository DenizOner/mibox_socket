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
    """Switch entity to wake/sleep device over Bluetooth.

    Design principles:
    - Optimistic update: when user toggles ON, return True immediately (UI responsive).
    - Background worker tries to actually wake device with retries.
    - Confirm device reachability after wake (short verification period).
    - Debounce: ignore new toggles for a short period after a user action.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, name: str, mac: str, backend: str):
        """Initialize the switch."""
        self.hass = hass
        self._entry = entry
        self._name = name
        self._mac = (mac or "").upper()
        self._backend = backend or DEFAULT_BACKEND

        # Entity state (optimistic + authoritative)
        self._is_on = False
        self._available = True

        # debounce: prevent immediate re-flip; seconds
        self._debounce_seconds = 4.0
        self._last_user_action_ts = 0.0

        # retry params (can be exposed as options later)
        self._timeout = entry.options.get("timeout_sec", DEFAULT_TIMEOUT_SEC)
        self._retry_count = entry.options.get("retry_count", DEFAULT_RETRY_COUNT)
        self._retry_delay = entry.options.get("retry_delay_sec", DEFAULT_RETRY_DELAY_SEC)

        # store last results for diagnostics
        self._last_attempt = None  # dict with timestamp, success, details
        # register storage in hass.data for diagnostics access
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].setdefault(entry.entry_id, {})
        hass.data[DOMAIN][entry.entry_id].setdefault("last_attempt", None)

        # device info / unique id
        self._unique_id = f"mipower_{self._mac.replace(':','').lower()}"

        # icon override (entity icon)
        self._entity_icon = "mdi:power"

    # --- HA Entity properties ---

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return availability of the entity."""
        return self._available

    @property
    def is_on(self) -> bool:
        """Return True if the device is considered ON."""
        return self._is_on

    @property
    def icon(self) -> str:
        """Return the material design icon for the entity (overrides device icon)."""
        return self._entity_icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for device registry (so the entity links to a device)."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._name,
            manufacturer="MiPower",
            model="Mi Box (Bluetooth)",
            via_device=None,
        )

    @callback
    def _set_last_attempt(self, success: bool, details: str | None = None):
        """Save last attempt info for diagnostics and logs."""
        now = time.time()
        rec = {"ts": now, "success": bool(success), "details": details}
        self._last_attempt = rec
        self.hass.data[DOMAIN][self._entry.entry_id]["last_attempt"] = rec

    # --- User actions (toggle) ---

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Handle user request to turn ON (wake)."""
        now = time.time()
        # debounce check:
        if now - self._last_user_action_ts < self._debounce_seconds:
            _LOGGER.debug("Debounce active for %s: ignoring turn_on", self._mac)
            return
        self._last_user_action_ts = now

        # Optimistic UI update
        self._is_on = True
        self.async_write_ha_state()

        # Schedule background wake attempt (don't block)
        self.hass.async_create_task(self._attempt_wake())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Handle user request to turn OFF (sleep/disconnect)."""
        now = time.time()
        if now - self._last_user_action_ts < self._debounce_seconds:
            _LOGGER.debug("Debounce active for %s: ignoring turn_off", self._mac)
            return
        self._last_user_action_ts = now

        # Optimistic UI update
        self._is_on = False
        self.async_write_ha_state()

        # Schedule background sleep attempt
        self.hass.async_create_task(self._attempt_sleep())

    # --- Operational helpers ---

    async def _attempt_wake(self):
        """Perform actual wake sequence with retries and confirmation."""
        mac = self._mac
        attempts = 0
        success = False
        last_err = None

        _LOGGER.debug("Starting wake sequence for %s using backend %s", mac, self._backend)

        while attempts <= self._retry_count and not success:
            attempts += 1
            try:
                if self._backend == BACKEND_BLUETOOTHCTL:
                    rc, out, err = await self._bluetoothctl_connect(mac, timeout=self._timeout)
                    if rc == 0 and not ("not available" in out.lower()):
                        success = True
                        _LOGGER.debug("bluetoothctl connect succeeded for %s (attempt %d)", mac, attempts)
                    else:
                        last_err = f"rc={rc} out={out!r} err={err!r}"
                        _LOGGER.debug("bluetoothctl connect attempt %d failed: %s", attempts, last_err)
                else:
                    # Bleak backend (if available)
                    ok, msg = await self._bleak_connect_once(mac, timeout=self._timeout)
                    if ok:
                        success = True
                        _LOGGER.debug("bleak connect succeeded for %s (attempt %d)", mac, attempts)
                    else:
                        last_err = msg
                        _LOGGER.debug("bleak connect attempt %d failed: %s", attempts, msg)
            except Exception as exc:
                last_err = str(exc)
                _LOGGER.exception("Exception during wake attempt for %s (attempt %d): %s", mac, attempts, exc)

            if not success:
                if attempts <= self._retry_count:
                    _LOGGER.debug("Retrying wake for %s in %s seconds (%d/%d)", mac, self._retry_delay, attempts, self._retry_count)
                    await asyncio.sleep(self._retry_delay)

        # Save attempt info for diagnostics
        self._set_last_attempt(success, last_err)

        # If succeeded, do a short confirmation check (is device connected/reachable?)
        if success:
            # Give a little time for device to register as connected
            await asyncio.sleep(1.2)
            reachable = await self._is_device_reachable()
            if not reachable:
                _LOGGER.debug("Wake succeeded but device not reachable after wait for %s", mac)
                # Some devices wake but immediately return to unavailable; in that case keep optimistic True for a few seconds
                # schedule a re-check: if still unreachable, revert state
                async_call_later(self.hass, 6, self._confirm_off_if_unreachable)
                self._is_on = True
                self.async_write_ha_state()
            else:
                _LOGGER.info("Device %s is reachable after wake", mac)
                self._is_on = True
                self.async_write_ha_state()
        else:
            # wake failed — revert optimistic state and log
            _LOGGER.warning("Wake failed for %s after %d attempts: %s", mac, attempts, last_err)
            self._is_on = False
            self.async_write_ha_state()

    async def _attempt_sleep(self):
        """Perform sleep (disconnect) sequence using bluetoothctl or bleak disconnect."""
        mac = self._mac
        try:
            if self._backend == BACKEND_BLUETOOTHCTL:
                rc, out, err = await self._bluetoothctl_command(["disconnect", mac], timeout=self._timeout)
                if rc == 0:
                    _LOGGER.info("Disconnected %s using bluetoothctl", mac)
                else:
                    _LOGGER.warning("bluetoothctl disconnect for %s returned rc=%s out=%s err=%s", mac, rc, out, err)
            else:
                ok, msg = await self._bleak_disconnect_once(mac, timeout=self._timeout)
                if ok:
                    _LOGGER.info("Disconnected %s using bleak", mac)
                else:
                    _LOGGER.warning("Bleak disconnect for %s failed: %s", mac, msg)
        except Exception as exc:
            _LOGGER.exception("Exception during sleep/disconnect for %s: %s", mac, exc)

        # After sleep attempt, mark as off (optimistic already set in async_turn_off)
        self._is_on = False
        self.async_write_ha_state()
        self._set_last_attempt(False, "sleep_requested")

    async def _confirm_off_if_unreachable(self, now=None):
        """Called via async_call_later to confirm and revert entity if unreachable."""
        reachable = await self._is_device_reachable()
        if not reachable:
            _LOGGER.debug("Confirm: device still unreachable, setting entity OFF for %s", self._mac)
            self._is_on = False
            self.async_write_ha_state()
            self._set_last_attempt(False, "unreachable_after_wake")
        else:
            _LOGGER.debug("Confirm: device reachable; leaving entity ON for %s", self._mac)

    # --- Backend helpers ---

    async def _is_device_reachable(self) -> bool:
        """Check device connectivity/reachability.

        For bluetoothctl backend, run `bluetoothctl info MAC` and look for 'Connected: yes'.
        For bleak backend, try to perform a short connect+disconnect with a very small timeout.
        """
        mac = self._mac
        if self._backend == BACKEND_BLUETOOTHCTL:
            try:
                rc, out, err = await self._bluetoothctl_command(["info", mac], timeout=3)
                out_low = (out or "").lower()
                if "connected: yes" in out_low:
                    return True
                # Some devices show no 'Connected' but show RSSI; treat 'not available' as not reachable
                if "not available" in out_low:
                    return False
                # If we see 'Connected: no' or nothing, return False
                return False
            except Exception as exc:
                _LOGGER.debug("Error checking reachable via bluetoothctl for %s: %s", mac, exc)
                return False
        else:
            # Bleak approach: attempt to connect quickly and disconnect
            ok, msg = await self._bleak_connect_once(mac, timeout=3)
            if ok:
                await asyncio.sleep(0.2)
                await self._bleak_disconnect_once(mac, timeout=1)
                return True
            return False

    async def _bluetoothctl_command(self, args: list[str], timeout: float = 8.0):
        """Run a single bluetoothctl <cmd> <args...> command via subprocess and return (rc, out, err)."""
        # Ensure bluetoothctl exists on host
        bt = shutil.which("bluetoothctl")
        if not bt:
            raise RuntimeError("bluetoothctl not found on host")

        cmd = [bt] + args
        _LOGGER.debug("Running bluetoothctl command: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            out_bytes, err_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            out_bytes, err_bytes = await proc.communicate()
            _LOGGER.debug("bluetoothctl command timeout, killed process")
            return proc.returncode or 1, (out_bytes or b"").decode(errors="ignore"), (err_bytes or b"").decode(errors="ignore")

        out = (out_bytes or b"").decode(errors="ignore")
        err = (err_bytes or b"").decode(errors="ignore")
        rc = proc.returncode if proc.returncode is not None else 0
        _LOGGER.debug("bluetoothctl rc=%s out=%s err=%s", rc, out.strip(), err.strip())
        return rc, out, err

    async def _bluetoothctl_connect(self, mac: str, timeout: float = 8.0):
        """Run bluetoothctl connect <mac> as a one-shot command."""
        return await self._bluetoothctl_command(["connect", mac], timeout=timeout)

    # --- Bleak helpers (best-effort; graceful degrade if libs missing) ---

    async def _bleak_connect_once(self, mac: str, timeout: float = 8.0):
        """Try to connect using bleak.BleakClient (best-effort). Return (True, None) or (False, message)."""
        try:
            from bleak import BleakClient
        except Exception as exc:
            return False, f"bleak not installed: {exc}"

        # Using BleakClient directly — note: bleak-retry-connector is recommended for robust connections.
        try:
            client = BleakClient(mac, timeout=timeout)
            await client.connect()
            # short connect then disconnect
            await asyncio.sleep(0.3)
            await client.disconnect()
            return True, None
        except Exception as exc:
            return False, str(exc)

    async def _bleak_disconnect_once(self, mac: str, timeout: float = 5.0):
        """Try to disconnect using bleak (best-effort). Return (True/False, msg)."""
        # Note: bleak does not provide 'disconnect by address' easily without keeping client object.
        # We'll attempt a connect+disconnect pattern to ensure device is disconnected, or rely on OS.
        ok, msg = await self._bleak_connect_once(mac, timeout=timeout)
        if ok:
            # we connected and then disconnected in that helper, so treat as success
            return True, None
        return False, msg
