"""MiPower switch platform.

- SwitchEntity kullanır (UI'de tek bir toggle görünür).
- bluetoothctl (BlueZ CLI) öncelikli backend olarak seçildi — daha güvenilir
  Linux hostlarda; Bleak fallback olarak kullanılacak.
- Opsiyonel polling için DataUpdateCoordinator ile entegre çalışır.
- Cihaz kapalıyken entity 'unavailable' olmayacak; kullanıcı yine açma komutu verebilecek.
- Hatalar `extra_state_attributes["last_error"]` içinde gösterilir.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ON,
    STATE_PLAYING,
    STATE_IDLE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType

from .bluetoothctl import (
    BluetoothCtlClient,
    BluetoothCtlError,
    BluetoothCtlTimeoutError,
    BluetoothCtlNotFoundError,
    BluetoothCtlPairingRequestedError,
)
from .coordinator import MiPowerCoordinator
from .const import (
    DOMAIN,
    DEFAULT_ENTITY_ICON,
    CONF_MAC,
    CONF_MEDIA_PLAYER_ENTITY_ID,
    CONF_TIMEOUT_SEC,
    CONF_RETRY_COUNT,
    CONF_RETRY_DELAY_SEC,
    CONF_POLLING_ENABLED,
    CONF_POLLING_INTERVAL_SEC,
    CONF_DISCONNECT_DELAY_SEC,
    CONF_SLEEP_COMMAND_TYPE,
    DEFAULT_TIMEOUT_SEC,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY_SEC,
    DEFAULT_POLLING_ENABLED,
    DEFAULT_POLLING_INTERVAL_SEC,
    DEFAULT_DISCONNECT_DELAY_SEC,
    SLEEP_CMD_DISCONNECT,
    SLEEP_CMD_POWER_OFF,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_WAKE = "wake_device"
SERVICE_SLEEP = "sleep_device"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up MiPower switch platform from a config entry.

    - Read MAC and options
    - Prepare a client_factory (bluetoothctl preferred, bleak fallback)
    - Optionally start a coordinator for polling
    - Create MiPowerSwitch entity and add to hass
    """
    mac = entry.data[CONF_MAC]

    options = entry.options or {}
    timeout_sec = float(options.get(CONF_TIMEOUT_SEC, DEFAULT_TIMEOUT_SEC))
    retry_count = int(options.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT))
    retry_delay_sec = float(options.get(CONF_RETRY_DELAY_SEC, DEFAULT_RETRY_DELAY_SEC))
    polling_enabled = bool(options.get(CONF_POLLING_ENABLED, DEFAULT_POLLING_ENABLED))
    polling_interval_sec = float(
        options.get(CONF_POLLING_INTERVAL_SEC, DEFAULT_POLLING_INTERVAL_SEC)
    )
    disconnect_delay_sec = float(
        options.get(CONF_DISCONNECT_DELAY_SEC, DEFAULT_DISCONNECT_DELAY_SEC)
    )
    media_player_entity_id = options.get(CONF_MEDIA_PLAYER_ENTITY_ID)
    sleep_cmd_type = options.get(CONF_SLEEP_COMMAND_TYPE, SLEEP_CMD_DISCONNECT)

    # client_factory burada tanımlanır; import-time blocking oluşturulmaması için.
    def client_factory() -> BluetoothCtlClient:
        """Return preferred client.

        Quick-fix: prefer bluetoothctl (BlueZ CLI) which is often more reliable
        for simple connect/disconnect sequences on Linux hosts. If you later
        want to prefer Bleak again, revert this.
        """
        # 1) Try bluetoothctl subprocess-based client first (preferred)
        try:
            return BluetoothCtlClient(timeout_sec=timeout_sec)
        except Exception as exc:
            _LOGGER.debug("bluetoothctl client not usable: %s — will try Bleak", exc)

        # 2) Try Bleak as fallback (if bleak.py + bleak package present)
        try:
            from .bleak import BleakClient  # type: ignore
        except Exception:
            BleakClient = None  # type: ignore

        if BleakClient is not None:
            try:
                return BleakClient(timeout_sec=timeout_sec)  # type: ignore
            except BluetoothCtlError as exc:
                _LOGGER.debug("Bleak backend present but unusable: %s", exc)

        # 3) No usable backend found -> raise so setup can fail loudly
        raise BluetoothCtlError("No usable bluetooth backend (bluetoothctl nor bleak)")

    coordinator: Optional[MiPowerCoordinator] = None
    if polling_enabled:
        coordinator = MiPowerCoordinator(
            hass, mac=mac, client_factory=client_factory, interval_sec=polling_interval_sec
        )
        # İlk veri çekimini bekle; başarısızsa ConfigEntryNotReady/UpdateFailed tetiklenir.
        await coordinator.async_config_entry_first_refresh()

    switch = MiPowerSwitch(
        hass=hass,
        entry=entry,
        entry_id=entry.entry_id,
        mac=mac,
        client_factory=client_factory,
        retry_count=retry_count,
        retry_delay_sec=retry_delay_sec,
        disconnect_delay_sec=disconnect_delay_sec,
        polling_enabled=polling_enabled,
        media_player_entity_id=media_player_entity_id,
        sleep_cmd_type=sleep_cmd_type,
        coordinator=coordinator,
    )

    async_add_entities([switch])


class MiPowerSwitch(SwitchEntity):
    """MiPower switch entity."""

    _attr_has_entity_name = False
    _attr_icon = DEFAULT_ENTITY_ICON

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        entry_id: str,
        mac: str,
        client_factory: Callable[[], BluetoothCtlClient],
        retry_count: int,
        retry_delay_sec: float,
        disconnect_delay_sec: float,
        polling_enabled: bool,
        media_player_entity_id: Optional[str],
        sleep_cmd_type: str,
        coordinator: Optional[MiPowerCoordinator] = None,
    ) -> None:
        # Temel alanlar
        self.hass = hass
        self._entry_id = entry_id
        self._mac = mac
        self._client_factory = client_factory
        self._retry_count = retry_count
        self._retry_delay_sec = retry_delay_sec
        self._disconnect_delay_sec = disconnect_delay_sec
        self._polling_enabled = polling_enabled
        self._media_player_entity_id = media_player_entity_id
        self._sleep_cmd_type = sleep_cmd_type
        self._coordinator = coordinator

        # unique_id: sadece bir kez mac kullanılarak oluşturulur (alt çizgi ile)
        sanitized_mac = str(self._mac).lower().replace(":", "_")
        self._attr_unique_id = f"{DOMAIN}_{sanitized_mac}"

        # Görünen isim: kullanıcı verdi mi, yoksa mantıklı fallback mi?
        given_name: str = entry.data.get(CONF_NAME, f"MiPower {sanitized_mac}")
        self._given_name = given_name
        self._attr_name = given_name

        # Availability / state
        # Önemli: Cihaz kapalıysa bile kullanıcı açabilsin diye available'ı kapatmıyoruz.
        self._attr_available = True
        self._is_on_cached: Optional[bool] = None
        self._unsub_media_listener = None

        # Son hata mesajı, extra_state_attributes içinde gösterilecektir.
        self._last_error: Optional[str] = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._given_name,
            manufacturer="Xiaomi / Bluetooth",
            model="MiPower",
        )

    @property
    def is_on(self) -> Optional[bool]:
        """Return True if device considered on.

        Priority:
         1) Coordinator (polling) data if enabled
         2) Media player mapping if polling disabled and media player set
         3) Cached value
        """
        if self._polling_enabled and self._coordinator and self._coordinator.data is not None:
            conn = self._coordinator.data.get("connected")
            return bool(conn) if conn is not None else self._is_on_cached

        if self._media_player_entity_id:
            st = self.hass.states.get(self._media_player_entity_id)
            if st:
                return self._map_media_state_to_on(st.state)

        return self._is_on_cached

    def _map_media_state_to_on(self, state: StateType) -> bool:
        return str(state) in (STATE_ON, STATE_PLAYING, STATE_IDLE)

    async def async_added_to_hass(self) -> None:
        """If polling disabled and media_player configured, subscribe to its state."""
        if not self._polling_enabled and self._media_player_entity_id:
            st = self.hass.states.get(self._media_player_entity_id)
            if st:
                self._is_on_cached = self._map_media_state_to_on(st.state)

            self._unsub_media_listener = async_track_state_change_event(
                self.hass, [self._media_player_entity_id], self._handle_media_state_event
            )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_media_listener:
            try:
                self._unsub_media_listener()
            except Exception:
                _LOGGER.debug("Error while unsubscribing media listener", exc_info=True)
        self._unsub_media_listener = None

    @callback
    def _handle_media_state_event(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state:
            self._is_on_cached = self._map_media_state_to_on(new_state.state)
            self.async_write_ha_state()

    async def _retrying(self, coro_factory: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        """Retry helper: retry on certain transient errors."""
        attempt = 0
        while True:
            try:
                return await coro_factory()
            except (BluetoothCtlTimeoutError, BluetoothCtlNotFoundError) as exc:
                attempt += 1
                if attempt > self._retry_count:
                    _LOGGER.warning(
                        "Operation failed for %s after %s attempts: %s",
                        self._mac,
                        attempt,
                        exc,
                    )
                    raise
                _LOGGER.debug(
                    "Operation failed (%s). Retrying %s/%s in %.1fs",
                    exc,
                    attempt,
                    self._retry_count,
                    self._retry_delay_sec,
                )
                await asyncio.sleep(self._retry_delay_sec)

    async def _do_info(self) -> Dict[str, Any]:
        """Call client.info and normalize result to a dict."""
        client = self._client_factory()
        info = await client.info(self._mac)

        if isinstance(info, dict):
            return {
                "connected": info.get("connected"),
                "paired": info.get("paired"),
                "trusted": info.get("trusted"),
                "name": info.get("name"),
                "address": info.get("address"),
                "raw": info.get("raw"),
            }

        return {
            "connected": getattr(info, "connected", None),
            "paired": getattr(info, "paired", None),
            "trusted": getattr(info, "trusted", None),
            "name": getattr(info, "name", None),
            "address": getattr(info, "address", None),
            "raw": getattr(info, "raw", None),
        }

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        if self._last_error:
            attrs["last_error"] = self._last_error
        if self._coordinator is not None:
            # coordinator.last_update_success exists on DataUpdateCoordinator
            attrs["coordinator_last_update_success"] = getattr(self._coordinator, "last_update_success", None)
        return attrs

    async def _wake_sequence(self) -> bool:
        """Wake sequence:
        - if already connected -> success
        - try connect (primary backend, fallback to bluetoothctl if primary fails)
        - wait disconnect_delay
        - disconnect (best-effort)
        - verify via info()
        """
        try:
            info_before = await self._retrying(lambda: self._do_info())
            if info_before.get("connected") is True:
                _LOGGER.info("Device %s already connected/awake; no-op", self._mac)
                return True

            client = self._client_factory()

            # Try connecting with primary backend; on generic backend error try bluetoothctl fallback.
            try:
                await self._retrying(lambda: client.connect(self._mac))
            except BluetoothCtlPairingRequestedError:
                _LOGGER.warning("Pairing requested by device/controller; aborting wake for %s", self._mac)
                return False
            except BluetoothCtlError as exc:
                _LOGGER.warning("Primary backend connect failed for %s: %s. Trying bluetoothctl fallback.", self._mac, exc)
                try:
                    fallback_client = BluetoothCtlClient(timeout_sec=self._disconnect_delay_sec or 12.0)
                    await self._retrying(lambda: fallback_client.connect(self._mac))
                    client = fallback_client
                except BluetoothCtlPairingRequestedError:
                    _LOGGER.warning("Pairing requested during fallback; aborting wake for %s", self._mac)
                    return False
                except Exception as exc2:
                    _LOGGER.error("Fallback bluetoothctl connect also failed for %s: %s", self._mac, exc2)
                    return False

            # Let device process wake
            await asyncio.sleep(self._disconnect_delay_sec)

            # Best-effort disconnect
            try:
                await self._retrying(lambda: client.disconnect(self._mac))
            except BluetoothCtlError:
                _LOGGER.debug("Disconnect after wake failed; continuing (best-effort).")

            # Verify
            info_after = await self._retrying(lambda: self._do_info())
            connected = info_after.get("connected")
            # Many devices don't remain connected after wake; treat as success unless pairing/fatal error occurred.
            return True if connected is True or connected is False else True

        except BluetoothCtlPairingRequestedError:
            _LOGGER.warning("Pairing requested; abort wake for %s", self._mac)
            return False
        except (BluetoothCtlTimeoutError, BluetoothCtlNotFoundError) as exc:
            _LOGGER.warning("Wake failed for %s: %s", self._mac, exc)
            return False
        except BluetoothCtlError as exc:
            _LOGGER.error("Wake error for %s: %s", self._mac, exc)
            return False
        except Exception as exc:
            _LOGGER.error("Unexpected wake error for %s: %s", self._mac, exc)
            return False

    async def _sleep_sequence(self) -> bool:
        """Sleep sequence: disconnect or power_off depending on config."""
        client = self._client_factory()
        try:
            if self._sleep_cmd_type == SLEEP_CMD_POWER_OFF:
                try:
                    await self._retrying(lambda: client.power_off(None))
                except BluetoothCtlPairingRequestedError:
                    _LOGGER.warning("Pairing requested on power_off; aborting sleep for %s", self._mac)
                    return False
            else:
                await self._retrying(lambda: client.disconnect(self._mac))

            info = await self._retrying(lambda: self._do_info())
            connected = info.get("connected")
            return (connected is False) or (connected is None)

        except (BluetoothCtlTimeoutError, BluetoothCtlNotFoundError) as exc:
            _LOGGER.warning("Sleep failed for %s: %s", self._mac, exc)
            return False
        except BluetoothCtlError as exc:
            _LOGGER.error("Sleep error for %s: %s", self._mac, exc)
            return False
        except Exception as exc:
            _LOGGER.error("Unexpected sleep error for %s: %s", self._mac, exc)
            return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """User requested turn_on (wake). Keep entity available even on failure; record error."""
        try:
            ok = await self._wake_sequence()
            if ok:
                self._is_on_cached = True
                self._last_error = None
            else:
                self._last_error = "Wake sequence failed (device may be powered off or unreachable)."
        except Exception as exc:
            _LOGGER.exception("Error during async_turn_on for %s", self._mac)
            self._last_error = f"Exception during wake: {exc}"
        finally:
            # Keep entity visible/usable; reflect any state/attribute changes.
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """User requested turn_off (sleep). Keep entity available even on failure; record error."""
        try:
            ok = await self._sleep_sequence()
            if ok:
                self._is_on_cached = False
                self._last_error = None
            else:
                self._last_error = "Sleep sequence failed (device may be unreachable)."
        except Exception as exc:
            _LOGGER.exception("Error during async_turn_off for %s", self._mac)
            self._last_error = f"Exception during sleep: {exc}"
        finally:
            self.async_write_ha_state()

    # Convenience: expose entity-level services (if you later register them)
    async def async_service_wake(self) -> None:
        await self.async_turn_on()

    async def async_service_sleep(self) -> None:
        await self.async_turn_off()
