"""
MiPower constants and helpers.
"""

from __future__ import annotations

import re
from typing import Final

DOMAIN: Final = "mipower"

# Entegrasyon (Integrations/HACS kartları) ikonu
INTEGRATION_ICON: Final = "mdi:power-settings"

# Varlık (switch) ikonu
DEFAULT_ENTITY_ICON: Final = "mdi:power"

# Defaults (can be overridden via Options Flow)
DEFAULT_TIMEOUT_SEC: Final[float] = 12.0
DEFAULT_RETRY_COUNT: Final[int] = 1
DEFAULT_RETRY_DELAY_SEC: Final[float] = 2.0
DEFAULT_POLLING_ENABLED: Final[bool] = False
DEFAULT_POLLING_INTERVAL_SEC: Final[float] = 15.0
DEFAULT_DISCONNECT_DELAY_SEC: Final[float] = 2.0

# Bounds (validated in Options Flow)
MIN_TIMEOUT_SEC: Final[float] = 5.0
MAX_TIMEOUT_SEC: Final[float] = 30.0

MIN_RETRY_COUNT: Final[int] = 0
MAX_RETRY_COUNT: Final[int] = 3

MIN_RETRY_DELAY_SEC: Final[float] = 1.0
MAX_RETRY_DELAY_SEC: Final[float] = 10.0

MIN_POLLING_INTERVAL_SEC: Final[float] = 5.0
MAX_POLLING_INTERVAL_SEC: Final[float] = 120.0

MIN_DISCONNECT_DELAY_SEC: Final[float] = 0.5
MAX_DISCONNECT_DELAY_SEC: Final[float] = 10.0

# Options keys
CONF_MAC: Final = "mac"
CONF_MEDIA_PLAYER_ENTITY_ID: Final = "media_player_entity_id"
CONF_TIMEOUT_SEC: Final = "timeout_sec"
CONF_RETRY_COUNT: Final = "retry_count"
CONF_RETRY_DELAY_SEC: Final = "retry_delay_sec"
CONF_POLLING_ENABLED: Final = "polling_enabled"
CONF_POLLING_INTERVAL_SEC: Final = "polling_interval_sec"
CONF_DISCONNECT_DELAY_SEC: Final = "disconnect_delay_sec"
CONF_SLEEP_COMMAND_TYPE: Final = "sleep_command_type"  # "disconnect" or "power_off"

# Sleep command type values
SLEEP_CMD_DISCONNECT: Final = "disconnect"
SLEEP_CMD_POWER_OFF: Final = "power_off"

# Entity
DEFAULT_ICON: Final = INTEGRATION_ICON

# MAC regex (AA:BB:CC:DD:EE:FF) - case-insensitive
MAC_REGEX: Final = re.compile(r"^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$")

# Helper: normalize MAC to uppercase
def normalize_mac(mac: str) -> str:
    return mac.strip().upper()

# Helper: validate MAC format
def is_valid_mac(mac: str) -> bool:
    return MAC_REGEX.match(mac.strip()) is not None


