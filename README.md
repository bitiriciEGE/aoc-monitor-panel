# AOC Monitor Kontrol Paneli

AOC Q27G42ZE (27" QHD 180Hz) monitörler için Python/tkinter DDC-CI kontrol uygulaması.

## Özellikler

- **DDC/CI** üzerinden tam kontrol (Windows `dxva2.dll`)
- Parlaklik, Kontrast
- Renk Sıcaklığı (sRGB / Warm / Normal / Cool / User)
- RGB Gain (Kırmızı, Yeşil, Mavi — User modu)
- Gaming Mode (Standard / FPS / RTS / Racing / Gamer 1-2-3)
- Giriş Kaynağı (DisplayPort / HDMI 1 / HDMI 2)
- Güç Modu (Ac / Bekleme / Kapat)
- Ses Seviyesi
- **Mavi Işık Filtresi** (GDI Gamma Ramp — DDC/CI bağımsız, her zaman çalışır)
- **Hızlı Profiller** (Sabah Dersi, Sabah Çalışması, Akşam Dersi, Counter Strike)
- Fabrika sıfırlama (Görüntü / Renk / Tümü)
- 2 monitör desteği (sekme bazlı)
- Premium Gaming + Glassmorphism arayüzü

## Gereksinimler

- Windows 10/11
- Python 3.8+
- Tkinter (Python ile birlikte gelir)
- DDC/CI destekleyen monitör (AOC Q27G42ZE ile test edildi)

## Kurulum

```bash
git clone https://github.com/KULLANICI_ADI/aoc-monitor-panel.git
cd aoc-monitor-panel
python monitor_control.py
```

Ekstra kütüphane gerekmez — yalnızca standart Python kullanılır.

## Teknik Notlar

- Her DDC komutu için **taze fiziksel monitor handle** açılır ve hemen yok edilir.  
  Bu, Windows'un iki monitöre aynı handle atamasını önler (yaygın bir Windows DDC hatası).
- Mavi Işık Filtresi `gdi32.SetDeviceGammaRamp` ile çalışır; DDC/CI durumundan bağımsızdır.
- RGB Gain VCP kodları yalnızca Renk Sıcaklığı **User (0x0B)** modunda aktif olur.  
  Slider'a dokunulduğunda uygulama otomatik olarak User moduna geçer.
- Desteklenmeyen ayarlar (Keskinlik, Gamma, Dark Boost vb.) yalnızca OSD üzerinden değiştirilebilir; bu ayarlar bilgi amaçlı listelenir.

## VCP Kodu Referansı

| Ayar | VCP | Değerler |
|------|-----|----------|
| Parlaklik | 0x10 | 0–100 |
| Kontrast | 0x12 | 0–100 |
| Renk Sıcaklığı | 0x14 | 0x01=sRGB, 0x05=Warm, 0x06=Normal, 0x08=Cool, 0x0B=User |
| Kırmızı Gain | 0x16 | 0–100 (User modu) |
| Yeşil Gain | 0x18 | 0–100 (User modu) |
| Mavi Gain | 0x1A | 0–100 (User modu) |
| Giriş Kaynağı | 0x60 | 0x0F=DP, 0x11=HDMI1, 0x12=HDMI2 |
| Ses | 0x62 | 0–100 |
| Güç | 0xD6 | 1=Ac, 4=Bekleme, 5=Kapat |
| Gaming Mode | 0xDC | 0x00=Std, 0x0B=FPS, 0x0C=RTS, 0x0D=Racing, 0x0E-10=Gamer1-3 |

## Lisans

MIT
