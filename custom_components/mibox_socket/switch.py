
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
from homeassistant.helpers.event import async_track_state_change, async_call_later

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_TIMEOUT = 15
PAIRING_TIMEOUT = 30
DEFAULT_OFF_DEBOUNCE = 8  # saniye

ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Platform loader'ın beklediği modül-seviyesinde async_setup_entry."""
    data = entry.data or {}
    options = entry.options or {}
    display_name = options.get("display_name") or data.get(CONF_NAME) or f"MiBox_{data.get(CONF_MAC,'')}"
    mac = data.get(CONF_MAC)
    device_id = data.get("device_id")
    media_player_entity_id = data.get("media_player_entity_id") or data.get("media_player") or options.get("media_player_entity_id")
    async_add_entities([MiBoxSocketSwitch(hass, entry.entry_id, display_name, mac, device_id=device_id, media_player_entity_id=media_player_entity_id)], True)


class MiBoxSocketSwitch(SwitchEntity):
    """Mibox Socket switch entity with debounce for transient media_player state changes."""

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
        self._off_check_handle: Optional[Callable] = None  # async_call_later callback
        self._off_debounce_seconds: int = DEFAULT_OFF_DEBOUNCE
        self._forced_user_action = False  # kullanıcının async_turn_off isteğini ayırt etmek için

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
        """Registry'den device_id'ye bağlı entity id'leri getir."""
        if not self._device_id:
            return []
        registry = er.async_get(self.hass)
        entity_ids: List[str] = []
        for ent in registry.entities.values():
            if ent.device_id == self._device_id:
                entity_ids.append(ent.entity_id)
        _LOGGER.debug("MiBoxSocket: device_id=%s için bulunan entity_ids: %s", self._device_id, entity_ids)
        return entity_ids

    def _get_tracked_entity_ids(self) -> List[str]:
        """
        Hangi entity'leri izlediğimizi döndür.
        Öncelik: açıkça verilen media_player_entity_id. Yoksa device_id'ye bağlı tüm entity'ler.
        """
        if self._media_player_entity_id:
            return [self._media_player_entity_id]
        if self._device_id:
            return self._get_device_entity_ids()
        return []

    def _device_is_on(self) -> bool:
        """
        İzlenen entity'lerin herhangi biri 'on'/'playing'/'active' ise device on sayılır.
        """
        entity_ids = self._get_tracked_entity_ids()
        if not entity_ids:
            return False
        for entity_id in entity_ids:
            st = self.hass.states.get(entity_id)
            if st is None:
                continue
            if st.state in ("on", "playing", "active"):
                _LOGGER.debug("MiBoxSocket: %s durumu %s -> considered ON", entity_id, st.state)
                return True
        return False

    @property
    def is_on(self) -> bool:
        """
        Debounce mantığı: is_on doğrudan gerçek duruma bakar,
        ama otomatik UI off uygulaması sadece doğrulanmış off sonrası yapılır.
        (Burada dönen değer, sistemin gördüğü nihai durumdur.)
        """
        # Eğer takip edilen entity'ler varsa direkt device_is_on hesaplaması gösterilsin.
        # Ancak gerçek UI off uygulaması debounce sürecine bağlı olarak gecikme ile gerçekleşir.
        if self._device_id or self._media_player_entity_id:
            # Eğer şu anda off-check scheduled ise, halen biz ON göstermeye devam edebiliriz.
            if self._off_check_handle:
                # off check beklemede: geçici off görüldü, ama henüz doğrulanmadı.
                _LOGGER.debug("MiBoxSocket: off_check beklemede, is_on=%s (öncelik ON)", True)
                return True
            val = self._device_is_on()
            _LOGGER.debug("MiBoxSocket: is_on computed from device/media_player => %s", val)
            return val
        return self._is_on_internal

    async def async_added_to_hass(self) -> None:
        """Entity eklendiğinde abonelik ve off_debounce ayarını al."""
        # off_debounce seconds al (entry options varsa)
        try:
            entry = self.hass.config_entries.async_get_entry(self._entry_id)
            if entry:
                opt = entry.options.get("off_debounce")
                if opt is not None:
                    # try convert to int
                    try:
                        self._off_debounce_seconds = int(opt)
                    except Exception:
                        self._off_debounce_seconds = DEFAULT_OFF_DEBOUNCE
            _LOGGER.debug("MiBoxSocket: off_debounce_seconds=%s", self._off_debounce_seconds)
        except Exception:
            _LOGGER.debug("MiBoxSocket: entry lookup sırasında hata, off_debounce default kullanılıyor")

        tracked = self._get_tracked_entity_ids()
        if tracked:
            self._unsub_media = async_track_state_change(self.hass, tracked, self._async_media_state_changed)
            _LOGGER.debug("MiBoxSocket: tracked entities subscription kuruldu: %s", tracked)
        else:
            _LOGGER.debug("MiBoxSocket: hiç entity takip edilmiyor (device_id/media_player boş).")

        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_media:
            try:
                self._unsub_media()
            except Exception:
                pass
            self._unsub_media = None
        self._cancel_off_check()

    def _cancel_off_check(self) -> None:
        """Eğer off doğrulama için zamanlayıcı varsa iptal et."""
        if self._off_check_handle:
            try:
                self._off_check_handle()  # cancel callback
            except Exception:
                pass
            self._off_check_handle = None
            _LOGGER.debug("MiBoxSocket: off_check iptal edildi.")

    def _schedule_off_check(self) -> None:
        """off_debounce saniye sonra _confirm_off çalıştır."""
        self._cancel_off_check()
        _LOGGER.debug("MiBoxSocket: off_check %s saniye sonra planlanıyor.", self._off_debounce_seconds)
        self._off_check_handle = async_call_later(self.hass, self._off_debounce_seconds, self._confirm_off)

    async def _confirm_off(self, _now) -> None:
        """Debounce süresi sonra gerçekten off mı diye kontrol et; eğer off ise UI'ı kapat."""
        self._off_check_handle = None
        try:
            still_on = self._device_is_on()
            _LOGGER.debug("MiBoxSocket: _confirm_off kontrolü -> still_on=%s", still_on)
            if not still_on:
                # Gerçekten off ise UI'ı OFF yap (ancak otomatik olarak media_player.turn_off çağırmayız)
                _LOGGER.info("MiBoxSocket: doğrulanmış OFF, UI kapatılıyor.")
                self.async_write_ha_state()  # is_on property artık False dönecek
            else:
                _LOGGER.debug("MiBoxSocket: cihaz debounce süresi sonunda yine ON bulundu; UI ON kaldı.")
                # nothing to do (is_on remains True)
        except Exception as exc:
            _LOGGER.exception("MiBoxSocket: _confirm_off sırasında hata: %s", exc)

    @callback
    def _async_media_state_changed(self, entity_id, old_state, new_state) -> None:
        """
        Her media_player state change geldiğinde:
        - Eğer yeni durum 'on/playing/active' ise off-check iptal ve hemen ON göster.
        - Eğer yeni durum 'off' ise off_check zamanlayıp doğrulama yap.
        """
        _LOGGER.debug("MiBoxSocket: media state changed: %s %s -> %s", entity_id, old_state.state if old_state else None, new_state.state if new_state else None)

        # Eğer herhangi bir izlenen entity 'on' ise hemen ON göster ve bekleyen off_check iptal et
        if self._device_is_on():
            _LOGGER.debug("MiBoxSocket: en az bir izlenen entity ON durumda -> off_check iptal ediliyor ve UI ON tutuluyor.")
            self._cancel_off_check()
            self.async_write_ha_state()
            return

        # Eğer buraya geldiyse izlenen entity'lerin hepsi OFF görünüyor -> debounce ile doğrula
        _LOGGER.debug("MiBoxSocket: tüm izlenen entity'ler OFF görünüyor -> off_check planlanıyor.")
        self._schedule_off_check()
        # UI'ı hemen yazmıyoruz; confirm_off sonucuna göre update edilecek.

    async def async_turn_on(self, **kwargs: Any) -> None:
        """
        Kullanıcı switch'i açmak isteyince (manual ON).
        Burada pairing/power on işlemini yapıyoruz (eski davranış).
        """
        _LOGGER.debug("MiBoxSocket: turn_on çağrısı (mac=%s device_id=%s media_player_entity=%s)", self._mac, self._device_id, self._media_player_entity_id)

        # Kullanıcı eylemi olduğundan, önce off_check varsa iptal et
        self._cancel_off_check()

        if (self._device_id or self._media_player_entity_id) and self._device_is_on():
            _LOGGER.info("MiBoxSocket: bağlı cihaz zaten açık. Bluetooth komutu gönderilmeyecek.")
            self.async_write_ha_state()
            return

        if not shutil.which("bluetoothctl"):
            _LOGGER.error("MiBoxSocket: bluetoothctl bulunamadi; pairing yapılamaz.")
            return

        # internal state göster (momentary)
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
                # Off check iptal edilmiş olabilir; durumu yeniden göster
                self.async_write_ha_state()
            else:
                self._is_on_internal = False
                self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """
        Kullanıcı tarafından kapatma isteği:
         - Hedef media_player entity'lerine media_player.turn_off çağrılır hemen (blocking).
        """
        _LOGGER.debug("MiBoxSocket: turn_off çağrısı (user-request) mac=%s device_id=%s media_player_entity=%s", self._mac, self._device_id, self._media_player_entity_id)

        # iptal varsa iptal et
        self._cancel_off_check()

        targets: List[str] = []
        if self._media_player_entity_id:
            targets.append(self._media_player_entity_id)
        elif self._device_id:
            entity_ids = self._get_device_entity_ids()
            for eid in entity_ids:
                domain = eid.split(".", 1)[0]
                if domain == "media_player":
                    targets.append(eid)

        if targets:
            for target in targets:
                try:
                    await self.hass.services.async_call("media_player", "turn_off", {"entity_id": target}, blocking=True)
                    _LOGGER.info("MiBoxSocket: media_player.turn_off çağrıldı: %s", target)
                except Exception as exc:
                    _LOGGER.exception("MiBoxSocket: media_player.turn_off sırasında hata (%s): %s", target, exc)
            # state HA tarafından güncellenecek; yine de UI yazdır
            self.async_write_ha_state()
            return

        # fallback internal state toggle
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
