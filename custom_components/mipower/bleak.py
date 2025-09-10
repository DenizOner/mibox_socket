"""Bleak-based minimal backend wrapper for MiPower.

This module provides `BleakClient` class exposing the async methods used by
the rest of the integration:
  - info(mac) -> dict-like / simple info
  - connect(mac, ...) -> str
  - disconnect(mac) -> str
  - power_off(mac) -> str

It attempts to use the `bleak` library if available. Errors are mapped to the
same BluetoothCtl* exception types used by the rest of the integration so the
higher layers can handle errors uniformly.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

# Try to import bleak; if not available, mark accordingly.
try:
    from bleak import BleakClient as _BleakClient  # type: ignore
    from bleak.exc import BleakError  # type: ignore
    _HAS_BLEAK = True
except Exception:
    _BleakClient = None  # type: ignore
    BleakError = Exception  # type: ignore
    _HAS_BLEAK = False

# Reuse our bluetoothctl exception types for compatibility with caller.
from .bluetoothctl import (
    BluetoothCtlError,
    BluetoothCtlTimeoutError,
    BluetoothCtlNotFoundError,
    BluetoothCtlPairingRequestedError,
)

# Default timeout for bleak operations
_DEFAULT_TIMEOUT = 12.0


class BleakClient:
    """Adapter using bleak to present the same interface as the bluetoothctl client.

    Note: This adapter focuses on providing a best-effort, minimal, compatible
    interface that the integration expects. For robust, device-specific usage
    you may need to extend methods to perform writes/reads to specific GATT
    characteristics.
    """

    def __init__(self, timeout_sec: float = _DEFAULT_TIMEOUT) -> None:
        self._timeout_sec = float(timeout_sec)
        if not _HAS_BLEAK:
            # Keep error type consistent with the rest of the code.
            raise BluetoothCtlError("bleak package is not installed")

    async def _with_client(self, mac: str, coro):
        """Create a BleakClient context and run coro(client)."""
        if not _HAS_BLEAK:
            raise BluetoothCtlError("bleak package is not installed")
        try:
            # Create a client instance and use it in a context manager
            # so connection resources are properly released.
            async with _BleakClient(mac) as client:
                return await coro(client)
        except asyncio.TimeoutError as exc:
            raise BluetoothCtlTimeoutError("bleak operation timed out") from exc
        except BleakError as exc:
            # Map bleak-specific errors to the generic BluetoothCtlError
            raise BluetoothCtlError(f"Bleak error: {exc}") from exc
        except Exception as exc:
            raise BluetoothCtlError(f"Bleak unexpected error: {exc}") from exc

    async def info(self, mac: str) -> Dict[str, Any]:
        """Return minimal info about the device (connected flag and placeholders)."""
        async def _task(client):
            try:
                # Bleak's client exposes an is_connected property once connected.
                # Use connect-then-inspect pattern to detect reachability.
                connected = client.is_connected
                return {"connected": connected}
            except Exception as exc:
                raise BluetoothCtlError(f"Bleak info error: {exc}") from exc

        try:
            return await asyncio.wait_for(self._with_client(mac, _task), timeout=self._timeout_sec)
        except BluetoothCtlTimeoutError:
            raise
        except BluetoothCtlError:
            raise
        except Exception as exc:
            raise BluetoothCtlNotFoundError(f"Unable to fetch info via bleak: {exc}") from exc

    async def connect(self, mac: str, retries: int = 3, retry_delay: float = 1.0) -> str:
        """Connect to device with simple retry logic.

        - retries: total attempts (1..n)
        - retry_delay: seconds to wait between attempts
        Returns "connected" on success, otherwise raises BluetoothCtlError.
        """
        if not _HAS_BLEAK:
            raise BluetoothCtlError("bleak package is not installed")

        async def _task(client):
            # Some bleak backends connect automatically when entering context,
            # but we ensure an explicit connect call for clarity.
            if not client.is_connected:
                await client.connect()
            return "connected"

        last_exc: Optional[Exception] = None
        for attempt in range(1, max(1, int(retries)) + 1):
            try:
                await asyncio.wait_for(self._with_client(mac, _task), timeout=self._timeout_sec)
                _LOGGER.debug("Bleak connect successful for %s (attempt %s/%s)", mac, attempt, retries)
                return "connected"
            except Exception as exc:
                last_exc = exc
                _LOGGER.debug(
                    "Bleak connect attempt %s/%s for %s failed: %s", attempt, retries, mac, exc
                )
                if attempt < retries:
                    await asyncio.sleep(float(retry_delay))

        # All attempts failed — surface a consistent error type.
        raise BluetoothCtlError(f"Bleak error: {last_exc}") from last_exc

    async def disconnect(self, mac: str) -> str:
        """Disconnect from the device (best-effort)."""
        async def _task(client):
            try:
                if client.is_connected:
                    await client.disconnect()
                return "disconnected"
            except Exception as exc:
                raise BluetoothCtlError(f"Bleak disconnect error: {exc}") from exc

        try:
            await asyncio.wait_for(self._with_client(mac, _task), timeout=self._timeout_sec)
            return "disconnected"
        except BluetoothCtlTimeoutError:
            raise
        except BluetoothCtlError:
            raise
        except Exception as exc:
            raise BluetoothCtlError(f"Bleak disconnect unexpected error: {exc}") from exc

    async def power_off(self, mac: Optional[str] = None) -> str:
        """Power-off is device-specific; fallback to disconnect as best-effort."""
        # Many BLE devices don't expose a generic 'power off' characteristic.
        if mac is None:
            raise BluetoothCtlError("power_off requires mac for BleakClient")
        await self.disconnect(mac)
        return "power_off"
