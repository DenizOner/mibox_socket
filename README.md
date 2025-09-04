<!-- Language selector -->
[English](README.md) | [Türkçe](README.tr.md) | [Español](README.es.md) | [Русский](README.ru.md)

# MiPower

[![GitHub Release](https://img.shields.io/github/v/release/DenizOner/MiPower?include_prereleases)](https://github.com/DenizOner/MiPower/releases)
[![License: CC0-1.0](https://img.shields.io/badge/license-CC0%201.0-lightgrey.svg)](https://creativecommons.org/publicdomain/zero/1.0/)
[![HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=DenizOner&repository=MiPower)

MiPower is a Home Assistant custom integration that enables powering on a **Mi Box S** via Bluetooth pairing (using `bluetoothctl`). The Mi Box S does not include an IR (Infra-Red) remote receiver like some other Mi Box models; therefore, this model can only be reliably controlled via its Bluetooth remote. MiPower implements a practical workaround to address the device's deep-sleep limitation.

**Why this project exists:**  
Turning a Mi Box S **off** can be done with an ADB command, but turning it **on** is only possible with the physical remote because the device enters a deep sleep state. This integration uses the `bluetoothctl` pairing sequence to awaken the device remotely — a pragmatic workaround that helps Home Assistant users control Mi Box S devices without the original remote.

---

## About
MiPower is a small, focused Home Assistant custom integration designed specifically to remotely **wake / power on a Mi Box S** using a controlled Bluetooth pairing attempt. It is not a replacement for official device APIs; it implements a pragmatic workaround where IR is unavailable and ADB cannot wake the device from deep sleep.

*Key idea:* a short, automated `bluetoothctl` pairing attempt (driven by `pexpect`) behaves as a wake signal for the Mi Box S.

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

Three supported installation methods are provided. 

### 1) Installation via My Home Assistant (one-click)

To install this add-on, manually add my HA-Addons repository to Home Assistant
using [this GitHub repository][ha-addons] or by clicking the button below.

[![Add Repository to HA][my-ha-badge]][my-ha-url]

### 2) Manual Installation (file copy)
1. Create directory: `config/custom_components/mibox_socket`
2. Copy all files from this repository's `custom_components/mibox_socket` into that directory, preserving structure (including `translations/`, `manifest.json`, `switch.py`, `config_flow.py`, `__init__.py`, `const.py`, etc.).
3. Ensure your host has `bluetoothctl` installed and that DBus access is available to Home Assistant.
4. Restart Home Assistant.

> After restart, continue with the **Configuration** section below to add the integration in the UI.

### 3) Installation via HACS (recommended)

Just simply click here:

[![Add MiPower to HACS][my-hacs-badge]][my-hacs-url]

Or manually continue:

1. Open Home Assistant → **HACS** → **Integrations**.

   ![HACS main screen](docs/images/hacs_main.png)
   
   *HACS main Integrations view.*
   
3. Click the three-dot menu → **Custom repositories**.

   ![HACS custom repos menu](docs/images/hacs_custom_repos.png)
   
   *Access the “Custom repositories” dialog from the three-dot menu.*
   
5. Add repository:
   - Repository URL: `https://github.com/DenizOner/MiPower`
   - Category / Type: **Integration**
	
 	![HACS add custom repo](docs/images/hacs_add_repo.png)

	*Add the repository URL and select “Integration” as the type.*
   
7. After HACS has indexed the repository, go to **HACS → Integrations**, find **MiPower** and click **Install**.

   ![HACS install integration](docs/images/hacs_install_integration.png)
   
   *Install the MiBox Socket integration from HACS → Integrations.*
   
9. Restart Home Assistant if prompted.

> After restart, continue with the **Configuration** section below to add the integration in the UI.

---

## Configuration (Post-installation UI flow)
1. In Home Assistant go to **Settings → Devices & Services**.

   ![Settings > Devices & Services](docs/images/settings_devices_services.png)
   
   *Open Devices & Services to add the integration.*
   
3. Click **Add Integration**.

   ![Add integration button](docs/images/add_integration_button.png)
   
   *Press "Add Integration" (button location varies by HA version).*
   
5. Search for **MiPower** and select it.

   ![Search and select MiPower](docs/images/search_mipower.png)
   
   *Search field: type the integration name.*
   
7. Fill the configuration form:
   - **MAC address** (required): Bluetooth MAC of your Mi Box S (`XX:XX:XX:XX:XX:XX`).
   - **Friendly name** (required): label for the switch entity.
   - **Optional**: choose an existing `media_player` entity to link the integration with, if desired.
   
   ![MiPower config form](docs/images/mipower_config_form.png)
   
   *Enter the device MAC like `AA:BB:CC:DD:EE:FF` and a friendly name, then submit.*
   
9. Submit. A new switch entity (e.g., `switch.<friendly_name>`) will appear in Entities.

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

---

## Support
If you need help or want to report an issue, please open an Issue on GitHub: https://github.com/DenizOner/MiPower/issues

---

## Authors & contributors
Originally forked from @frlequ's `mibox_socket` repository. For full contributor list, check the GitHub contributors page.

---

## Reference links (used above)
[ha-addons]: https://github.com/DenizOner/MiPower
[my-ha-url]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FDenizOner%2FMiPower
[my-hacs-url]: https://my.home-assistant.io/redirect/hacs_repository/?owner=DenizOner&repository=MiPower
[my-ha-badge]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[my-hacs-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[issue]: https://github.com/DenizOner/MiPower/issues



