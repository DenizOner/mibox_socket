# MiPower — Home Assistant custom integration

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.8%2B-41BDF5)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)
[![Release](https://img.shields.io/github/v/release/DenizOner/MiPower?display_name=tag)](https://github.com/DenizOner/MiPower/releases)
[![Downloads](https://img.shields.io/github/downloads/DenizOner/MiPower/total.svg)](https://github.com/DenizOner/MiPower/releases)

MiPower, Android TV / Mi Box tarzı cihazları Bluetooth üzerinden "wake" / "sleep" yapmaya odaklı bir Home Assistant eklentisidir.
Bu proje hem `bluetoothctl` (BlueZ CLI) hem de `bleak` tabanlı backend'leri destekler. İlk kurulumda varsayılan backend `bluetoothctl`'dir (tercih edilebilir).

## Öne çıkan özellikler
- Wake (açma) ve Sleep (uyku / disconnect) işlemleri.
- Hem `bluetoothctl` hem `bleak` backend desteği (kullanıcı seçimi).
- Cihazın durumu (connected/unreachable) için polling ve fallback mantığı.
- UI üzerinde tek bir toggle switch (kullanıcının verdiği isim kullanılır).

## Gereksinimler
- Home Assistant (Home Assistant OS, Supervised veya Core).
- Eğer `bluetoothctl` backend kullanılacaksa, ana sistemde `bluetoothctl` bulunmalı ve hass host tarafında Bluetooth erişimi olmalıdır.
- `bleak` ve `bleak-retry-connector` Python paketleri manifest.json aracılığıyla yüklenecektir.

## Kurulum
1. `config/custom_components/mipower/` altına ilgili dosyaları kopyalayın.
2. Home Assistant'ı yeniden başlatın.
3. Settings → Integrations → Add Integration → "MiPower" ile ekleyin.
   - MAC adresini girin.
   - Backend seçimini yapın (`bluetoothctl` varsayılan).
   - İsteğe bağlı: Display name, polling, media_player fallback vb.

_Eklenti kurulumu sonrası Home Assistant tüm gereksinimleri (manifest.json içindeki `requirements`) kuracaktır._

## Pairing ve gizlilik uyarısı
Bu entegrasyon **otomatik olarak `pair` komutunu çalıştırmaz**. Amacımız cihazın ekranında pairing / PIN isteklerinin açılmasını engellemektir. Bu yüzden:
- Wake için `connect`/`disconnect` komutları ya da Bleak bağlantısı kullanılır.
- Eğer cihaz, başka bir host/telefon ile eşleşmişse veya cihaz pairing gerektiriyorsa kullanıcı müdahalesi gerekebilir.

## Lisans
Bu proje, yazarın isteğine göre **CC0 1.0 Universal (Public Domain Dedication)** olarak beyan edilmiştir — yani proje üzerinde sınırlama olmadan değişiklik yapabilir, çoğaltabilir ve dağıtabilirsiniz. (Burada dosya eklenmedi; README'de lisans belirtildi.)

## Hata ayıklama ve loglar
- Settings → System → Logs bölümünden entegrasyon loglarını izleyin.
- Eğer `bluetoothctl` backend seçili ise Terminal add-on ile `bluetoothctl devices` çıkışını karşılaştırabilirsiniz.

---

Geliştirici notu: eklenti hem taşınabilir hem de BlueZ-hosted sistemlerde çalışacak şekilde tasarlandı. Eğer cihazın `ble` stack'ine dair özel servis/karakteristik bilgisi varsa (ör. MiBox özel bir GATT servisi) bunun entegrasyona eklenmesi ile durum tespiti daha sağlam olur.
