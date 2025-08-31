"""Switch entity for Mibox Socket with device-linked state detection."""

from __future__ import annotations

import logging
import shutil
from typing import Any, List

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_MAC, CONF_NAME

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_TIMEOUT = 15
PAIRING_TIMEOUT = 30

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Config entry için entity ekle. Pass device_id if present."""
    data = entry.data
    name = data.get(CONF_NAME)
    mac = data.get(CONF_MAC)
    device_id = data.get("device_id")  # may be None

    async_add_entities([MiBoxSocketSwitch(hass, entry.entry_id, name, mac, device_id)], True)


class MiBoxSocketSwitch(SwitchEntity):
    """Mibox Socket switch entity with optional device_id for state detection."""

    def __init__(self, hass: HomeAssistant, entry_id: str, name: str, mac: str, device_id: str | None = None) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._name = name
        self._mac = mac.upper()
        self._device_id = device_id
        self._available = True
        self._is_on = False
        self._attr_unique_id = f"mibox_{self._mac.replace(':', '')}"

        self._device_info = {
            "identifiers": {(DOMAIN, self._mac)},
            "name": self._name,
            "manufacturer": "Xiaomi (Mibox)",
            "model": "Mibox (via bluetoothctl pairing)",
        }

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
        """Return list of entity_ids associated with stored device_id."""
        if not self._device_id:
            return []
        registry = er.async_get(self.hass)
        # Collect entity_ids that have this device_id
        entity_ids: List[str] = []
        for ent in registry.entities.values():
            if ent.device_id == self._device_id:
                entity_ids.append(ent.entity_id)
        return entity_ids

    def _device_is_on(self) -> bool:
        """Check HA states for any entity attached to the device_id that indicate 'on'."""
        if not self._device_id:
            return False
        entity_ids = self._get_device_entity_ids()
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            # Common 'on' states for media_player: 'on', 'playing'
            if state.state in ("on", "playing", "active"):
                return True
        return False

    @property
    def is_on(self) -> bool:
        """If device_id present, use HA device state; otherwise use internal momentary state."""
        if self._device_id:
            return self._device_is_on()
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Trigger pairing (turn on action)."""
        if not shutil.which("bluetoothctl"):
            _LOGGER.error("bluetoothctl bulunamadi. Host'unuzda BlueZ/ bluetoothctl yüklü olmalı.")
            return

        # user sees ON while pairing runs
        self._is_on = True
        self.async_write_ha_state()

        try:
            success = await self.hass.async_add_executor_job(self._pair_device_blocking, self._mac)
            if success:
                _LOGGER.info("Pairing başarılı: %s", self._mac)
            else:
                _LOGGER.warning("Pairing başarısız: %s", self._mac)
        except Exception as exc:
            _LOGGER.exception("Pairing sırasında beklenmeyen hata: %s", exc)
        finally:
            # pairing tamamlandıktan sonra, eğer device_id varsa gerçek durumu HA üzerinden al
            if self._device_id:
                # small delay not added; rely on HA state updates that may come from integration
                pass
            self._is_on = False
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """No specific unpair functionality implemented (for now)."""
        self._is_on = False
        self.async_write_ha_state()

    def _pair_device_blocking(self, mac: str) -> bool:
        """Blocking pairing logic (pexpect)."""
        try:
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

            child.sendline(f"pair {mac}")

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
