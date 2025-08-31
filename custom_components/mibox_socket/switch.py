"""Mibox Socket switch platform.

Bu switch, "cihazı açmak" için bluetooth pairing sekansını çalıştırır.
Pairing sekansı blocking olabilir; bu nedenle pexpect'i bir executor içinde çalıştırıyoruz
(HA ana döngüsünü bloke etmemek için).

Kullanıcı config flow ile eklenen her entry için bir switch oluşturulur.
"""

from __future__ import annotations

import logging
import shutil
from typing import Any

import pexpect  # manifest'te requirements olarak bildirildi
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr
from homeassistant.const import CONF_MAC, CONF_NAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Bu timeout'ları ihtiyaca göre ayarlayabilirsin
PAIRING_TIMEOUT = 30  # saniye

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Config entry için switch entity'sini ekle."""
    data = entry.data
    name = data.get(CONF_NAME)
    mac = data.get(CONF_MAC)

    async_add_entities([MiBoxSocketSwitch(hass, entry.entry_id, name, mac)], True)


class MiBoxSocketSwitch(SwitchEntity):
    """Mibox Socket için SwitchEntity implementasyonu."""

    def __init__(self, hass: HomeAssistant, entry_id: str, name: str, mac: str) -> None:
        """Nesne oluşturma."""
        self.hass = hass
        self._entry_id = entry_id
        self._name = name
        self._mac = mac.upper()
        self._available = True
        self._is_on = False
        # unique_id cihazın MAC'inden türetilir (iki entity aynı MAC'e sahip olamaz)
        self._attr_unique_id = f"mibox_{self._mac.replace(':', '')}"
        # device info, HA cihaz registrasyonunda gözükmesi için
        self._device_info = {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": "Xiaomi (Mibox)",
            "model": "Mibox (via bluetoothctl pairing)"
        }

    @property
    def device_info(self) -> dict:
        """Device registry göstergesi."""
        return self._device_info

    @property
    def name(self) -> str:
        """Entity ismi."""
        return self._name

    @property
    def available(self) -> bool:
        """Entity uygun mu (cihaz/donanım vs)."""
        return self._available

    @property
    def is_on(self) -> bool:
        """Switch durumu (kısa süreli: pairing running => True)."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch 'ON' komutu geldiğinde pairing işlemini yap."""
        # Önce temel kontroller: bluetoothctl var mı?
        if not shutil.which("bluetoothctl"):
            _LOGGER.error("bluetoothctl bulunamadi. Host'unuzda BlueZ/ bluetoothctl yüklü olmalı.")
            return

        # Durum bilgisi: işlem başladı
        self._is_on = True
        self.async_write_ha_state()

        # pairing işlemini blocking olarak executor'da çalıştır
        try:
            success = await self.hass.async_add_executor_job(self._pair_device_blocking, self._mac)
            if success:
                _LOGGER.info("Pairing işleminde başarı: %s", self._mac)
            else:
                _LOGGER.warning("Pairing başarısız: %s", self._mac)
        except Exception as exc:
            _LOGGER.exception("Pairing sırasında hata: %s", exc)
        finally:
            # Pairing işlemi tamamlandıktan sonra switch'i tekrar kapalı duruma getiriyoruz.
            # (Bu switch 'anlık tetikleme' mantığında çalışır.)
            self._is_on = False
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch OFF: Bu entegrasyonda off bir anlam ifade etmiyor, sadece UI için var.
        İleride unpair/forget eklemek istersen burada yap.
        """
        self._is_on = False
        self.async_write_ha_state()

    def _pair_device_blocking(self, mac: str) -> bool:
        """Blocking: pexpect ile bluetoothctl üç aşamalı işlemi yürütür.

        Bu fonksiyon executor içinde çalışır; HA event loop'unu bloke etmez.
        - bluetoothctl spawn edilir (eğer yoksa ImportError/RuntimeError atılır)
        - scan on komutu ile cihaz aranır
        - cihaz görüldüğünde pair <MAC> komutu gönderilir
        - pairing sonucu gözlenir (başarılı/başarısız)

        Return: True başarılır, False başarısız
        """
        try:
            # spawn bluetoothctl
            child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=PAIRING_TIMEOUT)
        except Exception as e:
            _LOGGER.exception("bluetoothctl başlatılamadı: %s", e)
            return False

        try:
            # Tarama başlat
            child.sendline("scan on")

            # Cihazın görünmesini bekle
            # bluetoothctl çıktı formatı ortamdan ortama değişebilir; burada MAC içeren bir satır arıyoruz.
            found = False
            try:
                # 1) önce cihazı görmeyi bekle (cihaz adresi çıktıda görünene kadar)
                index = child.expect([mac, pexpect.TIMEOUT], timeout=15)
                if index == 0:
                    found = True
                else:
                    found = False
            except pexpect.TIMEOUT:
                found = False

            if not found:
                _LOGGER.warning("Cihaz taramada bulunamadı: %s", mac)
                # scan kapat
                child.sendline("scan off")
                child.close()
                return False

            # Cihaz bulundu -> pair komutu
            child.sendline(f"pair {mac}")

            # Pairing sonucu olarak beklenen çıktı örnekleri:
            # "Pairing successful" veya "Failed to pair"
            # Hem İngilizce hem olası farklı çıktılara karşı timeout ile bekliyoruz.
            try:
                idx = child.expect(["Pairing successful", "Failed to pair", "AlreadyExists", pexpect.TIMEOUT], timeout=PAIRING_TIMEOUT)
                if idx == 0:
                    # Başarılı
                    child.sendline("scan off")
                    child.close()
                    return True
                else:
                    # Başarısız ya da timeout
                    _LOGGER.debug("Pairing sonucu beklenen şekilde gelmedi, idx=%s", idx)
                    child.sendline("scan off")
                    child.close()
                    return False
            except pexpect.ExceptionPexpect as e:
                _LOGGER.exception("Pairing sırasında bekleme hatası: %s", e)
                child.sendline("scan off")
                child.close()
                return False

        except Exception as exc:
            _LOGGER.exception("Pairing sürecinde beklenmeyen hata: %s", exc)
            try:
                child.close()
            except Exception:
                pass
            return False
