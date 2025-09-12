"""Bleak-based backend wrapper.

This module exposes async functions:
- async info(address) -> dict
- async connect(address) -> BleakClient-like object or None
- async disconnect(address) -> None

Uses `bleak` and prefers `bleak-retry-connector` if available to increase reliability.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)

try:
    from bleak import BleakClient, BleakError  # type: ignore
except Exception as exc:
    BleakClient = None  # type: ignore
    BleakError = Exception  # type: ignore
    _LOGGER.debug("Bleak import failed: %s", exc)

# Try to import establish_connection from bleak_retry_connector
try:
    from bleak_retry_connector import establish_connection  # type: ignore
except Exception:
    establish_connection = None  # type: ignore


class BleakBackendError(Exception):
    """Generic bleak backend error."""


async def connect(address: str, timeout: float = 8.0, max_attempts: int = 3):
    """Try to establish a reliable BLE connection to address.

    Returns a connected BleakClient (caller must call disconnect) or raises.
    """
    if BleakClient is None:
        raise BleakBackendError("bleak library not available")

    # If bleak-retry-connector is available, use it
    if establish_connection is not None:
        try:
            # establish_connection will return connected client
            client = await asyncio.wait_for(
                establish_connection(BleakClient, address, max_attempts=max_attempts),
                timeout=timeout * max_attempts + 5,
            )
            return client
        except Exception as exc:
            _LOGGER.debug("bleak_retry_connector establish_connection failed: %s", exc)
            # fallback to plain Bleak below

    # Fallback: try connecting with BleakClient directly, with retries
    attempt = 0
    last_exc = None
    while attempt < max_attempts:
        attempt += 1
        try:
            client = BleakClient(address)
            await asyncio.wait_for(client.connect(), timeout=timeout)
            if await client.is_connected():
                return client
            else:
                await client.disconnect()
        except Exception as exc:
            last_exc = exc
            _LOGGER.debug("Bleak connect attempt %s failed: %s", attempt, exc)
            try:
                await asyncio.sleep(1.0)
            except Exception:
                pass
    raise BleakBackendError(f"Could not connect to {address}: {last_exc}")


async def disconnect(client, timeout: float = 5.0) -> None:
    """Disconnect a BleakClient instance (best-effort)."""
    try:
        if client is None:
            return
        await asyncio.wait_for(client.disconnect(), timeout=timeout)
    except Exception as exc:
        _LOGGER.debug("Bleak disconnect error (ignored): %s", exc)


async def info(address: str, timeout: float = 6.0) -> Dict[str, Optional[str]]:
    """Return basic info about connection state by attempting a lightweight connect-check.

    WARNING: This should be used sparingly (connect attempts are potentially heavy).
    """
    result: Dict[str, Optional[str]] = {
        "address": address,
        "name": None,
        "connected": None,
        "raw": None,
    }

    # Quick attempt: create a client, check is_connected without full connect flow if possible
    if BleakClient is None:
        raise BleakBackendError("bleak library not available")

    try:
        client = BleakClient(address)
        # try a very short connect to probe reachability
        await asyncio.wait_for(client.connect(), timeout=timeout)
        connected = await client.is_connected()
        result["connected"] = connected
        try:
            # Try to read name characteristic if present - best-effort (not required)
            result["name"] = await client.read_gatt_char("00002a00-0000-1000-8000-00805f9b34fb")
        except Exception:
            # ignore; not all devices expose that char
            pass
        await asyncio.wait_for(client.disconnect(), timeout=3.0)
    except Exception as exc:
        result["connected"] = False
        result["raw"] = str(exc)
    return result
