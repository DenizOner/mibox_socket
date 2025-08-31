"""Switch entity for Mibox Socket.

Bu switch tetiklendiğinde bluetoothctl ile pairing sekansını çalıştırır.
Pairing blocking/IO-bound bir işlem olduğundan executor içinde çalıştırılır.
"""

from __future__ import annotations

import logging
import shutil
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_MAC, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Pairing işlemi için bekleme süreleri
SCAN_TIMEOUT = 15  # cihazın taramada görünmesi için bekleme (saniye)
PAIRING_TIMEOUT = 30  # pairing işleminin tamamlanması için bekleme (saniye)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Config entry için entity ekle."""
    data = entry.data
    name = data.get(CONF_NAME)
    mac = data.get(CONF_MAC)

    async_add_entities([MiBoxSocketSwitch(hass, entry.entry_id, name, mac)], True)


class MiBoxSocketSwitch(SwitchEntity):
    """Mibox Socket switch entity."""

    def __init__(self, hass: HomeAssistant, entry_id: str, name: str, mac: str) -> None:
        """Nesne yaratma ve başlangıç ayarları."""
        self.hass = hass
        self._entry_id = entry_id
        self._name = name
        self._mac = mac.upper()
        self._available = True
        self._is_on = False

        # unique_id -> domain + mac
        self._attr_unique_id = f"mibox_{self._mac.replace(':', '')}"

        # Device registry'de görünmesi için device_info
        self._device_info = {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": "Xiaomi (Mibox)",
            "model": "Mibox (via bluetoothctl pairing)",
        }

    @property
    def device_info(self) -> dict:
        """Device registry metadata."""
        return self._device_info

    @property
    def name(self) -> str:
        """Entity name."""
        return self._name

    @property
    def available(self) -> bool:
        """Entity uygunluğu (host/donanım)."""
        return self._available

    @property
    def is_on(self) -> bool:
        """Switch durumu."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch ON tetiklendiğinde pairing işlemini başlat."""
        # bluetoothctl var mı kontrolü
        if not shutil.which("bluetoothctl"):
            _LOGGER.error("bluetoothctl bulunamadi. Host'unuzda BlueZ/ bluetoothctl yüklü olmalı.")
            return

        # UI'de geçici ON göster
        self._is_on = True
        self.async_write_ha_state()

        # Blocking pairing fonksiyonunu executor içinde çalıştır
        try:
            success = await self.hass.async_add_executor_job(self._pair_device_blocking, self._mac)
            if success:
                _LOGGER.info("Pairing başarılı: %s", self._mac)
            else:
                _LOGGER.warning("Pairing başarısız: %s", self._mac)
        except Exception as exc:
            _LOGGER.exception("Pairing sırasında beklenmeyen hata: %s", exc)
        finally:
            # Anlık tetikleme mantığı: işlem tamamlandığında switch'i tekrar kapalı göster
            self._is_on = False
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch OFF: Bu entegrasyonda gerçek 'off' operasyonu yok; UI için state toggle yapıyoruz."""
        self._is_on = False
        self.async_write_ha_state()

    def _pair_device_blocking(self, mac: str) -> bool:
        """Blocking pairing süreci (pexpect ile bluetoothctl).

        Bu fonksiyon executor içinde çalıştırılır; burada sync/IO koda izin var.

        Mantık:
        1. bluetoothctl spawn
        2. agent NoInputNoOutput + default-agent (bazı cihazlar PIN istemez)
        3. scan on -> cihazın MAC çıktıda görünmesini bekle
        4. pair <MAC> -> pairing sonucu için çeşitli pattern'ler bekle
        5. pairing başarılıysa trust <MAC> (opsiyonel)
        6. scan off -> kapanış
        """
        try:
            # pexpect import'u fonksiyon içinde: manifest'teki requirement yüklü değilse
            # modül import hatası tüm entegrasyonu bozmamalı
            import pexpect  # type: ignore
        except Exception as e:
            _LOGGER.exception("pexpect import edilemedi: %s", e)
            return False

        try:
            child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=PAIRING_TIMEOUT)
        except Exception as e:
            _LOGGER.exception("bluetoothctl başlatılamadı: %s", e)
            return False

        try:
            # Agent oluştur ve default-agent yap (PIN gerekmeyen eşleşme için)
            try:
                child.sendline("agent NoInputNoOutput")
                child.expect(["Agent registered", pexpect.TIMEOUT], timeout=5)
            except Exception:
                # Bazı bluetoothctl versiyonlarında farklı çıktı olabilir; fail etmiyoruz.
                pass

            try:
                child.sendline("default-agent")
            except Exception:
                pass

            # Taramayı başlat
            child.sendline("scan on")

            # Cihazın taramada görünmesini bekle (MAC içeren satır)
            found = False
            try:
                # 15s içinde MAC içeren bir satır gözükürse devam et
                child.expect([mac, pexpect.TIMEOUT], timeout=SCAN_TIMEOUT)
                # Eğer ilk pattern (mac) yakalandıysa found True olur.
                # pexpect.match veya index kontrolü zor; basitça çıktı kontrolü ile devam ediyoruz.
                found = mac in child.before or mac in child.after
            except pexpect.TIMEOUT:
                found = False

            if not found:
                _LOGGER.warning("Cihaz taramada bulunamadi (MAC: %s).", mac)
                try:
                    child.sendline("scan off")
                except Exception:
                    pass
                child.close()
                return False

            # Pair komutu
            child.sendline(f"pair {mac}")

            # Pairing sonucu için olası pattern'ler (case-insensitive benzeri)
            # Başarılı: "Pairing successful", "Paired: yes"
            # Hatalar: "Failed to pair", "AuthenticationFailed", "AlreadyExists"
            try:
                idx = child.expect(
                    [
                        r"Pairing successful",
                        r"Paired: yes",
                        r"Failed to pair",
                        r"AuthenticationFailed",
                        r"AlreadyExists",
                        pexpect.TIMEOUT,
                    ],
                    timeout=PAIRING_TIMEOUT,
                )
                # idx 0 veya 1 -> başarılı
                if idx in (0, 1):
                    # Güvenilirlik için trust et
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
                    _LOGGER.debug("Pairing beklenen konumda tamamlanmadi, idx=%s", idx)
                    try:
                        child.sendline("scan off")
                    except Exception:
                        pass
                    child.close()
                    return False
            except Exception as e:
                _LOGGER.exception("Pairing esnasında bekleme hatasi: %s", e)
                try:
                    child.sendline("scan off")
                except Exception:
                    pass
                child.close()
                return False

        except Exception as exc:
            _LOGGER.exception("Pairing sürecinde beklenmeyen exception: %s", exc)
            try:
                child.close()
            except Exception:
                pass
            return False
