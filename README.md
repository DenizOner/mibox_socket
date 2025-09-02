# MiPower

MiPower is a Home Assistant integration that allows you to power on your Xiaomi Mi Box via Bluetooth (“bluetoothctl” pairing), even without a physical remote.

---

## Features
- Simple UI-driven configuration: specify the Mi Box’s MAC address and a friendly name.
- Fully compatible with HACS (Home Assistant Community Store) as a Custom Integration.
- Supports both English (default) and Turkish translations (with localization files included).

---

## Requirements
- A compatible Linux host (e.g. Raspberry Pi OS) with `bluetoothctl` (BlueZ) installed.
- Home Assistant instance running on a system with access to Bluetooth and DBus. For containerized environments, ensure DBus (`/run/dbus`) is mounted and proper device permissions are granted.

---

## Installation Methods

### 1. Manual Installation
1. Create the `custom_components/mibox_socket` directory.
2. Copy all MiPower files into this directory.
3. Restart Home Assistant.

### 2. Installation via HACS
1. Open Home Assistant and go to **HACS → Integrations**.
2. Click the “⋮” (three-dot menu) and select **Custom repositories**.
3. Add the repository URL: `https://github.com/DenizOner/MiPower` and choose **Integration** type.
4. Once added, find **MiPower** under HACS → Integrations and install it.
5. Restart Home Assistant if prompted.

---

## Post-Installation: Configuration Flow

After installing MiPower:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **MiPower** and select it to configure.
3. Enter the **MAC address** of your Mi Box and assign a **friendly name**.
4. Confirm and complete the configuration.

_(Bu adımı destekleyen görseller yukarıda eklenmiştir.)_

---

## Usage Notes
- Ensure Bluetooth on the host is active and discoverable before initiating the pairing/provisioning process.
- Pairing may take 15–30 seconds depending on environmental conditions; please wait accordingly.
- If errors occur, verify:
  - Bluetooth and DBus configurations on the host,
  - Permission settings for Bluetooth access in Home Assistant environment,
  - Whether the Mi Box is visible over BLE.

---

## License
MiPower is released into the **public domain under the Creative Commons CC0 1.0 Universal "No Rights Reserved" license**. This means anyone can **use, modify, distribute, and build upon the code for any purpose**, without any restriction.:contentReference[oaicite:1]{index=1}

---

## Contribution Guidelines
Contributions are welcome! If you’d like to improve MiPower, feel free to:
- Submit **bug reports**, **feature requests**, or ask questions via the GitHub **Issues** section,
- Fork the repository, make your enhancements, and open a **Pull Request**.

---

## Feedback & Support
Need help or want to share feedback? Reach out through GitHub Issues—I'm listening, and your input shapes MiPower’s future.

---

