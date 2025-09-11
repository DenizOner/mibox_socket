"""MiPower switch platform.

Bu dosya:
- SwitchEntity türeterek Home Assistant'ta tek bir toggle (aç/kapa) oluşturur.
- BLE backend (bleak) veya fallback olarak bluetoothctl kullanır.
- Opsiyonel polling için coordinator ile entegre çalışır.
- Kullanıcı tarafından verilen isim varsa kullanır; yoksa mantıklı bir fallback sağlar.

Not: Dosyada bolca açıklama satırı (comment) vardır; bunlar kodun amacını ve
neden yazıldığını açıklamak içindir.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Optional, Dict

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

# Service names (if you register platform-level services)
SERVICE_WAKE = "wake_device"
SERVICE_SLEEP = "sleep_device"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Config entry'den platformu kurar ve entity'leri ekler.

    - entry.data içinden MAC alınır
    - opsiyonlar okunur ve varsayılanlar uygulanır
    - polling aktifse coordinator kurulur ve ilk fetch beklenir
    - entity oluşturulur ve add_entities ile HA'ya eklenir
    """
    mac = entry.data[CONF_MAC]

    # Options (varsa) oku, yoksa default değerleri kullan.
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

    # client_factory burada lokal olarak tanımlanır; böylece import sırasında
    # blocking davranış oluşmaz ve runtime'da tercih edilen backend seçilebilir.
    def client_factory() -> BluetoothCtlClient:
        """Tercih sırası:
           1) BleakClient (eğer bleak.py ve bleak yüklü ise)
           2) BluetoothCtlClient (fallback)
        """
        try:
            from .bleak import BleakClient  # type: ignore
        except Exception:
            BleakClient = None  # type: ignore

        if BleakClient is not None:
            try:
                return BleakClient(timeout_sec=timeout_sec)  # type: ignore
            except BluetoothCtlError:
                _LOGGER.debug("Bleak backend mevcut ama kullanılamıyor; bluetoothctl fallback'a dönülüyor")

        return BluetoothCtlClient(timeout_sec=timeout_sec)

    # Polling etkinse coordinator kur (periyodik update için)
    coordinator: Optional[MiPowerCoordinator] = None
    if polling_enabled:
        coordinator = MiPowerCoordinator(
            hass, mac=mac, client_factory=client_factory, interval_sec=polling_interval_sec
        )
        # İlk veri çekme; hata durumunda ConfigEntryNotReady veya UpdateFailed tetiklenir.
        await coordinator.async_config_entry_first_refresh()

    # Entity oluştur ve HA'ya ekle
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
    """MiPower için SwitchEntity implementasyonu.

    - unique_id: `mipower_<mac_with_underscores>` formatında tekilleştirilir.
    - name: eğer kullanıcı config'te bir isim verdiyse onunla gösterilir,
            aksi halde "MiPower <mac>" (alt çizgi formatlı) kullanılır.
    - is_on: polling varsa coordinator verisinden, yoksa media_player veya cached state'den okunur.
    """

    _attr_has_entity_name = False
    _attr_icon = DEFAULT_ENTITY_ICON  # switch icon

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
        """Entity başlatma: alanların initial değerlerini ata."""
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

        # unique_id: tekrar etmeyecek ve HA entity registry ile çakışmayacak şekilde oluştur.
        sanitized_mac = str(self._mac).lower().replace(":", "_")
        self._attr_unique_id = f"{DOMAIN}_{sanitized_mac}"

        # Kullanıcının verdiği isim (config'de varsa) ya da mantıklı bir fallback.
        given_name: str = entry.data.get(CONF_NAME, f"MiPower {sanitized_mac}")
        self._given_name = given_name
        self._attr_name = given_name

        # Entity availability & cached state
        self._attr_available = True
        self._is_on_cached: Optional[bool] = None
        self._unsub_media_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        """Device registry için bilgiler döndür."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._given_name,
            manufacturer="Xiaomi / Bluetooth",
            model="MiPower",
        )

    @property
    def is_on(self) -> Optional[bool]:
        """Switch'in açık/kapalı bilgisini döndür.

        Öncelik:
         1. Polling etkin ve coordinator verisi varsa => coordinator.data['connected']
         2. Polling kapalıysa ve media_player belirtilmişse => media player state'e göre
         3. Yukarıdakiler yoksa cached value (önceki durum)
        """
        # 1) Polling varsa coordinator kullanalım
        if self._polling_enabled and self._coordinator and self._coordinator.data is not None:
            conn = self._coordinator.data.get("connected")
            return bool(conn) if conn is not None else self._is_on_cached

        # 2) Polling kapalıyken media_player fallback
        if self._media_player_entity_id:
            st = self.hass.states.get(self._media_player_entity_id)
            if st:
                return self._map_media_state_to_on(st.state)

        # 3) Fallback cached state
        return self._is_on_cached

    def _map_media_state_to_on(self, state: StateType) -> bool:
        """Media player state'lerini on/off'a eşle."""
        return str(state) in (STATE_ON, STATE_PLAYING, STATE_IDLE)

    async def async_added_to_hass(self) -> None:
        """Entity HASS'e eklendiğinde yapılacaklar: media_player dinleme kaydı ekle (polling kapalıysa)."""
        if not self._polling_enabled and self._media_player_entity_id:
            st = self.hass.states.get(self._media_player_entity_id)
            if st:
                self._is_on_cached = self._map_media_state_to_on(st.state)

            self._unsub_media_listener = async_track_state_change_event(
                self.hass, [self._media_player_entity_id], self._handle_media_state_event
            )

    async def async_will_remove_from_hass(self) -> None:
        """Entity silinirken abone kaydını temizle."""
        if self._unsub_media_listener:
            try:
                self._unsub_media_listener()
            except Exception:
                _LOGGER.debug("Media listener unsubscribe sırasında hata", exc_info=True)
        self._unsub_media_listener = None

    @callback
    def _handle_media_state_event(self, event) -> None:
        """Media player'dan gelen state change event'ini işle."""
        new_state = event.data.get("new_state")
        if new_state:
            self._is_on_cached = self._map_media_state_to_on(new_state.state)
            self.async_write_ha_state()

    async def _retrying(self, coro_factory: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        """Basit retry helper.

        - self._retry_count kadar deneme yapılır (0 => hiç retry yok).
        - Sadece belirlenen bazı hata tiplerinde retry denemesi yapılır.
        - Denemeler arasında self._retry_delay_sec kadar beklenir.
        """
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
        """Client backend üzerinden info() çağır ve normalize et."""
        client = self._client_factory()
        info = await client.info(self._mac)

        if isinstance(info, dict):
            # Beklenen temel anahtarlar: connected, paired, trusted, name, address, raw
            return {
                "connected": info.get("connected"),
                "paired": info.get("paired"),
                "trusted": info.get("trusted"),
                "name": info.get("name"),
                "address": info.get("address"),
                "raw": info.get("raw"),
            }

        # fallback: obje üzerinde attribute erişimi
        return {
            "connected": getattr(info, "connected", None),
            "paired": getattr(info, "paired", None),
            "trusted": getattr(info, "trusted", None),
            "name": getattr(info, "name", None),
            "address": getattr(info, "address", None),
            "raw": getattr(info, "raw", None),
        }

    async def _wake_sequence(self) -> bool:
        """Cihazı uyandırma akışı (pairing istenirse iptal edilir).

        Adımlar:
         - info() ile cihazın hali hazırda bağlı olup olmadığı kontrol edilir
         - connect() çağrılır (primary backend; başarısızsa fallback deneyebilir)
         - kısa bekleme (disconnect_delay)
         - disconnect() veya power_off()
         - info() ile doğrulama
        """
        try:
            info_before = await self._retrying(lambda: self._do_info())
            if info_before.get("connected") is True:
                _LOGGER.info("Device %s already connected/awake; no-op", self._mac)
                return True

            client = self._client_factory()

            # Connect: primary backend ile dene
            try:
                await self._retrying(lambda: client.connect(self._mac))
            except BluetoothCtlPairingRequestedError:
                _LOGGER.warning(
                    "Pairing requested by device/controller; aborting wake for %s", self._mac
                )
                return False
            except BluetoothCtlError as exc:
                # Primary backend (ör. bleak) başarısız ise bluetoothctl fallback deneyelim
                _LOGGER.warning(
                    "Primary backend connect failed for %s: %s. Trying bluetoothctl fallback.",
                    self._mac,
                    exc,
                )
                try:
                    fallback_client = BluetoothCtlClient(timeout_sec=self._disconnect_delay_sec or 12.0)
                    await self._retrying(lambda: fallback_client.connect(self._mac))
                    client = fallback_client
                except BluetoothCtlPairingRequestedError:
                    _LOGGER.warning(
                        "Pairing requested during fallback; aborting wake for %s", self._mac
                    )
                    return False
                except Exception as exc2:
                    _LOGGER.error(
                        "Fallback bluetoothctl connect also failed for %s: %s", self._mac, exc2
                    )
                    return False

            # Cihazın wake sinyalini işlemesi için kısa bekle
            await asyncio.sleep(self._disconnect_delay_sec)

            # Best-effort disconnect
            try:
                await self._retrying(lambda: client.disconnect(self._mac))
            except BluetoothCtlError:
                _LOGGER.debug("Disconnect after wake failed; continuing (best-effort).")

            # Verify
            info_after = await self._retrying(lambda: self._do_info())
            connected = info_after.get("connected")
            # Birçok cihaz wake sonrası bağlı kalmayabilir; burada pairing veya fatal hata yoksa success say
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
        """Cihazı uyutma akışı: disconnect veya power_off (opsiyona göre)."""
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
        """Entity-level turn_on: wake sequence çalıştır ve HA'ya durum bildir."""
        self._attr_available = True
        ok = await self._wake_sequence()
        if ok:
            self._is_on_cached = True
            self.async_write_ha_state()
        else:
            self._attr_available = False
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Entity-level turn_off: sleep sequence çalıştır ve HA'ya durum bildir."""
        self._attr_available = True
        ok = await self._sleep_sequence()
        if ok:
            self._is_on_cached = False
            self.async_write_ha_state()
        else:
            self._attr_available = False
            self.async_write_ha_state()

    # Basit entity-bound servisler (parametresiz)
    async def async_service_wake(self) -> None:
        await self.async_turn_on()

    async def async_service_sleep(self) -> None:
        await self.async_turn_off()
