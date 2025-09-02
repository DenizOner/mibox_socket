# MiPower

**MiPower** is a Home Assistant custom integration that enables powering on a **Mi Box S** via Bluetooth pairing (using `bluetoothctl`). The Mi Box S does not include an IR (Infra-Red) remote receiver like some other Mi Box models; therefore, this model can only be reliably controlled via its Bluetooth remote. MiPower implements a practical workaround to address the device's deep-sleep limitation.

**Why this project exists (motivation, non-technical):**  
Turning a Mi Box S **off** can be done with an ADB command, but turning it **on** is only possible with the physical remote because the device enters a deep sleep state. This integration uses the `bluetoothctl` pairing sequence to awaken the device remotely — a workaround that is effective where IR control is not available. The approach is pragmatic and aims to help Home Assistant users control Mi Box S devices without the original remote.

---

## Features (high level)
- Create a switch entity in Home Assistant that attempts to wake the Mi Box S using Bluetooth pairing.
- UI-driven configuration (MAC address + friendly name).
- HACS (Home Assistant Community Store) compatible for easy installation as a custom integration.
- Translations included: English (default) and Turkish.

---

## Compatibility & Requirements
- Host OS: Linux with BlueZ (e.g., Raspberry Pi OS). `bluetoothctl` must be available.
- Home Assistant must run on a host/container that has access to the host Bluetooth interface and DBus (BlueZ). When running Home Assistant in containers, you may need to mount `/run/dbus` and provide device access privileges.
- Python package dependency listed in `manifest.json`: **`pexpect`** (used to drive the `bluetoothctl` pairing session).
- Minimum Home Assistant version (per packaging metadata): **2021.12.0** (see `hacs.json` for HACS metadata).
- Integration domain (code): `mibox_socket` — installed files live under `custom_components/mibox_socket`.

---

## Installation

Two supported installation methods are provided. Install files must remain in `custom_components/mibox_socket`.

### 1) Manual Installation (file copy)
1. Create directory: `config/custom_components/mibox_socket`
2. Copy **all** files from this repository's `custom_components/mibox_socket` into that directory, preserving structure (including `translations/`, `manifest.json`, `switch.py`, `config_flow.py`, `__init__.py`, `const.py`, etc.).
3. Ensure your host has `bluetoothctl` and DBus available to Home Assistant.
4. Restart Home Assistant.

> After restart, continue with **Configuration** section below to add the integration in the UI.

### 2) Installation via HACS (recommended for easier updates)
1. Open Home Assistant → **HACS** → **Integrations**.  
   ![HACS main screen](docs/images/hacs_main.png)
2. Click the three-dot menu (top right) → **Custom repositories**.  
   ![HACS custom repos menu](docs/images/hacs_custom_repos.png)
3. Add repository:
   - Repository URL: `https://github.com/DenizOner/MiPower`
   - Category / Type: **Integration**  
   ![HACS add custom repo](docs/images/hacs_add_repo.png)
4. After HACS has indexed the repo, go to **HACS → Integrations**, find **MiPower** and click **Install**.  
   ![HACS install integration](docs/images/hacs_install_integration.png)
5. Restart Home Assistant if HACS prompts you to do so.

> After restart, continue with **Configuration** section below to add the integration in the UI.

---

## Configuration (Post-installation UI flow)
1. In Home Assistant go to **Settings → Devices & Services**.  
   ![Settings > Devices & Services](docs/images/settings_devices_services.png)
2. Click **Add Integration** (bottom right or top right depending on HA version).  
   ![Add integration button](docs/images/add_integration_button.png)
3. Search for **MiPower** and select it.  
   ![Search and select MiPower](docs/images/search_mipower.png)
4. Fill the configuration form:
   - **MAC address** (required): the Bluetooth MAC of your Mi Box S (format `XX:XX:XX:XX:XX:XX`).
   - **Friendly name** (required): label for the switch entity.
   - **Optional**: choose an existing `media_player` entity to link the integration with (if desired).  
   ![MiPower config form](docs/images/mipower_config_form.png)
5. Submit. A new switch entity (something like `switch.<friendly_name>` depending on HA entity naming) will appear in Entities and can be used in automations or dashboards.

**Note:** `config_flow.py` in the integration supports a UI EntitySelector for an optional `media_player` input, but the integration works with only the MAC + name as a minimum.

---

## How it works (brief, non-technical)
- When you toggle the MiPower switch ON, the integration triggers a `bluetoothctl` pairing attempt towards the Mi Box S's MAC address using a controlled `bluetoothctl` session (driven via `pexpect`). This triggers the Mi Box S to wake up enough to accept commands or show the pairing prompt — which acts as a "wake" signal.
- This mechanism is a workaround for the device's deep sleep state and is intentionally minimal: it doesn’t attempt invasive device modification or rely on unsupported hardware hacks.

---

## Usage Notes & Best Practices
- Ensure the host Bluetooth adapter is not blocked and BlueZ is functional (`sudo bluetoothctl` should work on the host).
- The Mi Box S should be reachable over Bluetooth; physical distance and RF/environmental conditions affect success rate.
- Pairing may take several seconds — do not repeatedly issue pairing commands in rapid succession.
- The integration does not change Mi Box S firmware or settings; it only performs a pairing attempt as a wake action.
- The earlier outdated recommendation "Do not trigger the switch while the Mibox is already ON" has been removed from the docs — the integration handles usual device state changes; however, avoid forcing redundant toggles for cleaner logs and fewer pairing attempts.

---

## Troubleshooting
- **Pairing fails repeatedly:**
  - Confirm MAC is correct and formatted properly.
  - Verify BlueZ (`bluetoothctl`) on the host can discover/connect to other devices.
  - Check Home Assistant logs for `mibox_socket` related tracebacks (set logger level to debug temporarily).
  - Ensure `/run/dbus` is mounted into the container (if using docker).
- **Permission or DBus errors:**
  - Run Home Assistant with privileges or grant access to DBus (for supervised/home installed HA this is usually configured by default).
- **Dependency issues:**
  - Ensure `pexpect` is installed in Home Assistant’s Python environment (the integration `manifest.json` requests it — HACS should install this on supported installs; for manual installs, you may need to add the package).
- **Logs & Debugging:**
  - Check Home Assistant `core` logs and filter for `mibox_socket` or `switch.mibox_socket` for operational messages.
  - Add more verbose logging for `pexpect` sessions if needed in the integration (for advanced debugging).

---

## Contributing
Contributions are welcome. If you want to help:
- Open an **Issue** describing the bug, feature request, or question.
- Fork the repository, create a feature branch, implement your change, and open a **Pull Request**.
- Keep changes focused, include tests or detailed manual test steps when relevant, and document new behavior in README or code comments.
- For code style, prefer clear, well-documented Python with asyncio-aware functions (matching Home Assistant conventions).

---

## Feedback & Support
If you need assistance or want to provide feedback:
- Use GitHub **Issues** for bug reports, support requests, or improvement suggestions.
- Provide the following in your issue to speed diagnosis:
  - Home Assistant version and installation method (OS, Supervisor, Container).
  - Host OS and BlueZ version.
  - Relevant logs (filtered) and the Mi Box S MAC address (omit actual address if you prefer — but confirm format).
  - Exact steps you performed and observed results.

---

## Security & Privacy
- MiPower performs Bluetooth pairing attempts and does not collect or transmit personal data externally.
- The integration requires permission to use the host Bluetooth stack (local only). Use at your own discretion and ensure your host is secure.
- If you discover a security issue, report it privately via GitHub or contact the maintainer rather than posting details publicly.

---

## License
This project is released into the **public domain** under the **Creative Commons CC0 1.0 Universal** license (CC0 1.0). This effectively places the work into the public domain — you are free to copy, modify, distribute, and perform the work, even for commercial purposes, without asking permission.  
Reference: https://creativecommons.org/publicdomain/zero/1.0/

---

## Acknowledgements & Origins
MiPower is a fork and refinement of an earlier community workaround. The core idea — using a `bluetoothctl` pairing attempt to wake the device — comes from the same practical need: the Mi Box S goes to deep sleep and cannot be turned on with ADB alone. This repository adapts that approach into a Home Assistant custom integration with a config flow and HACS packaging.

---

## Files & Structure (what to expect after installation)
