"""Coordinator for periodic device info polling."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_POLLING_INTERVAL_SEC

_LOGGER = logging.getLogger(__name__)


class MiPowerCoordinator(DataUpdateCoordinator):
    """Coordinator that polls device info using provided info function."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        update_method: Callable[[], Any],
        interval: float = DEFAULT_POLLING_INTERVAL_SEC,
    ) -> None:
        """Create coordinator.

        update_method: coroutine function returning dict-like info for device.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=asyncio.timedelta(seconds=interval) if hasattr(asyncio, "timedelta") else None,
        )
        # Keep a direct reference to call
        self._update_method = update_method

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from device using the provided method."""
        try:
            data = await self._update_method()
            return data
        except Exception as err:
            raise UpdateFailed(err)
