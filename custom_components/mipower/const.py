"""Constants for MiPower integration."""

DOMAIN = "mipower"

# Config keys
CONF_MAC = "mac"
CONF_NAME = "name"
CONF_BACKEND = "backend"  # "bluetoothctl" or "bleak"
CONF_MEDIA_PLAYER_ENTITY_ID = "media_player_entity_id"

# Backend choices
BACKEND_BLUETOOTHCTL = "bluetoothctl"
BACKEND_BLEAK = "bleak"

# Defaults
DEFAULT_BACKEND = BACKEND_BLUETOOTHCTL
DEFAULT_TIMEOUT_SEC = 8.0
DEFAULT_RETRY_COUNT = 2
DEFAULT_RETRY_DELAY_SEC = 2.0
DEFAULT_POLLING_ENABLED = False
DEFAULT_POLLING_INTERVAL_SEC = 30
DEFAULT_DISCONNECT_DELAY_SEC = 2.0

# Sleep command types
SLEEP_CMD_DISCONNECT = "disconnect"
SLEEP_CMD_POWER_OFF = "power_off"

# Entity things
DEFAULT_ENTITY_ICON = "mdi:power-settings"
PLATFORMS = ["switch"]

# Service names (optional)
SERVICE_WAKE = "wake"
SERVICE_SLEEP = "sleep"
