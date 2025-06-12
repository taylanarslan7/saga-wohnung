import requests
from bs4 import BeautifulSoup
import time
import schedule
from datetime import datetime, timedelta
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import csv
import pathlib
import re

# .env dosyasının tam yolunu bul
env_path = pathlib.Path(__file__).parent / '.env'
print(f"\n.env dosyası aranıyor: {env_path}")
print(f"Dosya mevcut mu: {env_path.exists()}")

# .env dosyasını yükle
if env_path.exists():
    print("Dosya bulundu, yükleniyor...")
    load_dotenv(dotenv_path=env_path)
else:
    print("HATA: .env dosyası bulunamadı!")
    exit(1)

# Filtre ayarları
ODA_SAYILARI = ["2", "2,5", "3"]  # İstenen oda sayıları

# SAGA ana URL
SAGA_URL = "https://www.saga.hamburg/immobiliensuche?Kategorie=APARTMENT#APARTMENT-card-6"

KONTROL_ARALIĞI = 5  # 5 dakikada bir kontrol et

# Log dosyası ayarları
DETAYLI_LOG_DOSYASI = "saga_detayli_log.csv"

# E-posta ayarları
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_TO = os.getenv('EMAIL_TO')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Debug: .env değişkenlerini kontrol et
print("\n=== .env Değişkenleri ===")
print(f"EMAIL_FROM: {EMAIL_FROM}")
print(f"EMAIL_TO: {EMAIL_TO}")
print(f"EMAIL_PASSWORD: {'Ayarlanmış' if EMAIL_PASSWORD else 'Eksik'}")
print("=======================\n")

# E-posta ayarlarını kontrol et
if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
    print("HATA: E-posta ayarları eksik! Lütfen şu çevre değişkenlerini kontrol edin:")
    print(f"EMAIL_FROM: {'Ayarlanmış' if EMAIL_FROM else 'Eksik'}")
    print(f"EMAIL_TO: {'Ayarlanmış' if EMAIL_TO else 'Eksik'}")
    print(f"EMAIL_PASSWORD: {'Ayarlanmış' if EMAIL_PASSWORD else 'Eksik'}")
    exit(1)

# SMTP ayarları (Gmail için)
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# HTTP Session ayarları
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def detayli_log_ekle(islem, durum, detay=""):
    # İngilizce durum ve işlem adları
    islem_map = {
        "Kontrol": "Check",
        "Bağlantı": "Connection",
        "Veri": "Data",
        "Sistem": "System"
    }
    
    durum_map = {
        "Başladı": "Started",
        "Başarılı": "Success",
        "Hata": "Error",
        "Durduruldu": "Stopped"
    }
    
    # Detay çevirileri
    detay_map = {
        "Web sitesine bağlanılıyor": "Connecting to website",
        "Ev sayısı bulunamadı": "Apartment count not found",
        "Bağlantı hatası": "Connection error",
        "Zaman aşımı": "Timeout",
        "Kullanıcı tarafından": "By user"
    }
    
    simdi = datetime.now()
    with open(DETAYLI_LOG_DOSYASI, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Ev sayısı içeren detayları özel olarak işle
        if "Ev sayısı:" in detay:
            detay = detay.replace("Ev sayısı:", "Apartment count:")
        
        writer.writerow([
            simdi.strftime('%Y-%m-%d'),
            simdi.strftime('%H:%M:%S'),
            islem_map.get(islem, islem),
            durum_map.get(durum, durum),
            detay_map.get(detay, detay)
        ])

def email_gonder(baslik, mesaj):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = baslik
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO

        html_content = f"""
        <html>
        <body>
            <h2>SAGA Ev Bildirimi</h2>
            <p><strong>{mesaj}</strong></p>
            <p>Filtre: {', '.join(ODA_SAYILARI)} oda</p>
            <p>Detaylar için <a href="{SAGA_URL}">SAGA web sitesini</a> ziyaret edin.</p>
            <hr>
            <p><small>Bu e-posta otomatik olarak gönderilmiştir. {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"{datetime.now().strftime('%H:%M:%S')} - E-posta başarıyla gönderildi")
        detayli_log_ekle("E-posta", "Başarılı", "Bildirim gönderildi")
        
    except Exception as e:
        print(f"{datetime.now().strftime('%H:%M:%S')} - E-posta gönderilemedi: {str(e)}")
        detayli_log_ekle("E-posta", "Hata", str(e))

def bildirim_goster(mesaj):
    print(f"{datetime.now().strftime('%H:%M:%S')} - {mesaj}")
    email_gonder("SAGA Ev Bildirimi", mesaj)

def ev_sayisini_kontrol_et():
    try:
        print(f"\n{datetime.now().strftime('%H:%M:%S')} - Kontrol başlıyor...")
        print("Web sitesine bağlanılıyor...")
        
        response = session.get(SAGA_URL, headers=HEADERS, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # data-rooms attribute'u olan tüm elementleri bul
            ev_elementleri = soup.find_all(attrs={"data-rooms": True})
            print(f"\nToplam {len(ev_elementleri)} ev bulundu")
            
            # Önce filtreye uyan evleri bul
            filtreye_uyan_evler = []
            filtreye_uyan_ev_sayisi = 0
            
            # Her ev elementi için
            for element in ev_elementleri:
                oda_sayisi = element.get('data-rooms')
                print(f"\nEv bulundu - Oda sayısı: {oda_sayisi}")
                
                if oda_sayisi in ODA_SAYILARI:
                    print("✓ Filtreye uygun!")
                    filtreye_uyan_ev_sayisi += 1
                    
                    # Ev detaylarını topla
                    ev_detay = {}
                    
                    # Tüm parent div'leri kontrol et
                    for parent in element.find_parents('div'):
                        # a tag'lerini kontrol et
                        for a in parent.find_all('a'):
                            h3 = a.find('h3')
                            if h3 and 'text-primary' in h3.get('class', []):
                                ev_detay['baslik'] = h3.get_text().strip()
                                print(f"Başlık bulundu: {ev_detay['baslik']}")
                                break
                        if 'baslik' in ev_detay:
                            break
                    
                    # Zimmer
                    ev_detay['zimmer'] = oda_sayisi
                    
                    # m²
                    metrekare_elementi = element.find_parent('div').find(attrs={"data-livingspace": True})
                    if metrekare_elementi:
                        ev_detay['m2'] = metrekare_elementi.get('data-livingspace')
                        print(f"m² bulundu: {ev_detay['m2']}")
                    
                    # Gesamtmiete
                    kira_elementi = element.find_parent('div').find(attrs={"data-fullcosts": True})
                    if kira_elementi:
                        ev_detay['gesamtmiete'] = kira_elementi.get('data-fullcosts')
                        print(f"Gesamtmiete bulundu: {ev_detay['gesamtmiete']}")
                    
                    filtreye_uyan_evler.append(ev_detay)
                else:
                    print("✗ Filtreye uygun değil")
            
            print(f"\nToplam {filtreye_uyan_ev_sayisi} ev filtreye uyuyor")
            return filtreye_uyan_ev_sayisi, filtreye_uyan_evler
            
        else:
            print(f"\nHTTP hatası: {response.status_code}")
            return 0, []
            
    except requests.exceptions.ConnectionError:
        print("\nBağlantı hatası")
        return 0, []
    except requests.exceptions.Timeout:
        print("\nBağlantı zaman aşımına uğradı")
        return 0, []
    except Exception as e:
        print(f"\nBeklenmeyen hata: {str(e)}")
        return 0, []

def e_posta_gonder(ev_sayisi, uygun_evler):
    try:
        # E-posta ayarlarını kontrol et
        if not all([EMAIL_FROM, EMAIL_PASSWORD]):
            print("HATA: E-posta ayarları eksik!")
            return False
            
        # Alıcı e-posta adreslerini ayır
        alici_listesi = [email.strip() for email in EMAIL_TO.split(',')]
        if not alici_listesi:
            print("HATA: Alıcı e-posta adresi yok!")
            return False
            
        print(f"\n{datetime.now().strftime('%H:%M:%S')} - E-posta gönderiliyor...")
        
        # Ev detaylarını formatla
        ev_detaylari = []
        for ev in uygun_evler:
            detay = f"""
            {ev.get('baslik', 'Başlık bulunamadı')}
            Zimmer: {ev.get('zimmer', 'Bulunamadı')}
            m²: {ev.get('m2', 'Bulunamadı')}
            Gesamtmiete: {ev.get('gesamtmiete', 'Bulunamadı')} €
            """
            ev_detaylari.append(detay)
        
        # E-posta içeriğini hazırla
        konu = f"SAGA Wohnung Bildirimi - {ev_sayisi} Yeni İlan"
        icerik = f"""
        Merhaba,

        SAGA Wohnung web sitesinde {ev_sayisi} yeni ilan bulundu!

        Filtreleme kriterleri:
        - Oda sayıları: {', '.join(ODA_SAYILARI)}

        Bulunan ilanlar:
        {chr(10).join(ev_detaylari)}

        İlanları görüntülemek için: {SAGA_URL}

        Bu e-posta otomatik olarak gönderilmiştir.
        """
        
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as sunucu:
                sunucu.ehlo()
                sunucu.starttls()
                sunucu.ehlo()
                sunucu.login(EMAIL_FROM, EMAIL_PASSWORD)
                
                # Her alıcıya ayrı e-posta gönder
                for alici in alici_listesi:
                    try:
                        mesaj = MIMEText(icerik)
                        mesaj['Subject'] = konu
                        mesaj['From'] = EMAIL_FROM
                        mesaj['To'] = alici
                        
                        sunucu.send_message(mesaj)
                        print(f"✓ {alici} adresine gönderildi")
                    except Exception as e:
                        print(f"✗ {alici} adresine gönderilemedi: {str(e)}")
            
            print(f"\n{datetime.now().strftime('%H:%M:%S')} - E-posta işlemi tamamlandı!")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"\nSMTP Kimlik Doğrulama Hatası: {str(e)}")
            return False
            
        except smtplib.SMTPException as e:
            print(f"\nSMTP Hatası: {str(e)}")
            return False
            
    except Exception as e:
        print(f"\nBeklenmeyen Hata: {str(e)}")
        return False

def main():
    print("\n=== SAGA EV TAKİP SİSTEMİ ===")
    print("Versiyon: 5.1 - 2025-06-12")
    print(f"Her {KONTROL_ARALIĞI} dakikada bir kontrol edilecek")
    print(f"Filtre: {', '.join(ODA_SAYILARI)} oda")
    print("BeautifulSoup ile detaylı filtreleme aktif")
    print("Sadece e-posta bildirimleri aktif")
    print("Sistem başlatıldı...\n")
    
    son_ev_sayisi = 0
    
    while True:
        try:
            ev_sayisi, uygun_evler = ev_sayisini_kontrol_et()
            
            if ev_sayisi > son_ev_sayisi:
                print(f"\n{datetime.now().strftime('%H:%M:%S')} - Yeni ilanlar bulundu!")
                if e_posta_gonder(ev_sayisi, uygun_evler):
                    son_ev_sayisi = ev_sayisi
            else:
                print(f"\n{datetime.now().strftime('%H:%M:%S')} - Yeni ilan bulunamadı.")
            
            sonraki_kontrol = datetime.now() + timedelta(minutes=KONTROL_ARALIĞI)
            print(f"\nBir sonraki kontrol: {sonraki_kontrol.strftime('%H:%M:%S')}")
            time.sleep(KONTROL_ARALIĞI * 60)
            
        except KeyboardInterrupt:
            print("\n\nProgram kullanıcı tarafından durduruldu.")
            break
        except Exception as e:
            print(f"\nBeklenmeyen hata: {str(e)}")
            time.sleep(60)  # Hata durumunda 1 dakika bekle

if __name__ == "__main__":
    main() 