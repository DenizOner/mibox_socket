"""
custom_components/mibox_socket/switch.py

Mibox wake-up switch for Home Assistant.

Özellikler:
- Eğer config'te bir `media_player` entity_id verilmişse:
  - Switch'in gösterilen durumu (is_on) media_player'ın durumuna bağlı tutulur:
      media_player state != 'off'  -> switch görünümü: ON
      media_player state == 'off' -> switch görünümü: OFF
  - Kullanıcı switch'i açmaya çalıştığında (async_turn_on):
      - Eğer media_player zaten 'on' durumdaysa, bluetooth pairing komutu gönderilmez.
      - Eğer media_player 'off' ise, bluetooth pairing (wake) işlemi çalıştırılır.
- Pairing işlemi pexpect ile gerçekleştirilir; ağır bloklama işlemi olduğu için executor'da çalıştırılır.
- Kullanımı kolaylaştırmak için config hem eski yapı (device.mac) hem de düz (mac / media_player) altından destekler.
"""

import logging
import time
import asyncio

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

# Konfigürasyon anahtarları
CONF_MAC = "mac"
CONF_DEVICE = "device"
CONF_MEDIA_PLAYER = "media_player"
DEFAULT_NAME = "mibox_socket_switch"

# Platform schema: hem 'device: { mac: "...", media_player: "media_player.xyz" }'
# hem de top level olarak 'mac' ve 'media_player' kabul eder.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE): vol.Schema(
            {
                vol.Required(CONF_MAC): cv.string,
                vol.Optional(CONF_MEDIA_PLAYER): cv.entity_id,
                vol.Optional(CONF_NAME): cv.string,
            }
        ),
        vol.Optional(CONF_MAC): cv.string,
        vol.Optional(CONF_MEDIA_PLAYER): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """
    Platform kurulum fonksiyonu (senkron). HA platformu bunu çağırır.
    Burada config'ten MAC ve media_player alınır ve entity oluşturulur.
    """
    # Desteklenen yapı: configuration.yaml içinde ya:
    # switch:
    #   - platform: mibox_socket
    #     device:
    #       mac: "AA:BB:CC:DD:EE:FF"
    #       media_player: media_player.livingroom
    # veya doğrudan:
    #   - platform: mibox_socket
    #     mac: "AA:BB:CC:DD:EE:FF"
    #     media_player: media_player.livingroom

    # Öncelikle device dict varsa ondan al
    device_conf = config.get(CONF_DEVICE) or {}
    mac = device_conf.get(CONF_MAC) or config.get(CONF_MAC)
    media_player = device_conf.get(CONF_MEDIA_PLAYER) or config.get(CONF_MEDIA_PLAYER)
    name = device_conf.get(CONF_NAME) or config.get(CONF_NAME, DEFAULT_NAME)

    if not mac:
        _LOGGER.error("Mibox Socket: 'mac' konfigürasyonu gerekli.")
        return

    # Normalize: büyük harflerle MAC (daha kolay görüntüleme/karşılaştırma)
    mac = mac.upper()

    add_entities([MiboxSocketSwitch(hass, name, mac, media_player)], True)


class MiboxSocketSwitch(SwitchEntity):
    """
    Switch entity. Media player ile senkron halde davranır.
    """

    def __init__(self, hass, name, mac, media_player_entity_id):
        self.hass = hass
        self._name = name
        self._mac = mac
        self._media_player = media_player_entity_id  # örn. "media_player.tv"
        self._state = False  # True => switch HA'de ON görünür
        self._available = True
        self._unsub_media = None  # abonelik fonksiyonu
        self._log_prefix = f"[mibox_socket {self._mac}]"

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        """Switch'in anlık durumu (HA'ye gösterilen)."""
        return self._state

    @property
    def available(self):
        return self._available

    async def async_added_to_hass(self):
        """
        Entity HA'ye eklendiğinde çalışır.
        Eğer media_player belirtilmişse:
          - Başlangıç durumunu media_player'dan al.
          - media_player için state change aboneliği aç.
        """

        if self._media_player:
            # İlk durum kontrolü
            state_obj = self.hass.states.get(self._media_player)
            if state_obj:
                # Basit karar: media_player state 'off' ise switch kapalı; değilse açık.
                self._state = state_obj.state != "off"
                _LOGGER.debug("%s Başlangıç media_player durumu: %s => switch=%s", self._log_prefix, state_obj.state, self._state)
            else:
                # media_player entity bulunamadıysa false bırak
                self._state = False
                _LOGGER.warning("%s Belirtilen media_player '%s' bulunamadı.", self._log_prefix, self._media_player)

            # Durum değişikliklerini dinle
            # async_track_state_change(hass, entity_id or list, callback)
            self._unsub_media = async_track_state_change(
                self.hass, self._media_player, self._async_media_state_changed
            )

            # state yazdır
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        # Entity kaldırılırken aboneliği iptal et
        if self._unsub_media:
            self._unsub_media()
            self._unsub_media = None

    @callback
    def _async_media_state_changed(self, entity_id, old_state, new_state):
        """
        media_player durumu değiştiğinde çağrılır.
        new_state: State objesi (veya None)
        Logic: new_state.state != 'off' => bizim switch ON; 'off' => OFF.
        """
        if new_state is None:
            # entity silindiyse veya yoksa, switch'i kapatabiliriz
            _LOGGER.debug("%s media_player state became None (muhtemelen entity silindi).", self._log_prefix)
            self._state = False
            self.async_write_ha_state()
            return

        new_is_on = new_state.state != "off"
        if new_is_on != self._state:
            _LOGGER.info("%s media_player '%s' durumu '%s' => switch=%s", self._log_prefix, entity_id, new_state.state, new_is_on)
            self._state = new_is_on
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """
        Kullanıcı switch'i 'on' yapmak isteyince HA bunu çağırır.
        Davranış:
         - Eğer media_player konfigüre edilmişse ve media_player zaten açıksa => BT komutu gönderilmez.
         - Eğer media_player 'off' ise => pairing (wake) işlemi tetiklenir.
        """
        _LOGGER.debug("%s Kullanıcı turn_on çağrısı (media_player=%s)", self._log_prefix, self._media_player)

        if self._media_player:
            media_state = self.hass.states.get(self._media_player)
            if media_state and media_state.state != "off":
                # media player zaten çalışıyor: BT işlemine gerek yok
                _LOGGER.info("%s Media player '%s' açık (%s). Bluetooth komutu gönderilmeyecek.", self._log_prefix, self._media_player, media_state.state)
                # Switch görünümünü media_player ile uyumlu tut
                self._state = True
                self.async_write_ha_state()
                return

        # Buraya gelirse: ya media_player yok ya da media_player kapalı => pairing yap
        _LOGGER.info("%s Media player kapalı veya belirtilmemiş. Bluetooth wake/pairing başlatılıyor...", self._log_prefix)

        # pairing işlemi CPU bloklayacağı için executorda çalıştırıyoruz
        await self.hass.async_add_executor_job(self._do_pairing)

        # pairing'den sonra HA'de switch'i ON göster
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """
        Bu component aslında sadece 'wake' amaçlı; kapatma doğrudan kullanılamayabilir.
        Burada sadece state'i kapatıyoruz (UI için). Fiziksel kapatma ADB veya başka yol ile yapılmalı.
        """
        _LOGGER.debug("%s Kullanıcı turn_off çağrısı.", self._log_prefix)
        self._state = False
        self.async_write_ha_state()

    def _do_pairing(self):
        """
        Synchronous pairing routine. Burada `bluetoothctl` komutlarını kullanıyoruz.
        Orijinal projede pexpect kullanılmıştı; burada da pexpect ile benzer akışı kullanıyoruz.
        - scan on
        - pair <MAC>
        - trust <MAC>
        - scan off

        WARNING: Mibox ekranında eşleşme isteği çıkabilir; kullanıcının 'cancel' veya 'accept' yapması gerekebilir.
        """
        try:
            import pexpect
        except Exception as e:
            _LOGGER.exception("%s pexpect modülü bulunamadı: %s. Pairing yapılamaz.", self._log_prefix, e)
            return

        try:
            _LOGGER.debug("%s bluetoothctl başlatılıyor...", self._log_prefix)
            child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=30)
            # İlk prompt beklemesi (her sistemde farklı olabilir)
            time.sleep(0.5)
            # Başlangıçta scan aç
            child.sendline("scan on")
            # Kısa süre tarama yap
            time.sleep(2)

            _LOGGER.debug("%s pair komutu gönderiliyor: %s", self._log_prefix, self._mac)
            child.sendline(f"pair {self._mac}")

            # Bekleme: pairing sonucu mesajlarında farklı metinler olabilir (sistem, cihaz)
            try:
                idx = child.expect(
                    [
                        "Pairing successful",
                        "Pairing failed",
                        "Failed to pair",
                        "already paired",
                        "Authentication Failed",
                        pexpect.TIMEOUT,
                        pexpect.EOF,
                    ],
                    timeout=20,
                )
            except Exception as e:
                _LOGGER.debug("%s Pairing beklenirken timeout/exception: %s", self._log_prefix, e)
                idx = None

            # Basit kontrol: eğer pairing başarılı veya zaten eşli ise trust komutu ver
            # (eşlenmişse wake işlemi genelde başarılı olur)
            # Not: Bazı cihazlarda pairing isteği ekranda görünür ve manuel onay gerekir.
            _LOGGER.debug("%s pairing sonucu index=%s", self._log_prefix, idx)
            child.sendline(f"trust {self._mac}")
            time.sleep(0.5)
            child.sendline("scan off")
            time.sleep(0.2)
            child.close(force=True)
            _LOGGER.info("%s Pairing işlemi tamamlandı (komutlar gönderildi). Cihaz uyanmış olabilir.", self._log_prefix)
        except Exception as e:
            _LOGGER.exception("%s Pairing sırasında hata: %s", self._log_prefix, e)
