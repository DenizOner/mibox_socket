"""custom_components/mibox_socket/switch.py

Güncelleme: eğer entry.data['name'] bir media_player entity id'si ise
bunu media_player_entity_id olarak kullanır ve switch'in display adını düzeltir.
"""

from __future__ import annotations

import logging
import shutil
from typing import Any, List, Callable, Optional
import re

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_TIMEOUT = 15
PAIRING_TIMEOUT = 30

ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Config entry için entity ekle ve entry.data içeriğini akıllıca işle."""
    data = entry.data or {}
    raw_name = data.get(CONF_NAME) or ""
    mac = data.get(CONF_MAC)
    # Bazı eski/kullanıcı varyasyonları: 'media_player' veya 'media_player_entity_id'
    media_player_entity_id = data.get("media_player") or data.get("media_player_entity_id")

    # Eğer media_player bilgisi yoksa ve name bir entity_id pattern'ine uyuyorsa,
    # name muhtemelen media_player olarak kaydedilmiş — bunu kullan.
    display_name = raw_name or f"mibox_{(mac or '')}"
    if not media_player_entity_id and isinstance(raw_name, str) and raw_name.startswith("media_player.") and ENTITY_ID_RE.match(raw_name):
        media_player_entity_id = raw_name
        # display_name'i daha kullanıcı-dostu yap: "MiBox (felix...)" veya MAC'in son kısmı
        if mac:
            display_name = f"MiBox {mac[-5:].replace(':', '')}"
        else:
            # entity id'den okunabilir bölüm çıkar (ör. media_player.felix_s_mi_box_4 -> felix_s_mi_box_4)
            display_name = "MiBox " + raw_name.split(".", 1)[1]

    _LOGGER.debug(
        "MiBoxSocket async_setup_entry: entry_id=%s raw_name=%s -> display_name=%s media_player=%s mac=%s",
        entry.entry_id, raw_name, display_name, media_player_entity_id, mac
    )

    async_add_entities([MiBoxSocketSwitch(hass, entry.entry_id, display_name, mac, device_id=data.get("device_id"), media_player_entity_id=media_player_entity_id)], True)


class MiBoxSocketSwitch(SwitchEntity):
    """Mibox Socket switch entity with robust detection (device_id or media_player entity)."""

    def __init__(self, hass: HomeAssistant, entry_id: str, name: str, mac: Optional[str], device_id: Optional[str] = None, media_player_entity_id: Optional[str] = None) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._name = name
        self._mac = (mac or "").upper()
        self._device_id = device_id
        self._media_player_entity_id = media_player_entity_id
        self._available = True
        self._is_on_internal = False
        self._attr_unique_id = f"mibox_{(self._mac or '').replace(':', '')}"
        self._device_info = {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": "Xiaomi (Mibox)",
            "model": "Mibox (bluetooth wake)",
        }
        self._unsub_media: Optional[Callable] = None

    @property
    def device_info(self) -> dict:
        return self._device_info

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        return self._available

    def _get_device_entity_ids(self) -> List[str]:
        """Registry'den device_id'ye bağlı entity id'leri getir ve logla."""
        if not self._device_id:
            return []
        registry = er.async_get(self.hass)
        entity_ids: List[str] = []
        for ent in registry.entities.values():
            if ent.device_id == self._device_id:
                entity_ids.append(ent.entity_id)
        _LOGGER.debug("MiBoxSocket: device_id=%s için bulunan entity_ids: %s", self._device_id, entity_ids)
        return entity_ids

    def _device_is_on(self) -> bool:
        """
        Device id veya media_player_entity_id üzerinden on/playing/active kontrolleri yap.
        Hangi entity'nin hangi durumda olduğu loglanır.
        """
        # Öncelik: açıkça verilen media_player_entity_id
        if self._media_player_entity_id:
            st = self.hass.states.get(self._media_player_entity_id)
            _LOGGER.debug("MiBoxSocket: kontrol edilen media_player_entity_id=%s state=%s", self._media_player_entity_id, st.state if st else "None")
            if st and st.state in ("on", "playing", "active"):
                return True
            return False

        # device_id bazlı kontrol
        if not self._device_id:
            return False
        entity_ids = self._get_device_entity_ids()
        for entity_id in entity_ids:
            st = self.hass.states.get(entity_id)
            if not st:
                _LOGGER.debug("MiBoxSocket: entity %s state None", entity_id)
                continue
            _LOGGER.debug("MiBoxSocket: device entity check: %s -> %s", entity_id, st.state)
            if st.state in ("on", "playing", "active"):
                _LOGGER.debug("MiBoxSocket: device considered ON because %s is %s", entity_id, st.state)
                return True
        return False

    @property
    def is_on(self) -> bool:
        """Eğer media_player veya device_id tanımlıysa HA'daki gerçek durumu döndürür."""
        if self._device_id or self._media_player_entity_id:
            try:
                val = self._device_is_on()
                _LOGGER.debug("MiBoxSocket: is_on computed from device/media_player => %s", val)
                return val
            except Exception as e:
                _LOGGER.exception("MiBoxSocket: is_on hesaplanırken hata: %s", e)
                return False
        return self._is_on_internal

    async def async_added_to_hass(self) -> None:
        """Entity eklendiğinde gerekli abonelikleri kur."""
        # Eğer media_player_entity_id varsa ona abone ol
        if self._media_player_entity_id:
            _LOGGER.debug("MiBoxSocket: media_player_entity_id ile abonelik kuruluyor: %s", self._media_player_entity_id)
            self._unsub_media = async_track_state_change(self.hass, self._media_player_entity_id, self._async_media_state_changed)
        elif self._device_id:
            entity_ids = self._get_device_entity_ids()
            if entity_ids:
                _LOGGER.debug("MiBoxSocket: device_id aboneliği kuruluyor entity_ids=%s", entity_ids)
                self._unsub_media = async_track_state_change(self.hass, entity_ids, self._async_media_state_changed)
            else:
                _LOGGER.debug("MiBoxSocket: device_id var ama entity bulunamadı (device_id=%s).", self._device_id)
        # ilk UI güncellemesi
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_media:
            try:
                self._unsub_media()
            except Exception:
                pass
            self._unsub_media = None

    @callback
    def _async_media_state_changed(self, entity_id, old_state, new_state) -> None:
        _LOGGER.debug("MiBoxSocket: bağlı entity %s durumu değişti: %s -> %s", entity_id, old_state.state if old_state else None, new_state.state if new_state else None)
        # UI'ı güncelle
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch ON talebi geldiğinde önce device/media_player durumuna bak, açıksa pairing/komut atlama."""
        _LOGGER.debug("MiBoxSocket: turn_on çağrısı (mac=%s device_id=%s media_player_entity=%s)", self._mac, self._device_id, self._media_player_entity_id)

        # Eğer bağlı cihaz zaten açık görünüyorsa pairing gönderme
        if (self._device_id or self._media_player_entity_id) and self._device_is_on():
            _LOGGER.info("MiBoxSocket: bağlı cihaz zaten açık. Bluetooth komutu gönderilmeyecek.")
            self.async_write_ha_state()
            return

        if not shutil.which("bluetoothctl"):
            _LOGGER.error("MiBoxSocket: bluetoothctl bulunamadi; pairing yapılamaz.")
            return

        # Eğer internal (device_id yok) anlık ON göstermek istiyorsak
        if not (self._device_id or self._media_player_entity_id):
            self._is_on_internal = True
            self.async_write_ha_state()

        _LOGGER.info("MiBoxSocket: pairing başlatılıyor (MAC=%s)", self._mac)
        try:
            success = await self.hass.async_add_executor_job(self._pair_device_blocking, self._mac)
            if success:
                _LOGGER.info("MiBoxSocket: pairing başarılı %s", self._mac)
            else:
                _LOGGER.warning("MiBoxSocket: pairing başarısız %s", self._mac)
        except Exception as exc:
            _LOGGER.exception("MiBoxSocket: pairing sırasında hata: %s", exc)
        finally:
            # pairing sonrası UI güncellemesi
            if self._device_id or self._media_player_entity_id:
                self.async_write_ha_state()
            else:
                self._is_on_internal = False
                self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on_internal = False
        self.async_write_ha_state()

    def _pair_device_blocking(self, mac: str) -> bool:
        """Blocking pairing logic (pexpect kullanıyor)."""
        try:
            import pexpect  # type: ignore
        except Exception as e:
            _LOGGER.exception("MiBoxSocket: pexpect import edilemedi: %s", e)
            return False

        try:
            child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=PAIRING_TIMEOUT)
        except Exception as e:
            _LOGGER.exception("MiBoxSocket: bluetoothctl başlatılamadı: %s", e)
            return False

        try:
            try:
                child.sendline("agent NoInputNoOutput")
                child.expect(["Agent registered", pexpect.TIMEOUT], timeout=5)
            except Exception:
                pass
            try:
                child.sendline("default-agent")
            except Exception:
                pass

            child.sendline("scan on")
            found = False
            try:
                child.expect([mac, pexpect.TIMEOUT], timeout=SCAN_TIMEOUT)
                found = mac in (child.before or "") or mac in (child.after or "")
            except Exception:
                found = False

            if not found:
                _LOGGER.warning("MiBoxSocket: cihaz taramada bulunamadi (MAC=%s)", mac)
                try:
                    child.sendline("scan off")
                except Exception:
                    pass
                child.close()
                return False

            child.sendline(f"pair {mac}")
            try:
                idx = child.expect([r"Pairing successful", r"Paired: yes", r"Failed to pair", r"AuthenticationFailed", r"AlreadyExists", pexpect.TIMEOUT], timeout=PAIRING_TIMEOUT)
                if idx in (0, 1):
                    try:
                        child.sendline(f"trust {mac}")
                    except Exception:
                        pass
                    try:
                        child.sendline("scan off")
                    except Exception:
                        pass
                    child.close()
                    return True
                else:
                    _LOGGER.debug("MiBoxSocket: pairing beklenen konumda tamamlanmadi, idx=%s", idx)
                    try:
                        child.sendline("scan off")
                    except Exception:
                        pass
                    child.close()
                    return False
            except Exception as e:
                _LOGGER.exception("MiBoxSocket: pairing esnasında bekleme hatasi: %s", e)
                try:
                    child.sendline("scan off")
                except Exception:
                    pass
                child.close()
                return False
        except Exception as exc:
            _LOGGER.exception("MiBoxSocket: pairing sürecinde beklenmeyen exception: %s", exc)
            try:
                child.close()
            except Exception:
                pass
            return False
