import time
import random
import os
from playwright.sync_api import Page, BrowserContext, TimeoutError as PWTimeout
import config
from modules.logger import get_logger

log = get_logger("pegasus")

GIRIS_URL = "https://acente.flypgs.com/"
ANA_EKRAN_URL = "acente.flypgs.com/MemberRezvEntry.jsp"
GECICI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gecici")

# Havalimanı kod → görünen metin eşlemesi (dropdown arama için)
HAVALIMANI_ARAMA = {
    "IST": "İstanbul",
    "SAW": "Sabiha",
    "ESB": "Ankara",
    "ANK": "Ankara",
    "ADB": "İzmir",
    "AYT": "Antalya",
    "BJV": "Bodrum",
    "TZX": "Trabzon",
    "SZF": "Samsun",
    "GZT": "Gaziantep",
    "DLM": "Dalaman",
    "ADA": "Adana",
    "KYA": "Konya",
    "ERZ": "Erzurum",
    "MLX": "Malatya",
}


def _bekle(min_s=None, max_s=None):
    mn = min_s or config.INSAN_GIBI_BEKLE_MIN
    mx = max_s or config.INSAN_GIBI_BEKLE_MAX
    time.sleep(random.uniform(mn, mx))


def _ekran_goruntüsü(sayfa: Page, ad: str):
    os.makedirs(GECICI_DIR, exist_ok=True)
    yol = os.path.join(GECICI_DIR, f"{ad}.png")
    sayfa.screenshot(path=yol, full_page=True)
    log.info(f"Screenshot: {yol}")
    return yol


def pegasus_giris_baslat(konteks: BrowserContext, sayfa: Page) -> dict:
    """
    Pegasus acentesi giriş sayfasını açar, kullanıcı adı+şifre doldurur,
    'Üye Girişi' butonuna basar ve SMS bekleme durumuna geçer.

    Döner:
        {"durum": "sms_bekleniyor"} — başarı
        {"durum": "hata", "mesaj": str}
    """
    try:
        log.info("Pegasus giriş sayfası açılıyor...")
        sayfa.goto(GIRIS_URL, wait_until="domcontentloaded", timeout=30000)

        # USERNAME alanı görünene kadar bekle — sayfa JS ile yükleniyor
        log.info("USERNAME alanı bekleniyor...")
        sayfa.wait_for_selector("input[name='USERNAME']", timeout=30000)
        _bekle(0.5, 1.0)

        # Kullanıcı adı ve şifre doldur
        sayfa.fill("input[name='USERNAME']", config.PEGASUS_KULLANICI)
        _bekle(0.3, 0.7)
        sayfa.fill("input[name='PASSWORD']", config.PEGASUS_SIFRE)
        _bekle(0.5, 1.0)

        _ekran_goruntüsü(sayfa, "01_kimlik_doldu")

        # Üye Girişi butonunu bul — farklı stratejiler dene
        buton = _uve_girisi_butonu_bul(sayfa)
        if buton is None:
            # Son çare: formu JS ile gönder
            log.warning("Buton bulunamadı, form JS ile submit ediliyor...")
            sayfa.evaluate("document.querySelector('form').submit()")
        else:
            buton.click()
            log.info("'Üye Girişi' butonu tıklandı.")

        _ekran_goruntüsü(sayfa, "02_buton_sonrasi")

        # SMS butonunu bekle (giriş sonrası ekran)
        log.info("SMS Gönder butonu bekleniyor...")
        sayfa.wait_for_selector("button:has-text('SMS Gönder')", timeout=20000)
        sayfa.click("button:has-text('SMS Gönder')")
        log.info("SMS Gönder tıklandı.")
        _ekran_goruntüsü(sayfa, "03_sms_gonderildi")

        return {"durum": "sms_bekleniyor"}

    except PWTimeout as e:
        log.error(f"Timeout: {e}")
        _ekran_goruntüsü(sayfa, "hata_timeout")
        return {"durum": "hata", "mesaj": f"Zaman aşımı: {e}"}
    except Exception as e:
        log.error(f"Giriş hatası: {e}")
        _ekran_goruntüsü(sayfa, "hata_genel")
        return {"durum": "hata", "mesaj": str(e)}


def _uve_girisi_butonu_bul(sayfa: Page):
    """
    'Üye Girişi' butonunu birden fazla yöntemle arar.
    Playwright ElementHandle veya None döner.
    """
    stratejiler = [
        # 1. Metin içeriğine göre
        lambda: sayfa.wait_for_selector("button:has-text('Üye Girişi')", timeout=10000),
        # 2. Büyük/küçük harf duyarsız JS ile
        lambda: _js_buton_bul(sayfa, "üye girişi"),
        # 3. type=submit butonu
        lambda: sayfa.wait_for_selector("button[type='submit']", timeout=5000),
        # 4. input[type=submit]
        lambda: sayfa.wait_for_selector("input[type='submit']", timeout=5000),
        # 5. Form içindeki ilk buton
        lambda: sayfa.wait_for_selector("form button", timeout=5000),
    ]

    for i, strateji in enumerate(stratejiler):
        try:
            eleman = strateji()
            if eleman:
                log.info(f"Buton strateji {i+1} ile bulundu.")
                return eleman
        except Exception:
            continue

    log.warning("Hiçbir strateji ile buton bulunamadı.")
    return None


def _js_buton_bul(sayfa: Page, aranan: str):
    """JavaScript ile metin içeriğine göre buton arar ve tıklar."""
    sonuc = sayfa.evaluate(f"""
        () => {{
            const buttons = Array.from(document.querySelectorAll('button, input[type=submit], a'));
            const btn = buttons.find(b => b.textContent.toLowerCase().includes('{aranan}') || (b.value || '').toLowerCase().includes('{aranan}'));
            if (btn) {{ btn.click(); return true; }}
            return false;
        }}
    """)
    return sonuc or None


def pegasus_otp_gir(sayfa: Page, otp_kodu: str) -> dict:
    """OTP kodunu girer ve giriş yap butonuna basar. Yeni sayfayı bekler."""
    try:
        sayfa.wait_for_selector("input[name='OTP_INPUT']", timeout=20000)
        sayfa.fill("input[name='OTP_INPUT']", otp_kodu)
        _bekle(0.3, 0.7)
        sayfa.click("button:has-text('Giriş yap')")
        log.info("OTP girildi, Giriş yap tıklandı.")
        _ekran_goruntüsü(sayfa, "04_otp_sonrasi")
        return {"durum": "tamam"}
    except Exception as e:
        log.error(f"OTP hata: {e}")
        return {"durum": "hata", "mesaj": str(e)}


def pegasus_yeni_sayfa_bekle(konteks: BrowserContext, timeout=30000) -> Page | None:
    """Giriş sonrası açılan yeni pencereyi yakalar."""
    try:
        with konteks.expect_page(timeout=timeout) as yeni_sayfa_bilgi:
            pass
        yeni_sayfa = yeni_sayfa_bilgi.value
        yeni_sayfa.wait_for_load_state("domcontentloaded")
        log.info(f"Yeni sayfa yakalandı: {yeni_sayfa.url}")
        return yeni_sayfa
    except Exception as e:
        log.error(f"Yeni sayfa yakalanamadı: {e}")
        return None


def pegasus_ucus_ara(sayfa: Page, arama: dict) -> list[dict]:
    """
    Ana ekranda uçuş arama formunu doldurur ve sonuçları döner.

    arama = {
        "nereden": "IST", "nereye": "ESB",
        "gidis_tarihi": "2025-07-15", "donus_tarihi": null,
        "yetiskin": 1, "cocuk": 0, "bebek": 0, "tek_yon": true
    }
    """
    try:
        log.info(f"Uçuş aranıyor: {arama}")
        sayfa.wait_for_load_state("domcontentloaded")
        _ekran_goruntüsü(sayfa, "05_ana_ekran")

        # Tek yön sekmesi
        if arama.get("tek_yon", True):
            _sekme_sec(sayfa, "Tek Yön")
        else:
            _sekme_sec(sayfa, "Gidiş - Dönüş")

        # Nereden
        _sehir_sec(sayfa, "nereden", arama["nereden"])
        _bekle(0.5, 1.0)

        # Nereye
        _sehir_sec(sayfa, "nereye", arama["nereye"])
        _bekle(0.5, 1.0)

        # Gidiş tarihi
        _tarih_sec(sayfa, "gidis", arama["gidis_tarihi"])
        _bekle(0.3, 0.7)

        # Dönüş tarihi
        if not arama.get("tek_yon", True) and arama.get("donus_tarihi"):
            _tarih_sec(sayfa, "donus", arama["donus_tarihi"])

        # Yolcu sayıları
        _yolcu_sec(sayfa, arama.get("yetiskin", 1), arama.get("cocuk", 0), arama.get("bebek", 0))

        _ekran_goruntüsü(sayfa, "06_form_doldu")

        # Ara butonuna bas
        sayfa.click("button:has-text('Ara')")
        _bekle(1.0, 2.0)

        # Uyarı popup kontrolü
        try:
            devam = sayfa.wait_for_selector("button:has-text('Devam')", timeout=5000)
            if devam:
                devam.click()
                log.info("Uyarı popup'ı kapatıldı.")
        except PWTimeout:
            pass

        # Sonuç sayfası yüklensin
        sayfa.wait_for_url("**/MemberRezvResults.jsp**", timeout=30000)
        log.info("Sonuç sayfasına ulaşıldı.")
        _ekran_goruntüsü(sayfa, "07_sonuclar")

        return _ucus_sonuclari_oku(sayfa)

    except Exception as e:
        log.error(f"Uçuş arama hatası: {e}")
        _ekran_goruntüsü(sayfa, "hata_arama")
        return []


def _sekme_sec(sayfa: Page, sekme_adi: str):
    try:
        sayfa.click(f"text='{sekme_adi}'")
    except Exception:
        log.warning(f"'{sekme_adi}' sekmesi bulunamadı, devam ediliyor.")


def _sehir_sec(sayfa: Page, alan: str, kod: str):
    arama_metni = HAVALIMANI_ARAMA.get(kod, kod)
    # Alan adını içeren input'u bul (placeholder veya id)
    try:
        girdi = sayfa.locator(f"input[placeholder*='{alan.title()}'], input[id*='{alan}']").first
        girdi.clear()
        girdi.type(arama_metni, delay=80)
        _bekle(0.5, 1.0)
        # Dropdown'dan ilk uygun seçeneği seç
        sayfa.wait_for_selector(".autocomplete-result, li[class*='result'], .dropdown-item", timeout=8000)
        sayfa.locator(f"text='{kod}'").first.click()
    except Exception as e:
        log.warning(f"Şehir seçimi ({alan}={kod}) hatası: {e}")


def _tarih_sec(sayfa: Page, yon: str, tarih: str):
    """tarih: YYYY-MM-DD formatında"""
    try:
        # Tarih input'una yaz (bazı sayfalarda direkt type kabul eder)
        girdi = sayfa.locator(f"input[name*='{yon.upper()}'], input[id*='{yon}Date']").first
        girdi.fill(tarih)
    except Exception as e:
        log.warning(f"Tarih seçimi ({yon}={tarih}) hatası: {e}")


def _yolcu_sec(sayfa: Page, yetiskin: int, cocuk: int, bebek: int):
    try:
        # Yolcu dropdown'u aç
        sayfa.locator("text='Kişi'").first.click()
        _bekle(0.3, 0.6)
        # Yetişkin sayısını ayarla (varsayılan 1 gelir, gerekirse artır)
        for _ in range(yetiskin - 1):
            sayfa.locator("button[id*='adult'][class*='plus'], button:has-text('+')").first.click()
        for _ in range(cocuk):
            sayfa.locator("button[id*='child'][class*='plus']").first.click()
        for _ in range(bebek):
            sayfa.locator("button[id*='infant'][class*='plus']").first.click()
    except Exception as e:
        log.warning(f"Yolcu seçimi hatası: {e}")


def _ucus_sonuclari_oku(sayfa: Page) -> list[dict]:
    """Sonuç sayfasındaki uçuşları listeler."""
    ucuslar = []
    try:
        # "Bütün Fiyatları Göster" linklerine tıkla
        fiyat_linkleri = sayfa.locator("text='Bütün Fiyatları Göster'").all()
        for link in fiyat_linkleri:
            try:
                link.click()
                _bekle(0.3, 0.6)
            except Exception:
                pass

        # Her uçuş satırını oku
        satirlar = sayfa.locator(".flight-row, tr[class*='flight'], .result-row").all()
        for i, satir in enumerate(satirlar):
            try:
                metin = satir.inner_text()
                ucuslar.append({"index": i + 1, "ham_metin": metin.strip()})
            except Exception:
                pass

        if not ucuslar:
            # Genel sayfa metnini al
            log.warning("Yapılandırılmış uçuş satırları bulunamadı, sayfa metni alınıyor.")
            ucuslar = [{"index": 0, "ham_metin": sayfa.inner_text("body")[:3000]}]

    except Exception as e:
        log.error(f"Sonuç okuma hatası: {e}")

    log.info(f"{len(ucuslar)} uçuş bulundu.")
    return ucuslar


def pegasus_paket_sec(sayfa: Page, ucus_index: int, paket: str) -> dict:
    """
    Belirtilen uçuştaki paketi seçer (Light / Süper Eko / Avantaj / Comfort Flex).
    Döner: {"durum": "tamam"} veya {"durum": "hata", "mesaj": str}
    """
    try:
        paket_map = {
            "light": 0, "süper eko": 1, "avantaj": 2, "comfort flex": 3,
        }
        paket_idx = paket_map.get(paket.lower(), 0)

        # Uçuş satırını bul
        satirlar = sayfa.locator(".flight-row, tr[class*='flight'], .result-row").all()
        if ucus_index - 1 >= len(satirlar):
            return {"durum": "hata", "mesaj": "Geçersiz uçuş numarası"}

        satir = satirlar[ucus_index - 1]
        paket_butonlari = satir.locator("button, input[type=radio]").all()
        if paket_idx < len(paket_butonlari):
            paket_butonlari[paket_idx].click()
        else:
            log.warning("Paket butonu bulunamadı, ilk buton seçiliyor.")
            paket_butonlari[0].click()

        _bekle(1.0, 2.0)
        log.info(f"Paket seçildi: {paket}")
        return {"durum": "tamam"}
    except Exception as e:
        log.error(f"Paket seçim hatası: {e}")
        return {"durum": "hata", "mesaj": str(e)}


def pegasus_yolcu_bilgisi_gir(sayfa: Page, yolcular: list[dict]) -> dict:
    """
    Yolcu bilgilerini (ad, soyad, TC, doğum tarihi, cinsiyet) form'a girer.
    yolcular = [{"ad": "Ali", "soyad": "Yılmaz", "tc": "12345678901",
                 "dogum_tarihi": "1990-05-20", "cinsiyet": "BAY", "tip": "yetiskin"}, ...]
    """
    try:
        sayfa.wait_for_url("**/RezvPaxEntry.jsp**", timeout=20000)
        _ekran_goruntüsü(sayfa, "08_yolcu_formu")

        for i, yolcu in enumerate(yolcular):
            _yolcu_formu_doldur(sayfa, i, yolcu)

        # İletişim bilgileri
        _iletisim_doldur(sayfa)

        # "İlk Yolcu Bilgilerini Getir" checkbox
        try:
            cb = sayfa.locator("input[type='checkbox']:near(:text('İlk Yolcu'))").first
            if not cb.is_checked():
                cb.check()
        except Exception:
            pass

        # Onay checkbox'ları — sadece zorunlu olanı işaretle
        _onay_checkbox(sayfa)

        _ekran_goruntüsü(sayfa, "09_yolcu_doldu")
        sayfa.click("button:has-text('Devam'), button:has-text('İleri'), button[type='submit']")
        return {"durum": "tamam"}

    except Exception as e:
        log.error(f"Yolcu bilgisi hatası: {e}")
        _ekran_goruntüsü(sayfa, "hata_yolcu")
        return {"durum": "hata", "mesaj": str(e)}


def _yolcu_formu_doldur(sayfa: Page, idx: int, yolcu: dict):
    try:
        # Cinsiyet (sadece yetişkinde)
        if yolcu.get("tip") == "yetiskin":
            cinsiyet_sel = sayfa.locator(f"select[name*='GENDER'][data-index='{idx}'], select[id*='gender{idx}']").first
            cinsiyet_sel.select_option(label=yolcu.get("cinsiyet", "BAY"))

        sayfa.fill(f"input[name*='FIRSTNAME'][data-index='{idx}'], input[id*='firstName{idx}']", yolcu["ad"])
        sayfa.fill(f"input[name*='LASTNAME'][data-index='{idx}'], input[id*='lastName{idx}']", yolcu["soyad"])

        if yolcu.get("tc"):
            sayfa.fill(f"input[name*='IDENTITY'][data-index='{idx}'], input[id*='identity{idx}']", yolcu["tc"])

        if yolcu.get("dogum_tarihi"):
            # YYYY-MM-DD → GG/AA/YYYY
            parca = yolcu["dogum_tarihi"].split("-")
            if len(parca) == 3:
                gun_ay_yil = f"{parca[2]}/{parca[1]}/{parca[0]}"
                sayfa.fill(f"input[name*='BIRTHDATE'][data-index='{idx}'], input[id*='birthDate{idx}']", gun_ay_il)

    except Exception as e:
        log.warning(f"Yolcu {idx} form hatası: {e}")


def _iletisim_doldur(sayfa: Page):
    try:
        sayfa.fill("input[name*='PHONE'], input[id*='phone']", config.ACENTE_TEL)
        sayfa.fill("input[name*='EMAIL'], input[id*='email']", config.ACENTE_EMAIL)
    except Exception as e:
        log.warning(f"İletişim doldurma hatası: {e}")


def _onay_checkbox(sayfa: Page):
    """Zorunlu onay kutularını işaretle; ücretli SMS'e (186,87 TRY) dokunma."""
    try:
        checkboxlar = sayfa.locator("input[type='checkbox']").all()
        for cb in checkboxlar:
            try:
                etiket = cb.evaluate("el => el.closest('label')?.textContent || el.nextElementSibling?.textContent || ''")
                # Ücretli SMS'i atla
                if "186" in etiket or "sms" in etiket.lower() and "tl" in etiket.lower():
                    log.info(f"Ücretli SMS checkbox'ı atlandı: {etiket[:60]}")
                    continue
                if "onaylıyorum" in etiket.lower() or "kabul ediyorum" in etiket.lower():
                    if not cb.is_checked():
                        cb.check()
                        log.info(f"Onay checkbox işaretlendi: {etiket[:60]}")
            except Exception:
                pass
    except Exception as e:
        log.warning(f"Onay checkbox hatası: {e}")


def pegasus_ek_hizmet_atla(sayfa: Page) -> dict:
    """Ek hizmetler sayfasını geçer (hiçbir şey seçmeden)."""
    try:
        sayfa.wait_for_url("**/SellSsr.jsp**", timeout=20000)
        _ekran_goruntüsü(sayfa, "10_ek_hizmet")
        sayfa.click("button:has-text('Ödemeye Devam Et'), button:has-text('Devam Et')")
        log.info("Ek hizmetler atlandı.")
        return {"durum": "tamam"}
    except Exception as e:
        log.error(f"Ek hizmet atlama hatası: {e}")
        return {"durum": "hata", "mesaj": str(e)}


def pegasus_pnr_al(sayfa: Page) -> dict:
    """
    Ödeme sayfasında durur ve PNR/rezervasyon numarasını ekrandan okur.
    Bot bu aşamada durur — ödeme kullanıcıya bırakılır.
    """
    try:
        _bekle(2.0, 3.0)
        _ekran_goruntüsü(sayfa, "11_odeme_sayfasi")

        # PNR aramak için sayfa metnini tara
        metin = sayfa.inner_text("body")
        import re
        pnr_eslesme = re.search(r"\b([A-Z0-9]{6})\b", metin)
        pnr = pnr_eslesme.group(1) if pnr_eslesme else "Bulunamadı"

        log.info(f"PNR: {pnr}")
        return {"durum": "tamam", "pnr": pnr, "url": sayfa.url}
    except Exception as e:
        log.error(f"PNR alma hatası: {e}")
        return {"durum": "hata", "mesaj": str(e)}
