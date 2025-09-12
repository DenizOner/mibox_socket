# MiPower — Home Assistant custom integration

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.8%2B-41BDF5)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)
[![Release](https://img.shields.io/github/v/release/DenizOner/MiPower?display_name=tag)](https://github.com/DenizOner/MiPower/releases)
[![Downloads](https://img.shields.io/github/downloads/DenizOner/MiPower/total.svg)](https://github.com/DenizOner/MiPower/releases)

MiPower is a Home Assistant custom integration that aims to wake / sleep Android TV / Mi Box style devices over Bluetooth.
It supports both `bluetoothctl` (BlueZ CLI on the host) and `bleak` (Python BLE client) backends.

## Quick features
- Toggle device (wake via connect / sleep via disconnect).
- Two backends: `bluetoothctl` (default) and `bleak` (user-selectable).
- Optional polling for device reachability.
- Single toggle switch using the name you set.

## Installation
1. Place the `mipower` folder into `config/custom_components/`.
2. Restart Home Assistant.
3. Integrations -> Add Integration -> “MiPower”. Provide the device MAC and choose backend.

## Backend notes
- `bluetoothctl` backend requires `bluetoothctl` available on the host system (Home Assistant OS, supervised host, or add-on).
- `bleak` requires Python packages (`bleak`, `bleak-retry-connector`), which are declared in `manifest.json` and will be installed automatically by HA when the integration is loaded.

## Safety & pairing
- This integration **does not perform `pair`** or attempt to modify device pairing to avoid triggering device UI pairing prompts.
- We use `connect`/`disconnect` or a short BLE probe to wake devices. In some devices, pairing or host-side permissions may still be required.

## Troubleshooting
- If the integration fails to behave as expected, check: Settings -> System -> Logs for `custom_components.mipower`.
- If using `bluetoothctl`, the host must have Bluetooth enabled and the user running the HA process must have permission to use BlueZ.
- If HACS says "pending restart" but you see no notification, manually restarting Home Assistant is always safe and will load new code.

## License
Author has chosen **CC0 1.0 Universal (Public Domain Dedication)** for this project. No separate LICENSE file is included per project owner request.

## Developer notes
- The integration avoids blocking the Home Assistant event loop by using asyncio subprocess for `bluetoothctl` calls.
- Extensive debug logs are available under logger `custom_components.mipower`.
