"""Bluetoothctl (BlueZ) asynchronous helper.

This module provides a small async wrapper around the bluetoothctl binary,
using asyncio.create_subprocess_exec so we do not block the Home Assistant event loop.

It provides a minimal "client" API with:
- async info(address) -> dict
- async connect(address) -> None
- async disconnect(address) -> None
- async scan(seconds) -> list of (address,name)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

class BluetoothCtlError(Exception):
    """Generic bluetoothctl wrapper error."""


async def _run_cmd(*args: str, timeout: float = 10.0) -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise BluetoothCtlError(f"Command {' '.join(args)} timed out")
    return proc.returncode, (stdout.decode("utf-8", errors="ignore") if stdout else ""), (stderr.decode("utf-8", errors="ignore") if stderr else "")


async def info(address: str, timeout: float = 6.0) -> Dict[str, Optional[str]]:
    """Return parsed output of `bluetoothctl info <address>`.

    Example output lines parsed:
      Name: Mi Box S
      Alias: Mi Box S
      Paired: yes
      Trusted: yes
      Connected: no
    """
    try:
        rc, out, err = await _run_cmd("bluetoothctl", "info", address, timeout=timeout)
    except BluetoothCtlError as exc:
        _LOGGER.debug("bluetoothctl info failed: %s", exc)
        raise

    data: Dict[str, Optional[str]] = {
        "address": address,
        "raw": out,
        "name": None,
        "paired": None,
        "trusted": None,
        "connected": None,
    }
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            data["name"] = line.partition("Name:")[2].strip()
        elif line.startswith("Paired:"):
            data["paired"] = line.partition("Paired:")[2].strip()
        elif line.startswith("Trusted:"):
            data["trusted"] = line.partition("Trusted:")[2].strip()
        elif line.startswith("Connected:"):
            data["connected"] = line.partition("Connected:")[2].strip().lower()
    return data


async def connect(address: str, timeout: float = 8.0) -> None:
    """Attempt to connect via bluetoothctl connect <address>.

    We purposely do NOT run `pair` to avoid triggering pairing UI on the device.
    """
    try:
        rc, out, err = await _run_cmd("bluetoothctl", "connect", address, timeout=timeout)
        if rc != 0:
            _LOGGER.debug("bluetoothctl connect returned rc=%s out=%s err=%s", rc, out, err)
            raise BluetoothCtlError(f"connect failed ({rc})")
        # Note: bluetoothctl may still succeed but return 0 while not fully connected; consumer should check info().
    except BluetoothCtlError:
        raise


async def disconnect(address: str, timeout: float = 6.0) -> None:
    """Run bluetoothctl disconnect <address>."""
    try:
        rc, out, err = await _run_cmd("bluetoothctl", "disconnect", address, timeout=timeout)
        if rc != 0:
            _LOGGER.debug("bluetoothctl disconnect returned rc=%s out=%s err=%s", rc, out, err)
            # not raising - disconnect best-effort
    except BluetoothCtlError:
        raise


async def scan(seconds: float = 8.0) -> List[Tuple[str, Optional[str]]]:
    """Run `bluetoothctl scan on` for a few seconds and gather discovered devices (best-effort).

    Note: scanning via bluetoothctl as a subprocess is best-effort; if bluetoothctl is not available,
    this will raise.
    """
    # Start scanning (spawn bluetoothctl with "scan on" then sleep then run "devices")
    # Simpler approach: run "bluetoothctl devices" after waiting; if device adverts, it will be present.
    await _run_cmd("bluetoothctl", "scan", "on", timeout=2.0)
    await asyncio.sleep(seconds)
    try:
        rc, out, err = await _run_cmd("bluetoothctl", "devices", timeout=4.0)
    finally:
        # turn scan off (best effort)
        try:
            await _run_cmd("bluetoothctl", "scan", "off", timeout=2.0)
        except Exception:
            pass

    results: List[Tuple[str, Optional[str]]] = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Device"):
            # "Device E0:B6:55:52:6C:00 Mi Box S"
            parts = line.split(" ", 2)
            if len(parts) >= 2:
                addr = parts[1].strip()
                name = parts[2].strip() if len(parts) >= 3 else None
                results.append((addr, name))
    return results
