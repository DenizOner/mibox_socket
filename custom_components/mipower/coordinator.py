"""MiPower DataUpdateCoordinator for optional polling."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable, Dict

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


class MiPowerCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator that holds the latest parsed info() results.

    Data structure example:
    {
        "connected": True|False|None,
        "paired": True|False|None,
        "trusted": True|False|None,
        "name": str|None,
        "address": str|None,
        "raw": str|None,
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

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from device using the configured client backend.

        Convert results to a normalized dict regardless of backend return type.
        Raise UpdateFailed for transient/unrecoverable update errors so the
        DataUpdateCoordinator machinery can handle retries.
        """
        client = self._client_factory()
        try:
            info = await client.info(self._mac)
        except BluetoothCtlPairingRequestedError as exc:
            # Pairing is not desired; classify as failure for this update cycle.
            raise UpdateFailed(f"Pairing requested: {exc}") from exc
        except (BluetoothCtlTimeoutError, BluetoothCtlNotFoundError) as exc:
            # Device unreachable / timeout
            raise UpdateFailed(str(exc)) from exc
        except BluetoothCtlError as exc:
            raise UpdateFailed(f"BluetoothCtl error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001, broad but we normalize here
            raise UpdateFailed(f"Unexpected error: {exc}") from exc

        # Normalize result: support both dict-like and object-like returns
        if isinstance(info, dict):
            return {
                "connected": info.get("connected"),
                "paired": info.get("paired"),
                "trusted": info.get("trusted"),
                "name": info.get("name"),
                "address": info.get("address"),
                "raw": info.get("raw"),
            }

        # Fallback: try attribute access on returned object
        return {
            "connected": getattr(info, "connected", None),
            "paired": getattr(info, "paired", None),
            "trusted": getattr(info, "trusted", None),
            "name": getattr(info, "name", None),
            "address": getattr(info, "address", None),
            "raw": getattr(info, "raw", None),
        }
