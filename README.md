<!-- Language selector -->
[English](README.md) | [Türkçe](README.tr.md) | [Español](README.es.md) | [Русский](README.ru.md)

# MiPower

MiPower is a Home Assistant custom integration that enables powering on a **Mi Box S** via Bluetooth pairing (using `bluetoothctl`). The Mi Box S does not include an IR (Infra-Red) remote receiver like some other Mi Box models; therefore, this model can only be reliably controlled via its Bluetooth remote. MiPower implements a practical workaround to address the device's deep-sleep limitation.

**Why this project exists:**  
Turning a Mi Box S **off** can be done with an ADB command, but turning it **on** is only possible with the physical remote because the device enters a deep sleep state. This integration uses the `bluetoothctl` pairing sequence to awaken the device remotely — a pragmatic workaround that helps Home Assistant users control Mi Box S devices without the original remote.

---

## Features
- Provides a Home Assistant switch entity that attempts to wake a Mi Box S via a controlled Bluetooth pairing attempt.
- Simple UI-driven configuration (MAC address + friendly name).
- Compatible with HACS (Home Assistant Community Store) as a custom integration.
- Includes English and Turkish translations; additional language files may be added.

---

## Compatibility & Requirements
- Host OS: Linux with BlueZ (e.g., Raspberry Pi OS). `bluetoothctl` must be available on the host.
- Home Assistant must run on a host/container with access to the host Bluetooth interface and DBus (BlueZ). Containerized installs may require mounting `/run/dbus` and granting device permissions.
- Python dependency declared in `manifest.json`: **pexpect** (used to control `bluetoothctl` sessions).
- Minimum Home Assistant version per metadata: **2021.12.0**.
- Integration domain: `mibox_socket` (install files under `custom_components/mibox_socket`).

---

## Installation

Two supported installation methods are provided. Files must be placed under `custom_components/mibox_socket`.

### 1) Manual Installation (file copy)
1. Create directory: `config/custom_components/mibox_socket`
2. Copy all files from this repository's `custom_components/mibox_socket` into that directory, preserving structure (including `translations/`, `manifest.json`, `switch.py`, `config_flow.py`, `__init__.py`, `const.py`, etc.).
3. Ensure your host has `bluetoothctl` installed and that DBus access is available to Home Assistant.
4. Restart Home Assistant.

> After restart, continue with the **Configuration** section below to add the integration in the UI.

### 2) Installation via HACS (recommended)
1. Open Home Assistant → **HACS** → **Integrations**.
   ![HACS main screen](docs/images/hacs_main.png)
   *HACS main Integrations view.*
   
2. Click the three-dot menu → **Custom repositories**.
   ![HACS custom repos menu](docs/images/hacs_custom_repos.png)
   *Access the “Custom repositories” dialog from the three-dot menu.*
   
3. Add repository:
   - Repository URL: `https://github.com/DenizOner/MiPower`
   - Category / Type: **Integration**
	![HACS add custom repo](docs/images/hacs_add_repo.png)
   *Add the repository URL and select “Integration” as the type.*
   
4. After HACS has indexed the repository, go to **HACS → Integrations**, find **MiPower** and click **Install**.
   ![HACS install integration](docs/images/hacs_install_integration.png)
   *Install the MiBox Socket integration from HACS → Integrations.*
   
5. Restart Home Assistant if prompted.

> After restart, continue with the **Configuration** section below to add the integration in the UI.

---

## Configuration (Post-installation UI flow)
1. In Home Assistant go to **Settings → Devices & Services**.
   ![Settings > Devices & Services](docs/images/settings_devices_services.png)
   *Open Devices & Services to add the integration.*
   
2. Click **Add Integration**.
   ![Add integration button](docs/images/add_integration_button.png)
   *Press "Add Integration" (button location varies by HA version).*
   
3. Search for **MiPower** and select it.
   ![Search and select MiPower](docs/images/search_mipower.png)
   *Search field: type the integration name.*
   
4. Fill the configuration form:
   - **MAC address** (required): Bluetooth MAC of your Mi Box S (`XX:XX:XX:XX:XX:XX`).
   - **Friendly name** (required): label for the switch entity.
   - **Optional**: choose an existing `media_player` entity to link the integration with, if desired.
   ![MiPower config form](docs/images/mipower_config_form.png)
   *Enter the device MAC like `AA:BB:CC:DD:EE:FF` and a friendly name, then submit.*
   
5. Submit. A new switch entity (e.g., `switch.<friendly_name>`) will appear in Entities.

Placeholders for screenshots are included using `docs/images/*.png`. To show real screenshots, add them to `docs/images/` with the referenced filenames.

---

## How it works
- When the MiPower switch is toggled ON, the integration triggers a `bluetoothctl` pairing attempt toward the Mi Box S's MAC address using a controlled session (driven via `pexpect`). The pairing attempt acts as a wake signal to the device.
- This is a workaround for the device's deep sleep state and does not modify device firmware or settings.

---

## Usage Notes & Best Practices
- Ensure the host Bluetooth adapter is functional (`sudo bluetoothctl` should work on the host).
- The Mi Box S should be within range; RF environment affects success.
- Avoid issuing pairing commands in rapid succession.
- The integration does not change Mi Box S firmware or settings; it performs a pairing attempt as a wake action.

---

## Troubleshooting
- Verify MAC address format.
- Confirm BlueZ and `bluetoothctl` can discover/connect to devices on the host.
- Check Home Assistant logs for `mibox_socket` related messages (increase logger level to debug if needed).
- If using containers, ensure `/run/dbus` is mounted and device permissions are granted.

---

## Contributing
Contributions are welcome:
- Open an Issue for bugs or feature requests.
- Fork the repository, implement changes on a branch, and open a Pull Request.
- Include tests or manual verification steps where relevant and document new behaviors.

---

## Feedback & Support
Use GitHub Issues for bug reports, support requests, or suggestions. Include Home Assistant version, installation type, host OS, BlueZ version, relevant logs, and steps you performed.

---

## Security & Privacy
- MiPower performs local Bluetooth pairing attempts and does not transmit personal data externally.
- The integration requires host-level Bluetooth/DBus access; use on trusted hosts.

---

## License
This project is released into the public domain under the **Creative Commons CC0 1.0 Universal (CC0 1.0)** license. You are free to copy, modify, and distribute the work without restriction.
Reference: https://creativecommons.org/publicdomain/zero/1.0/

---

## Acknowledgements & Origins
MiPower is a fork of @frlequ's `mibox_socket` project — many core ideas and the original implementation were derived from that repository.
