<!-- Dil seçici -->
[English](README.md) | [Türkçe](README.tr.md) | [Español](README.es.md) | [Русский](README.ru.md)

# MiPower

MiPower, **Mi Box S** cihazınızı Bluetooth eşleştirmesi (`bluetoothctl` kullanarak) yoluyla açmanıza olanak tanıyan bir Home Assistant özel entegrasyonudur. Mi Box S, bazı diğer Mi Box modellerinde bulunan IR (kızılötesi) alıcı modülünü içermez; bu nedenle bu model yalnızca Bluetooth kumandası ile güvenilir biçimde kontrol edilebilir. MiPower, cihazın derin uyku (deep sleep) sınırlamasına yönelik pratik bir çözüm sunar.

**Projeye neden başladık:**  
Mi Box S’i **kapatmak** ADB komutuyla mümkünken, cihaz derin uykuya geçtiği için **açmak** yalnızca fiziksel kumandayla yapılabiliyordu. Bu entegrasyon, cihazı uzaktan uyandırmak için `bluetoothctl` ile eşleştirme sırasını kullanır — fiziksel kumanda olmadan Mi Box S kontrolünü sağlamaya yönelik pragmatik bir çözümdür.

---

## Özellikler
- Mi Box S’i uyandırmayı deneyen bir Home Assistant switch (anahtar) varlığı sağlar.
- Basit, kullanıcı arayüzü (UI) tabanlı yapılandırma (MAC adresi + takma ad).
- HACS (Home Assistant Community Store) ile uyumludur.
- İngilizce ve Türkçe çeviri dosyaları dahildir; ek diller eklenebilir.

---

## Uyumluluk ve Gereksinimler
- Host işletim sistemi: BlueZ içeren Linux (ör. Raspberry Pi OS). Host üzerinde `bluetoothctl` bulunmalıdır.
- Home Assistant, host Bluetooth arabirimine ve DBus'a erişebilen bir ortamda çalışmalıdır. Konteyner kullanıyorsanız `/run/dbus`'ın mount edilmesi ve cihaz izinlerinin sağlanması gerekebilir.
- `manifest.json` içinde beyan edilen Python bağımlılığı: **pexpect** (kontrol amaçlı).
- Metadata'ya göre minimum Home Assistant sürümü: **2021.12.0**.
- Entegrasyon domain'i: `mibox_socket` (dosyaları `custom_components/mibox_socket` altına yerleştirin).

---

## Kurulum

Dosyalar `custom_components/mibox_socket` altında olmalıdır. İki kurulum yöntemi desteklenir.

### 1) Manuel Kurulum (dosya kopyalama)
1. Klasör oluşturun: `config/custom_components/mibox_socket`
2. Bu repo içindeki `custom_components/mibox_socket` içeriğini aynı dizine olduğu gibi kopyalayın (`translations/`, `manifest.json`, `switch.py`, `config_flow.py`, `__init__.py`, `const.py` vb. dahil).
3. Host üzerinde `bluetoothctl` yüklü ve DBus erişimi Home Assistant için sağlanmış olmalı.
4. Home Assistant’ı yeniden başlatın.

> Yeniden başlatmanın ardından aşağıdaki **Yapılandırma** bölümünü izleyin.

### 2) HACS Üzerinden Kurulum (önerilen)
1. Home Assistant → **HACS** → **Integrations** açın.
2. Sağ üstteki üç nokta menüsünden **Custom repositories** seçeneğine tıklayın.
3. Depo ekleyin:
   - Repository URL: `https://github.com/DenizOner/MiPower`
   - Kategori / Tür: **Integration**
4. HACS repo'yu indeksledikten sonra **HACS → Integrations** üzerinden **MiPower**'ı bulun ve **Install** yapın.
5. Gerekirse Home Assistant’ı yeniden başlatın.

> Yeniden başlatmanın ardından aşağıdaki **Yapılandırma** bölümünü izleyin.

---

## Yapılandırma (Kurulum sonrası - UI akışı)
1. Home Assistant'ta **Settings → Devices & Services** menüsüne gidin.
2. **Add Integration**'a tıklayın.
3. **MiPower** aratıp seçin.
4. Yapılandırma formunu doldurun:
   - **MAC address** (zorunlu): Mi Box S’in Bluetooth MAC adresi (`XX:XX:XX:XX:XX:XX`).
   - **Friendly name** (zorunlu): switch için takma ad.
   - **Opsiyonel**: varsa bir `media_player` varlığını ilişkilendirebilirsiniz.
5. Gönderin. Yeni bir switch varlığı oluşacaktır (örn. `switch.<friendly_name>`).

Ekran görüntüleri için `docs/images/*.png` yer tutucuları kullanılmıştır. Gerçek ekran görüntülerini `docs/images/` altına ekleyin.

---

## Nasıl çalışır
- Switch ON konumuna getirildiğinde entegrasyon, `pexpect` aracılığıyla kontrol edilen bir `bluetoothctl` eşleştirme denemesi başlatır. Bu eşleştirme denemesi Mi Box S’i uyandıran bir sinyal görevi görür.
- Bu yöntem cihazın derin uyku durumuna yönelik bir çözümdür; cihaz yazılımını değiştirmez veya kalıcı değişiklik yapmaz.

---

## Kullanım Notları & İyi Uygulamalar
- Host üzerinde `bluetoothctl` çalıştığından emin olun (`sudo bluetoothctl` ile test edin).
- Mi Box S’in erişim menzili dahilinde olduğundan emin olun; çevresel koşullar başarı oranını etkiler.
- Eşleştirme komutlarını art arda hızlıca göndermekten kaçının.
- Entegrasyon, Mi Box S’in yazılımını değiştirmez; sadece uyandırma amaçlı bir eşleştirme denemesi yapar.

---

## Sorun Giderme
- MAC adresini kontrol edin.
- Host'ta BlueZ ve `bluetoothctl` ile cihaz keşfinin mümkün olup olmadığını doğrulayın.
- Home Assistant loglarını `mibox_socket` için kontrol edin (gerekirse log seviyesini debug yapın).
- Konteyner kullanıyorsanız `/run/dbus`'ın mount edildiğinden ve izinlerin verildiğinden emin olun.

---

## Katkıda Bulunma
Katkılar memnuniyetle kabul edilir:
- Hata raporları veya özellik talepleri için Issue açın.
- Depoyu fork’layın, değişiklikleri branch üzerinde yapın ve Pull Request gönderin.
- Değişiklikleri dokümante edin ve gerekirse test adımları ekleyin.

---

## Geri Bildirim & Destek
Destek veya geri bildirim için GitHub Issues kullanın. Lütfen bildirirken şu bilgileri ekleyin: Home Assistant sürümü ve kurulum türü, host OS, BlueZ sürümü, ilgili loglar ve yaptığınız adımlar.

---

## Güvenlik & Gizlilik
- MiPower yerel Bluetooth eşleştirme denemeleri yapar; kişisel verileri dışarı aktarmaz.
- Entegrasyon host seviyesinde Bluetooth/DBus erişimi gerektirir; güvenilir hostlarda kullanın.

---

## Lisans
Bu proje **Creative Commons CC0 1.0 Universal (CC0 1.0)** lisansı ile kamu malı (public domain) olarak yayımlanmıştır. Kodu istediğiniz şekilde kopyalayabilir, değiştirebilir ve dağıtabilirsiniz.
Referans: https://creativecommons.org/publicdomain/zero/1.0/

---

## Teşekkür & Kaynaklar
MiPower, @frlequ kullanıcı adının `mibox_socket` projesinden fork edilmiştir — birçok temel fikir ve orijinal uygulama o depodan türetilmiştir.
