"""
MiPower DataUpdateCoordinator for optional polling.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .bluetoothctl import (
    BluetoothCtlClient,
    BluetoothCtlError,
    BluetoothCtlTimeoutError,
    BluetoothCtlNotFoundError,
    BluetoothCtlPairingRequestedError,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MiPowerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    Coordinator holds the latest parsed info() results.

    data example:
    {
        "connected": True/False/None,
        "paired": True/False/None,
        "trusted": True/False/None,
        "name": str|None,
        "address": str|None,
        "raw": str,
    }
    """

    def __init__(
        self,
        hass: HomeAssistant,
        mac: str,
        client_factory: Callable[[], BluetoothCtlClient],
        interval_sec: float,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_coordinator_{mac}",
            update_interval=timedelta(seconds=interval_sec),
        )
        self._mac = mac
        self._client_factory = client_factory

    async def _async_update_data(self) -> dict[str, Any]:
        client = self._client_factory()
        try:
            info = await client.info(self._mac)
        except BluetoothCtlPairingRequestedError as exc:
            # Pairing is not desired; classify as warning and keep last data.
            raise UpdateFailed(f"Pairing requested: {exc}") from exc
        except (BluetoothCtlTimeoutError, BluetoothCtlNotFoundError) as exc:
            # Device unreachable/timeouts; not fatal, but update failed.
            raise UpdateFailed(str(exc)) from exc
        except BluetoothCtlError as exc:
            raise UpdateFailed(f"BluetoothCtl error: {exc}") from exc
        except Exception as exc:
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

        return {
            "connected": info.connected,
            "paired": info.paired,
            "trusted": info.trusted,
            "name": info.name,
            "address": info.address,
            "raw": info.raw,
        }
