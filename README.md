# Mibox Socket

Mibox Socket — Home Assistant integration using bluetooth pairing (bluetoothctl) to “turn on” the Xiaomi Mibox device without a remote control.

## Features
- Configuration via UI (MAC + name)
- HACS compatible (can be added as a custom repository)
- English default, Turkish translations included

## Requirements
- Host system must have `bluetoothctl` (BlueZ). On Raspberry Pi OS and many Linux distros this is available.
- Home Assistant must run on a host/container that has access to bluetooth stack (DBus/BlueZ). In some container setups you may need to mount `/run/dbus` and provide device permissions.

## Installation (manual)
1. In your repository create the directory structure `custom_components/mibox_socket` and add the files from this repo.
2. Restart Home Assistant.
3. Go to Settings -> Devices & Services -> Add Integration -> search "Mibox Socket" and add. Enter MAC and name.

## Installation (via HACS)
1. In HACS -> Integrations -> three dots (top right) -> Custom repositories -> Add your repo URL `https://github.com/DenizOner/mibox_socket`, type: `Integration`.
2. After HACS imports it, go to Integrations and install.
3. Restart Home Assistant if required.

## Usage notes
- Do not trigger the switch while the Mibox is already ON — this may show pairing dialog on-screen. If that happens, cancel pairing on the TV.
- Pairing may take up to ~15-30 seconds depending on environment.
- If pairing fails, check host Bluetooth, permissions, and that Mibox is reachable.

## Issues
Use GitHub issues for bug reports.

