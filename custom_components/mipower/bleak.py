"""Bleak-based minimal backend wrapper for MiPower.

This module provides `BleakClient` class exposing the same async methods
used by the rest of the integration:
  - info(mac) -> dict-like / simple info
  - connect(mac)
  - disconnect(mac)
  - power_off(mac)

It attempts to use the `bleak` library if available. If `bleak` is not
installed, the class will raise an environment error when used — the
switch module uses a factory to prefer Bleak when available, otherwise
falls back to the existing bluetoothctl implementation.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

try:
    from bleak import BleakClient as _BleakClient  # type: ignore
    _HAS_BLEAK = True
except Exception:
    _BleakClient = None  # type: ignore
    _HAS_BLEAK = False

# Import the exception classes from bluetoothctl module so we expose the
# same exception types to the rest of the integration (compatibility).
from .bluetoothctl import (
    BluetoothCtlError,
    BluetoothCtlTimeoutError,
    BluetoothCtlNotFoundError,
    BluetoothCtlPairingRequestedError,
)


class BleakClient:
    """A minimal adapter implementing the same interface expected by the
    integration while using `bleak` internally when available.
    """

    def __init__(self, timeout_sec: float = 12.0) -> None:
        self._timeout_sec = float(timeout_sec)
        if not _HAS_BLEAK:
            # Use the same exception class so caller can handle uniformly.
            raise BluetoothCtlError("bleak package is not installed")

    async def _with_client(self, mac: str, coro):
        """Helper to create a BleakClient connection and run coro(client)."""
        if not _HAS_BLEAK:
            raise BluetoothCtlError("bleak package is not installed")
        try:
            async with _BleakClient(mac) as client:
                return await coro(client)
        except asyncio.TimeoutError as exc:
            raise BluetoothCtlTimeoutError("bleak operation timed out") from exc
        except Exception as exc:
            # Map bleak errors to generic BluetoothCtlError for compatibility.
            raise BluetoothCtlError(f"Bleak error: {exc}") from exc

    async def info(self, mac: str) -> Dict[str, Any]:
        """Attempt to collect minimal info. Bleak's API is GATT-based; for
        a generic info we expose whether we can connect and a placeholder.
        Real device-specific attributes should be added after device testing.
        """
        async def _task(client):
            # .is_connected is a property on bleak client after connection
            return {"connected": client.is_connected}

        try:
            return await asyncio.wait_for(self._with_client(mac, _task), timeout=self._timeout_sec)
        except BluetoothCtlError:
            raise
        except Exception as exc:
            # If unable to fetch info, map to not found / generic error
            raise BluetoothCtlNotFoundError(f"Unable to fetch info via bleak: {exc}") from exc

    async def connect(self, mac: str) -> str:
        """Connect to device (best-effort)."""
        async def _task(client):
            # For many devices, client.connect is implicit when using context manager.
            # If ensures explicit connect, try it.
            if not client.is_connected:
                await client.connect()
            return "connected"

        await asyncio.wait_for(self._with_client(mac, _task), timeout=self._timeout_sec)
        return "connected"

    async def disconnect(self, mac: str) -> str:
        """Disconnect from device (best-effort)."""
        async def _task(client):
            if client.is_connected:
                await client.disconnect()
            return "disconnected"

        await asyncio.wait_for(self._with_client(mac, _task), timeout=self._timeout_sec)
        return "disconnected"

    async def power_off(self, mac: Optional[str] = None) -> str:
        """Power-off is controller-specific; raise not implemented or attempt a disconnect."""
        # Many BLE devices don't expose a 'power off' GATT write generically.
        # We mimic best-effort by disconnecting.
        if mac is None:
            raise BluetoothCtlError("power_off requires mac for BleakClient")
        await self.disconnect(mac)
        return "power_off"
