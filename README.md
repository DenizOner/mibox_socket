# MiPower

A Home Assistant custom integration to wake/sleep Mi Box S–like devices via bluetoothctl without pairing popups.

- Async, non-interactive `bluetoothctl`
- Pairing‑free wake flow (info → connect → short wait → disconnect → verify)
- Optional polling (DataUpdateCoordinator); else sync switch state to a chosen media_player
- Entity services: `mipower.wake_device`, `mipower.sleep_device`
- Options Flow (Gelişmiş Ayarlar)

## Requirements

- Linux host with BlueZ (`bluetoothctl`) available on PATH
  - Debian/Ubuntu: `sudo apt install bluez`
  - Docker: ensure host BlueZ/DBus is accessible (e.g., `--net=host` or equivalent), grant required permissions

## Install

1. Copy `custom_components/mipower` to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add MiPower from Integrations, provide Bluetooth MAC (AA:BB:CC:DD:EE:FF).
   - Tip: It probably starts with `E0:B6:55:**:**:**`.

## Options (Gelişmiş Ayarlar)

- Command timeout (sec), retry count, retry delay (sec)
- Disconnect delay after wake (sec, step 0.1)
- Polling on/off
- Polling interval (sec)
- Sleep command type: `disconnect` (default) or `power off`

When polling is OFF:
- Select a `media_player` entity to mirror its state
- We try to preselect a media_player whose Bluetooth MAC starts with `E0:B6:55`, if detectable via device registry

## Services

- `mipower.wake_device`
  - Target: the MiPower switch entity
  - Behavior: info → connect → wait → disconnect → verify (no pairing)
- `mipower.sleep_device`
  - Target: the MiPower switch entity
  - Behavior: either `disconnect` or `power off` depending on Options

## Error handling

- No pairing is performed by the integration
- If pairing is requested by the device/controller, the flow aborts and a Warning is logged
- Timeouts and out-of-range conditions are logged as Warning
- Environment issues (missing `bluetoothctl`) are Critical during setup (setup rejected)

## Troubleshooting

- Verify `bluetoothctl` is installed and works from shell
- Ensure the host has Bluetooth and BlueZ running
- For Docker: run with host networking and DBus or provide required interfaces
- Check HA logs under `custom_components.mipower` (enable DEBUG for detailed traces)

## Diagnostics

Optional diagnostics export will mask MAC address and include non-sensitive options for support.
