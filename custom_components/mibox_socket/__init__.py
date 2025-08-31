"""Mibox Socket integration __init__.

Bu dosya entegrasyonun entry point'ini sağlar: config entry kurulumu / kaldırılması
ve hass.data içinde entegrasyon verisinin saklanması.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Integration-level setup.

    Bu örnekte hiçbir global setup gerekmediği için sadece hass.data yapısını hazırlarız.
    """
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Bir config entry (kullanıcı tarafından eklenen örnek) kurulduğunda çağrılır.

    Burada entry verisini saklayıp platformları yükleriz (switch).
    """
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # 'switch' platformunu bu entry için yükle
    hass.config_entries.async_setup_platforms(entry, ["switch"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entry kaldırılırken platformları kaldır."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["switch"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok