"""Constants for MiPower integration."""

DOMAIN = "mipower"

# Configuration keys (user-facing)
CONF_MAC = "mac"
CONF_NAME = "name"
CONF_BACKEND = "backend"
CONF_MEDIA_PLAYER_ENTITY_ID = "media_player_entity_id"

# Optional advanced config keys
CONF_TIMEOUT_SEC = "timeout_sec"
CONF_RETRY_COUNT = "retry_count"
CONF_RETRY_DELAY_SEC = "retry_delay_sec"
CONF_POLLING_ENABLED = "polling_enabled"
CONF_POLLING_INTERVAL_SEC = "polling_interval_sec"
CONF_DISCONNECT_DELAY_SEC = "disconnect_delay_sec"
CONF_SLEEP_COMMAND_TYPE = "sleep_command_type"

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

# Entities / platforms
PLATFORMS = ["switch"]
DEFAULT_ENTITY_ICON = "mdi:power-settings"
