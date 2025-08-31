# Mibox Socket

Mibox Socket — Xiaomi Mibox cihazını uzaktan kumanda olmadan "açmak" için bluetoothctl pairing (pexpect) kullanan Home Assistant integration.

## Features
- UI üzerinden konfigürasyon (MAC + isim)
- HACS uyumlu (custom repository olarak eklenebilir)
- English default, Turkish translations included

## Requirements (host)
- `bluetoothctl` (BlueZ) yüklü olmalı.
- Home Assistant'ın çalıştığı host/container'ın BlueZ/DBus erişimi olmalı. Container kullanıyorsanız `/run/dbus` vb. mount etmeniz gerekebilir.

## Installation (manual)
1. Repo içeriğini `custom_components/mibox_socket` altına kopyalayın.
2. Restart Home Assistant.
3. Settings -> Devices & Services -> Add Integration -> search "Mibox Socket" ve ekleyin. MAC ve name girin.

## Installation (HACS)
1. HACS -> Integrations -> üç nokta -> Custom repositories -> Add: `https://github.com/DenizOner/mibox_socket`, type: `Integration`.
2. Install, sonra Integration sayfasından yapılandırın.

## Usage notes
- Switch tetiklendiğinde entegrasyon pairing sekansını çalıştırır; işlem anlık bir "momentary" tetikleme gibidir (switch ON → pairing süresi → tekrar OFF).
- Pairing sırasında cihaz ekranında pairing bildirimi çıkabilir; kullanıcı iptal ederse pairing başarısız olur.
- Eğer pairing sürekli başarısızsa, `bluetoothctl` çıktısını alıp bana gönder; pattern'leri güncelleyip anında düzelteceğim.

## Issues
Bug report için GitHub issues kullanın.
