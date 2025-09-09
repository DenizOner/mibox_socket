# MiPower

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.8%2B-41BDF5)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)
[![Release](https://img.shields.io/github/v/release/your-org-or-user/mipower?display_name=tag)](https://github.com/your-org-or-user/mipower/releases)
[![Downloads](https://img.shields.io/github/downloads/your-org-or-user/mipower/total.svg)](https://github.com/your-org-or-user/mipower/releases)

MiPower is a Home Assistant custom integration that wakes and sleeps Mi Box S–like devices via `bluetoothctl` **without showing pairing popups**.  
It is fully asynchronous, uses non‑interactive commands, and follows a **"abort if pairing is requested"** safety rule.

- Pairing‑free wake flow: `info` → `connect` → short wait → `disconnect` → verify
- Optional polling (DataUpdateCoordinator) for real-time status
- Media player state fallback when polling is disabled
- Services: `mipower.wake_device` and `mipower.sleep_device`
- Advanced settings (Options Flow) for timeouts, retries, polling, and behavior

> Tip: Your device’s Bluetooth MAC address likely starts with `E0:B6:55:**:**:**`.

---

## Features

- Fully async, non‑interactive `bluetoothctl` execution
- Aborts if pairing is requested (never initiates pairing)
- Adjustable timeout and retry policies
- Configurable polling on/off, polling interval, and disconnect delay
- Media player state sync when polling is off
- `sleep_device` service can either `disconnect` or `power off` (with warnings)
- Diagnostics support (MAC partially masked for privacy)

---

## Requirements

- Linux host with BlueZ (`bluetoothctl`) installed and available in PATH:
  - Debian/Ubuntu: `sudo apt install bluez`
  - Other distros: install bluez/bluetoothctl via your package manager
- Home Assistant 2024.8 or newer
- If running in Docker:
  - Host must have BlueZ and DBus running
  - Container must have access to host Bluetooth and DBus (e.g., `--net=host` or equivalent), with proper permissions

---

## Installation

### 1) Install via HACS

#### A) As a Custom Repository (immediate use)
1. Go to **HACS > Integrations >** three‑dot menu > **Custom repositories**
2. Repository URL: `https://github.com/your-org-or-user/mipower`
3. Category: **Integration**
4. Click **Add**, then install MiPower from HACS
5. Restart Home Assistant
6. Go to **Settings > Devices & Services > Add Integration > MiPower**

> Note: The repo includes `hacs.json` so README renders properly in HACS.

#### B) Once in the HACS Default List
- Search for “MiPower” in HACS and install directly.
- This requires the project to be accepted into HACS’s official default list.

### 2) Manual Installation (without HACS)

1. Download or clone this repository.
2. Create the directory `custom_components/mipower` under your Home Assistant `config` folder.
3. Copy all files from this repo’s `custom_components/mipower` into that directory.
4. The structure should look like:
   ```
   config/
   └── custom_components/
       └── mipower/
           ├── __init__.py
           ├── manifest.json
           ├── const.py
           ├── config_flow.py
           ├── bluetoothctl.py
           ├── coordinator.py
           ├── switch.py
           ├── services.yaml
           ├── diagnostics.py
           ├── translations/
           │   ├── en.json
           │   └── tr.json
           └── README.md
   ```
5. Restart Home Assistant.
6. Go to **Settings > Devices & Services > Add Integration > MiPower**.

---

## Initial Setup

1. When adding the integration, enter your device’s Bluetooth MAC address (AA:BB:CC:DD:EE:FF).
   - Tip: Likely starts with `E0:B6:55:**:**:**`.
   - Case-insensitive; integration normalizes to uppercase.
2. After setup, open **Options** (Advanced Settings) to fine-tune behavior.

---

## Advanced Settings (Options Flow)

- **Command timeout** (5–30s; default 12s)
- **Retry count** (0–3; default 1)
- **Retry delay** (1–10s; default 2s)
- **Disconnect delay after wake** (0.5–10.0s; default 2.0s, 0.1s precision)
- **Polling** on/off
- **Polling interval** (5–120s; default 15s)
- **Sleep command type**:
  - `disconnect` (default)
  - `power off` (optional; may trigger pairing or other side effects depending on model)

### Media Player Fallback (when polling is off)
- If polling is disabled, you must select a `media_player` entity.
- Switch state will mirror the selected media_player’s state (`on`/`playing`/`idle` → on; `off` → off).
- If Home Assistant can detect Bluetooth MACs for media players and finds one starting with `E0:B6:55`, it will be preselected.

---

## Services

- **`mipower.wake_device`**
  - Target: MiPower switch entity
  - Flow: `info` → `connect` → short wait → `disconnect` → verify
  - Aborts if pairing is requested; logs a warning

- **`mipower.sleep_device`**
  - Target: MiPower switch entity
  - Behavior: per Options:
    - `disconnect`: end connection
    - `power off`: attempt to power off controller (may vary by model/environment)
  - Verifies after action

Example automation (wake):
```yaml
alias: MiPower - Morning Wake
trigger:
  - platform: time
    at: "07:30:00"
action:
  - service: mipower.wake_device
    target:
      entity_id: switch.mipower_e0_b6_55_aa_bb_cc
mode: single
```

Example automation (sleep):
```yaml
alias: MiPower - Night Sleep
trigger:
  - platform: time
    at: "01:00:00"
action:
  - service: mipower.sleep_device
    target:
      entity_id: switch.mipower_e0_b6_55_aa_bb_cc
mode: single
```

---

## How It Works

- **Wake**:
  1. `bluetoothctl info <MAC>`
  2. If not connected: `connect <MAC>`
  3. Wait (disconnect delay from Options)
  4. `disconnect <MAC>`
  5. Verify with `info`
- If pairing is requested, abort and log warning.
- **Polling on**: Coordinator runs `info` periodically.
- **Polling off**: Switch state mirrors selected media_player.

---

## Troubleshooting

- **`bluetoothctl` not found**:
  - Debian/Ubuntu: `sudo apt install bluez`
  - Ensure it’s in PATH (`bluetoothctl` works in terminal)
  - Docker: Host BlueZ + DBus access, container permissions (`--net=host` or equivalent)
- **Pairing popup**:
  - Integration never initiates pairing; if detected, aborts.
  - Some models may require one-time manual pairing to avoid prompts.
- **Timeout / out of range**:
  - Increase timeout/retry in Options.
  - Improve Bluetooth signal/antenna.
- **State not updating**:
  - Enable polling or ensure correct media_player is selected.
- **Unexpected `power off` behavior**:
  - May affect controller; prefer `disconnect` if unsure.

Log levels:
- **Warning**: timeout, out of range, pairing detected
- **Error**: environment/subprocess errors
- **Debug**: detailed command/output (enable DEBUG logger)

---

## Diagnostics

You can export settings and last known state (with masked MAC) for support:
- **Settings > Devices & Services > MiPower >** three‑dot menu > **Download Diagnostics**

---

## FAQ

- **Does it pair?**  
  No. If pairing is detected, aborts and logs a warning.
- **Multiple devices?**  
  Yes. Add the integration multiple times; each entry is independent.
- **Minimum HA version?**  
  2024.8 or newer.

---

## Contributing & Issues

- Report issues via GitHub Issues with detailed logs and description.
- PRs welcome — follow async and design principles.

---

## License

MIT — see LICENSE file.

---

## Changelog

- **0.1.0**: Initial release — async bluetoothctl, pairing‑free wake, optional polling, media_player fallback, wake/sleep services, advanced settings.
