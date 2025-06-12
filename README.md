# SAGA Wohnung Takip Sistemi

Bu program, SAGA Hamburg web sitesindeki yeni daire ilanlarını takip eder ve belirlenen kriterlere uygun ilanlar bulunduğunda e-posta bildirimi gönderir.

## Özellikler

- Her 5 dakikada bir otomatik kontrol
- 2, 2.5 ve 3 odalı daireleri filtreleme
- E-posta bildirimleri (başlık, oda sayısı, m², toplam kira bilgileriyle)
- Çoklu e-posta alıcı desteği

## Kurulum

1. Render.com hesabı oluşturun
2. Bu repository'yi Render.com'a bağlayın
3. Aşağıdaki ortam değişkenlerini ayarlayın:
   - `EMAIL_FROM`: Gönderen e-posta adresi
   - `EMAIL_TO`: Alıcı e-posta adresleri (virgülle ayrılmış)
   - `EMAIL_PASSWORD`: Gmail uygulama şifresi

## Gereksinimler

- Python 3.8+
- requests
- beautifulsoup4
- python-dotenv

## Notlar

- Gmail hesabınızda "2 Adımlı Doğrulama" açık olmalı
- Gmail "Uygulama Şifresi" oluşturulmalı
- Program sürekli çalışır durumda kalacak şekilde ayarlanmıştır 