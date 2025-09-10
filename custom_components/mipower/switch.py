"""
MiPower Switch platform.

Implements:
- Wake (turn_on): info -> connect -> short wait -> disconnect -> verify
- Sleep (turn_off): disconnect or power_off (per Options) -> verify
- State source:
  * If polling enabled: Coordinator's parsed 'connected' result
  * If polling disabled: Keep entity state in sync with a selected media_player's state
"""

from __future__ import annotations

import asyncio
import logging

from typing import Any, Callable, Coroutine

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_PLAYING, STATE_IDLE, STATE_OFF, CONF_NAME
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

# Entity services to bind on this platform (no parameters; target specific entity)
SERVICE_WAKE = "wake_device"
SERVICE_SLEEP = "sleep_device"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    mac = entry.data[CONF_MAC]

    # Resolve options with defaults
    options = entry.options or {}
    timeout_sec = float(options.get(CONF_TIMEOUT_SEC, DEFAULT_TIMEOUT_SEC))
    retry_count = int(options.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT))
    retry_delay_sec = float(options.get(CONF_RETRY_DELAY_SEC, DEFAULT_RETRY_DELAY_SEC))
    polling_enabled = bool(options.get(CONF_POLLING_ENABLED, DEFAULT_POLLING_ENABLED))
    polling_interval_sec = float(options.get(CONF_POLLING_INTERVAL_SEC, DEFAULT_POLLING_INTERVAL_SEC))
    disconnect_delay_sec = float(options.get(CONF_DISCONNECT_DELAY_SEC, DEFAULT_DISCONNECT_DELAY_SEC))
    media_player_entity_id = options.get(CONF_MEDIA_PLAYER_ENTITY_ID)
    sleep_cmd_type = options.get(CONF_SLEEP_COMMAND_TYPE, SLEEP_CMD_DISCONNECT)

    def client_factory() -> BluetoothCtlClient:
        return BluetoothCtlClient(timeout_sec=timeout_sec)

    coordinator: MiPowerCoordinator | None = None
    if polling_enabled:
        coordinator = MiPowerCoordinator(hass, mac=mac, client_factory=client_factory, interval_sec=polling_interval_sec)
        await coordinator.async_config_entry_first_refresh()

    switch = MiPowerSwitch(
        hass=hass,
        entry=entry,  # ✅ entry’yi geç
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
    _attr_has_entity_name = False
    _attr_icon = DEFAULT_ENTITY_ICON  # switch icon

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,  # ✅ entry’yi parametre olarak al
        entry_id: str,
        mac: str,
        client_factory: Callable[[], BluetoothCtlClient],
        retry_count: int,
        retry_delay_sec: float,
        disconnect_delay_sec: float,
        polling_enabled: bool,
        media_player_entity_id: str | None,
        sleep_cmd_type: str,
        coordinator: MiPowerCoordinator | None = None,
    ) -> None:
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

        self._attr_unique_id = f"{self._mac}_switch"
        self._given_name: str = entry.data.get(CONF_NAME, f"MiPower {self._mac}")
        self._attr_name = self._given_name
        self._attr_available = True
        self._is_on_cached: bool | None = None

        self._unsub_media_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._given_name,
            manufacturer="Xiaomi (Mi Box S family) / Bluetooth",
            model="MiPower",
        )

    @property
    def is_on(self) -> bool | None:
        # State source strategy:
        if self._polling_enabled and self._coordinator and self._coordinator.data is not None:
            conn = self._coordinator.data.get("connected")
            return bool(conn) if conn is not None else self._is_on_cached
        # Polling disabled: sync with media_player state (if provided)
        if self._media_player_entity_id:
            st = self.hass.states.get(self._media_player_entity_id)
            if st:
                return self._map_media_state_to_on(st.state)
        # Fallback to cached state
        return self._is_on_cached

    def _map_media_state_to_on(self, state: StateType) -> bool:
        # Consider playing/on/idle as "on"
        return str(state) in (STATE_ON, STATE_PLAYING, STATE_IDLE)

    async def async_added_to_hass(self) -> None:
    # Subscribe to media_player state changes if polling is disabled
    if not self._polling_enabled and self._media_player_entity_id:
        # Set initial cached state from media_player
        st = self.hass.states.get(self._media_player_entity_id)
        if st:
            self._is_on_cached = self._map_media_state_to_on(st.state)
        self._unsub_media_listener = async_track_state_change_event(
            self.hass, [self._media_player_entity_id], self._handle_media_state_event
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_media_listener:
            self._unsub_media_listener()
            self._unsub_media_listener = None

    @callback
    def _handle_media_state_event(self, event) -> None:
        # Update switch state based on media_player new state
        new_state = event.data.get("new_state")
        if new_state:
            self._is_on_cached = self._map_media_state_to_on(new_state.state)
            self.async_write_ha_state()

    async def _retrying(self, coro_factory: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        """
        Retry helper with simple fixed delay policy.
        """
        attempt = 0
        while True:
            try:
                return await coro_factory()
            except (BluetoothCtlTimeoutError, BluetoothCtlNotFoundError) as exc:
                attempt += 1
                if attempt > self._retry_count:
                    raise
                _LOGGER.warning("Operation failed (%s). Retrying %s/%s in %.1fs", exc, attempt, self._retry_count, self._retry_delay_sec)
                await asyncio.sleep(self._retry_delay_sec)

    async def _do_info(self) -> dict[str, Any]:
        client = self._client_factory()
        info = await client.info(self._mac)
        return {
            "connected": info.connected,
            "paired": info.paired,
            "trusted": info.trusted,
            "raw": info.raw,
            "name": info.name,
            "address": info.address,
        }

    async def _wake_sequence(self) -> bool:
        """
        Wake without pairing:
        - info -> if already connected/awake, no-op (success)
        - connect -> short wait -> disconnect
        - info verify -> connected(True) preferred but some devices won't keep it; treat as best-effort
        """
        try:
            info_before = await self._retrying(lambda: self._do_info())
            if info_before.get("connected") is True:
                _LOGGER.info("Device %s already connected/awake; no-op", self._mac)
                return True

            client = self._client_factory()
            # Pairing attempts must abort the flow
            try:
                await self._retrying(lambda: client.connect(self._mac))
            except BluetoothCtlPairingRequestedError:
                _LOGGER.warning(
                    "Pairing requested by device/controller; aborting wake for %s",
                    self._mac,
                )
                return False

            # Allow device to process the wake signal
            await asyncio.sleep(self._disconnect_delay_sec)

            # Best-effort disconnect
            try:
                await self._retrying(lambda: client.disconnect(self._mac))
            except BluetoothCtlError:
                _LOGGER.debug("Disconnect after wake failed; continuing (best-effort).")

            # Verify
            info_after = await self._retrying(lambda: self._do_info())
            # Many devices report disconnected after wake; consider success if no pairing or fatal errors occurred
            connected = info_after.get("connected")
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
        """
        Sleep:
        - If option is 'disconnect': best-effort disconnect
        - If option is 'power_off': best-effort power off (may affect controller; documented)
        - Verify with info()
        """
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
            # If disconnected or unknown, treat as 'off'
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
        self._attr_available = True
        ok = await self._wake_sequence()
        if ok:
            self._is_on_cached = True
        else:
            # Reflect problem
            self._attr_available = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_available = True
        ok = await self._sleep_sequence()
        if ok:
            self._is_on_cached = False
        else:
            self._attr_available = False
        self.async_write_ha_state()

    # Entity-bound services (no parameters)
    async def async_service_wake(self) -> None:
        await self.async_turn_on()

    async def async_service_sleep(self) -> None:
        await self.async_turn_off()











