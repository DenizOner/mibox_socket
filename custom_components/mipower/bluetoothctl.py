"""
Async bluetoothctl client wrapper for MiPower.

Non-interactive, one-shot commands via asyncio subprocess.
No pairing commands are issued by this client. If pairing-like prompts
are detected, operations are aborted with a specific error.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
from dataclasses import dataclass
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# Heuristic strings to classify output results
PAIRING_HINTS = (
    "pair",  # generic
    "authentication",  # org.bluez.Error.Authentication*
    "passkey",
    "pincode",
    "confirm",
    "authorize",
)
NOT_FOUND_HINTS = (
    "not available",
    "not found",
    "no such device",
)
TIMEOUT_HINTS = ("timed out", "timeout",)

@dataclass
class BtInfo:
    connected: Optional[bool] = None
    paired: Optional[bool] = None
    trusted: Optional[bool] = None
    address: Optional[str] = None
    name: Optional[str] = None
    raw: str = ""


class BluetoothCtlError(Exception):
    """Base class for bluetoothctl-related errors."""


class BluetoothCtlTimeoutError(BluetoothCtlError):
    """Command timeout."""


class BluetoothCtlPairingRequestedError(BluetoothCtlError):
    """Pairing requested/required detected; we deliberately abort."""


class BluetoothCtlNotFoundError(BluetoothCtlError):
    """Device not found or controller/device unavailable."""


class BluetoothCtlEnvError(BluetoothCtlError):
    """Environment or execution error (bluetoothctl missing/failed)."""


class BluetoothCtlParseError(BluetoothCtlError):
    """Parsing failed or unexpected output."""


class BluetoothCtlClient:
    """
    One-shot async bluetoothctl wrapper.

    Design:
    - Each command spawns a subprocess: bluetoothctl <subcommand...>
    - Output is captured and analyzed.
    - Timeout is enforced via asyncio.wait_for.
    - No stateful interactive session; minimal side-effects.
    """

    def __init__(self, timeout_sec: float = 12.0) -> None:
        self._timeout_sec = timeout_sec

    def _build_argv(self, *parts: str) -> list[str]:
        # We prefer argv over shell strings to avoid shell quoting issues.
        return ["bluetoothctl", *parts]

    async def _run(self, *parts: str) -> str:
        """
        Run a bluetoothctl command and return stdout text.

        Raises:
            BluetoothCtlTimeoutError, BluetoothCtlEnvError
        """
        argv = self._build_argv(*parts)
        _LOGGER.debug("Running bluetoothctl: %s", " ".join(shlex.quote(p) for p in argv))
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as exc:
            raise BluetoothCtlEnvError(f"Failed to start bluetoothctl: {exc}") from exc

        try:
            stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=self._timeout_sec)
        except asyncio.TimeoutError as exc:
            with contextlib.suppress(Exception):
                proc.kill()
            raise BluetoothCtlTimeoutError("bluetoothctl command timed out") from exc

        output = stdout_bytes.decode("utf-8", errors="replace").strip()
        _LOGGER.debug("bluetoothctl output:\n%s", output)
        return output

    @staticmethod
    def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
        text = haystack.lower()
        return any(n in text for n in needles)

    @staticmethod
    def _parse_yes_no(line: str) -> Optional[bool]:
        # Expect lines like "Connected: yes/no"
        parts = [p.strip() for p in line.split(":", 1)]
        if len(parts) != 2:
            return None
        val = parts[1].strip().lower()
        if val in ("yes", "true", "on"):
            return True
        if val in ("no", "false", "off"):
            return False
        return None

    def _parse_info(self, mac: str, output: str) -> BtInfo:
        info = BtInfo(raw=output)
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            low = line.lower()
            if low.startswith("device ") and mac.lower() in low:
                info.address = mac
            elif low.startswith("name:"):
                info.name = line.split(":", 1)[1].strip()
            elif low.startswith("connected:"):
                info.connected = self._parse_yes_no(line)
            elif low.startswith("paired:"):
                info.paired = self._parse_yes_no(line)
            elif low.startswith("trusted:"):
                info.trusted = self._parse_yes_no(line)
        return info

    def _classify_common_errors(self, output: str) -> None:
        low = output.lower()
        if self._contains_any(low, PAIRING_HINTS):
            raise BluetoothCtlPairingRequestedError("Pairing requested/required by device/controller")
        if self._contains_any(low, NOT_FOUND_HINTS):
            raise BluetoothCtlNotFoundError("Device not available or not found")

    async def info(self, mac: str) -> BtInfo:
        out = await self._run("info", mac)
        # Some controllers print nothing for unknown devices; still classify
        self._classify_common_errors(out)
        # Parse best-effort
        info = self._parse_info(mac, out)
        return info

    async def connect(self, mac: str) -> str:
        out = await self._run("connect", mac)
        self._classify_common_errors(out)
        return out

    async def disconnect(self, mac: str) -> str:
        out = await self._run("disconnect", mac)
        # disconnect often returns success even if not connected; still ok
        self._classify_common_errors(out)
        return out

    async def power_off(self, mac: str | None = None) -> str:
        """
        Power off the controller or device where applicable.

        Note: On many systems 'power off' affects the controller, not device.
        Some devices expose device-specific power actions via different APIs.
        We keep this as a best-effort, and still parse for pairing hints.
        """
        out = await self._run("power", "off")
        self._classify_common_errors(out)
        return out
