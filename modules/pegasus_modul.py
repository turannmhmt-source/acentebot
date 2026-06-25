"""
pegasus_modul.py — Pegasus acente otomasyonu
Fonksiyonlar: giris_baslat, otp_gir, ucus_sorgula, paket_sec, yolcu_doldur, rezervasyon_bilgisi_al
"""

import re
import time
import random
import os
from modules.logger import get_logger

log = get_logger("pegasus")

PEGASUS_URL = "https://acente.flypgs.com/"
PEGASUS_ANA_URL = "https://acente.flypgs.com/MemberRezvEntry.jsp"
GECICI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gecici")

SEHIR_ARAMA = {
    "IST": "İstanbul Tümü",
    "SAW": "Sabiha",
    "ESB": "Ankara",
    "ADB": "İzmir",
    "AYT": "Antalya",
    "BJV": "Bodrum",
    "DLM": "Dalaman",
    "TZX": "Trabzon",
    "GZT": "Gaziantep",
    "ADA": "Adana",
    "ASR": "Kayseri",
    "SZF": "Samsun",
    "DIY": "Diyarbakır",
    "VAN": "Van",
    "MLX": "Malatya",
    "ERZ": "Erzurum",
    "HTY": "Hatay",
    "KYA": "Konya",
    "NAV": "Nevşehir",
    "SJJ": "Saraybosna",
}

PAKET_ICERIKLERI = {
    "Light": "Koltuk altı çanta (40x30x15cm 3kg), Bagaj yok",
    "Süper Eko": "Koltuk altı çanta, Kabin bagaj (55x40x23cm), 20kg bagaj",
    "Avantaj": "Koltuk altı çanta, Kabin bagaj, 20kg bagaj, Koltuk seçimi",
    "Comfort Flex": "Koltuk altı çanta, Kabin bagaj, 20kg bagaj, Esnek değişiklik, Koltuk seçimi",
}

ACENTE_TEL_ALAN = "555"
ACENTE_TEL_NO = "0094805"
ACENTE_EMAIL = "masaraturizm@gmail.com"


def _bekle(mn=1.0, mx=2.5):
    time.sleep(random.uniform(mn, mx))


def _ss(sayfa, ad: str) -> str:
    os.makedirs(GECICI_DIR, exist_ok=True)
    from datetime import datetime
    dosya = os.path.join(GECICI_DIR, f"{ad}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    try:
        sayfa.screenshot(path=dosya, full_page=True)
        log.info(f"Screenshot: {dosya}")
    except Exception as e:
        log.warning(f"Screenshot hatası: {e}")
    return dosya


# ─────────────────────────────────────────────────────────────────────────────
# 1. GİRİŞ
# ─────────────────────────────────────────────────────────────────────────────

def pegasus_giris_baslat(tarayici) -> tuple:
    """
    Pegasus giriş sayfasını açar, kimlik bilgilerini doldurur,
    Enter ile submit eder ve SMS kodunu bekler.
    Döner: (konteks, sayfa) veya (None, None)
    """
    import config as cfg
    sayfa = None
    konteks = None
    try:
        # Yeni context aç
        konteks = tarayici.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        sayfa = konteks.new_page()
        log.info("Pegasus açılıyor...")

        # Sayfayı aç — domcontentloaded yeterli, networkidle bekleme
        sayfa.goto(PEGASUS_URL, wait_until="domcontentloaded", timeout=30000)
        _bekle(2, 3)

        # USERNAME alanı görünene kadar bekle
        log.info("USERNAME bekleniyor...")
        sayfa.wait_for_selector("input[name='USERNAME']", state="visible", timeout=20000)
        log.info(f"Sayfa yüklendi: {sayfa.url}")

        # Kullanıcı adı ve şifre doldur
        sayfa.fill("input[name='USERNAME']", cfg.PEGASUS_KULLANICI)
        _bekle(0.5, 1.0)
        sayfa.fill("input[name='PASSWORD']", cfg.PEGASUS_SIFRE)
        _bekle(0.5, 1.0)
        log.info(f"Kimlik dolduruldu: {cfg.PEGASUS_KULLANICI}")

        _ss(sayfa, "01_kimlik_doldu")

        # Enter ile submit — buton aramadan
        sayfa.press("input[name='PASSWORD']", "Enter")
        log.info("Enter basıldı — submit bekleniyor...")
        _bekle(3, 5)

        _ss(sayfa, "02_enter_sonrasi")

        # OTP alanı görünene kadar bekle
        try:
            sayfa.wait_for_selector("input[name='OTP_INPUT']", state="visible", timeout=10000)
            log.info("OTP ekranı açıldı ✅")
        except Exception:
            log.warning("OTP direkt açılmadı, buton aranıyor...")
            _buton_tikla(sayfa)
            _bekle(3, 5)
            sayfa.wait_for_selector("input[name='OTP_INPUT']", state="visible", timeout=15000)
            log.info("OTP ekranı açıldı ✅")

        # SMS Gönder — Playwright get_by_text (element tipi fark etmez)
        try:
            sayfa.get_by_text("SMS Gönder", exact=True).click(timeout=5000)
            log.info("SMS Gönder tıklandı ✅")
            _bekle(3, 4)
        except Exception:
            try:
                sayfa.locator("text=SMS Gönder").first.click(timeout=5000)
                log.info("SMS Gönder tıklandı ✅ (locator)")
                _bekle(3, 4)
            except Exception as e:
                log.warning(f"SMS Gönder tıklanamadı: {e}")

        _ss(sayfa, "03_sms_gonderildi")
        log.info("SMS gönderildi — OTP bekleniyor")
        return konteks, sayfa

    except Exception as e:
        log.error(f"Giriş hatası: {e}")
        if sayfa:
            _ss(sayfa, "hata_giris")
        return None, None


def _buton_tikla(sayfa) -> bool:
    """Üye Girişi butonunu birden fazla yöntemle tıklamayı dener."""
    # Yöntem 1: Metin ile
    try:
        btn = sayfa.query_selector("button:has-text('Üye Girişi')")
        if btn and btn.is_visible():
            btn.click()
            log.info("Buton (metin) tıklandı ✅")
            return True
    except Exception:
        pass

    # Yöntem 2: submit input
    try:
        btn = sayfa.query_selector("input[type='submit']")
        if btn and btn.is_visible():
            btn.click()
            log.info("Buton (submit input) tıklandı ✅")
            return True
    except Exception:
        pass

    # Yöntem 3: JavaScript — tüm buton benzeri elementler
    try:
        sonuc = sayfa.evaluate("""
            () => {
                const elems = Array.from(document.querySelectorAll(
                    'button, input[type=submit], a[href], div[onclick], span[onclick]'
                ));
                for (const el of elems) {
                    const t = (el.textContent || el.value || '').trim().toLowerCase();
                    if (t.includes('giri') || t.includes('login')) {
                        el.click();
                        return t;
                    }
                }
                return null;
            }
        """)
        if sonuc:
            log.info(f"Buton (JS) tıklandı ✅: {sonuc}")
            return True
    except Exception:
        pass

    # Yöntem 4: Tab + Enter
    try:
        sayfa.focus("input[name='PASSWORD']")
        for _ in range(5):
            sayfa.keyboard.press("Tab")
            _bekle(0.2, 0.3)
            tag = sayfa.evaluate("() => document.activeElement?.tagName || ''")
            if tag in ("BUTTON", "A"):
                sayfa.keyboard.press("Enter")
                log.info(f"Buton (Tab+Enter, {tag}) tıklandı ✅")
                return True
    except Exception:
        pass

    # Yöntem 5: form.submit()
    try:
        ok = sayfa.evaluate("() => { const f = document.querySelector('form'); if(f){f.submit();return true;} return false; }")
        if ok:
            log.info("form.submit() ✅")
            return True
    except Exception:
        pass

    log.error("Buton tıklanamadı — tüm yöntemler başarısız")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 2. OTP
# ─────────────────────────────────────────────────────────────────────────────

def pegasus_otp_gir(konteks, sayfa, otp_kodu: str):
    """
    OTP kodunu girer, 'Giriş yap' butonuna basar,
    açılan yeni pencereyi döner. Başarısızsa None.
    """
    try:
        # SMS metninden kodu çıkar: "...aktivasyon kodunuz fxop 'dir"
        kod = _otp_cikart(otp_kodu)
        log.info(f"OTP: {kod}")

        sayfa.fill("input[name='OTP_INPUT']", kod)
        _bekle(0.5, 1.0)

        # Giriş yap — tıkla ve mevcut sayfada navigasyonu bekle
        try:
            sayfa.get_by_text("Giriş yap", exact=True).click(timeout=5000)
            log.info("Giriş yap tıklandı ✅")
        except Exception:
            try:
                sayfa.locator("text=Giriş yap").first.click(timeout=5000)
                log.info("Giriş yap tıklandı ✅ (locator)")
            except Exception:
                sayfa.press("input[name='OTP_INPUT']", "Enter")
                log.info("Giriş yap — Enter ✅")

        # Mevcut sayfada navigasyon veya yeni popup — ikisini de dene
        yeni_sayfa = None
        try:
            # Yeni popup pencere açılırsa yakala (kısa timeout)
            with konteks.expect_page(timeout=8000) as yeni_bilgi:
                pass
            yeni_sayfa = yeni_bilgi.value
            yeni_sayfa.wait_for_load_state("domcontentloaded", timeout=30000)
            log.info(f"Yeni pencere açıldı: {yeni_sayfa.url}")
        except Exception:
            # Popup yok — mevcut sayfada devam ediyor
            log.info("Popup yok, mevcut sayfada bekleniyor...")
            sayfa.wait_for_load_state("domcontentloaded", timeout=30000)
            _bekle(3, 5)
            yeni_sayfa = sayfa
            log.info(f"Mevcut sayfa URL: {sayfa.url}")

        _bekle(2, 3)
        _ss(yeni_sayfa, "04_ana_ekran")

        if "acente.flypgs.com" in yeni_sayfa.url:
            log.info("Ana ekran açıldı ✅")
            return yeni_sayfa
        else:
            log.error(f"Beklenmeyen URL: {yeni_sayfa.url}")
            return None

    except Exception as e:
        log.error(f"OTP hatası: {e}")
        if sayfa:
            _ss(sayfa, "hata_otp")
        return None


def _otp_cikart(metin: str) -> str:
    """
    SMS metninden OTP kodunu çıkarır.
    Örnek: "A297TQ34 ile login için aktivasyon kodunuz fxop 'dir"
    → "fxop"
    Düz sayı/harf kodu da desteklenir: "1234" → "1234"
    """
    metin = metin.strip()

    # "kodunuz XXXX 'dir" veya "kodunuz XXXX." kalıbı
    eslesme = re.search(r"kodunuz\s+([A-Za-z0-9]+)", metin, re.IGNORECASE)
    if eslesme:
        return eslesme.group(1)

    # Sadece sayı/harf kombinasyonu (4-8 karakter)
    eslesme = re.search(r"\b([A-Za-z0-9]{4,8})\b", metin)
    if eslesme:
        return eslesme.group(1)

    # Hiçbiri yoksa ham metni döndür
    return metin


# ─────────────────────────────────────────────────────────────────────────────
# 3. UÇUŞ SORGULAMA
# ─────────────────────────────────────────────────────────────────────────────

def pegasus_ucus_sorgula(sayfa, komut: dict) -> list:
    """
    Ana ekranda form doldurur, uçuş listesini döner.
    komut = {tip, nereden, nereye, tarih, yetiskin, cocuk, bebek, direkt_mi}
    """
    import config as cfg
    try:
        tip = komut.get("tip", "tek_yon")
        nereden = komut.get("nereden", "IST")
        nereye = komut.get("nereye", "")
        yetiskin = komut.get("yetiskin", 1)
        cocuk = komut.get("cocuk", 0)
        bebek = komut.get("bebek", 0)
        direkt_mi = komut.get("direkt_mi", True)

        log.info(f"Sorgu: {nereden}→{nereye} {tip}")

        sayfa.goto(PEGASUS_ANA_URL, wait_until="domcontentloaded", timeout=30000)
        _bekle(3, 4)
        _ss(sayfa, "05_ana_ekran")

        # Sayfadaki tüm visible input'ları logla (bir kez diagnostic)
        try:
            inputlar = sayfa.evaluate("""
                () => Array.from(document.querySelectorAll('input:not([type=hidden]),select,textarea'))
                    .filter(el => el.offsetParent !== null)
                    .map(el => el.tagName+'|'+el.type+'|'+el.name+'|'+el.id+'|'+el.placeholder)
            """)
            log.info(f"Ana ekran inputları: {inputlar[:15]}")
        except Exception:
            pass

        # Uçuş tipi
        if tip == "tek_yon":
            try:
                sayfa.click("a:has-text('Tek Yön'), li:has-text('Tek Yön')")
                _bekle(1, 2)
            except Exception:
                pass
        elif tip == "gidis_donus":
            try:
                sayfa.click("a:has-text('Gidiş - Dönüş')")
                _bekle(1, 2)
            except Exception:
                pass

        _sehir_sec(sayfa, nereden, "nereden")
        _bekle(1, 2)
        _sehir_sec(sayfa, nereye, "nereye")
        _bekle(1, 2)

        if tip == "tek_yon":
            _tarih_sec(sayfa, komut.get("tarih", ""), "gidis")
        else:
            _tarih_sec(sayfa, komut.get("gidis_tarihi", ""), "gidis")
            _bekle(0.5, 1)
            _tarih_sec(sayfa, komut.get("donus_tarihi", ""), "donus")
        _bekle(1, 2)

        _yolcu_sec(sayfa, yetiskin, cocuk, bebek)
        _bekle(1, 2)

        sayfa.click("button:has-text('Ara'), input[value='Ara']")
        _bekle(3, 5)

        # Uyarı popup
        try:
            sayfa.wait_for_selector("button:has-text('Devam')", timeout=6000)
            sayfa.click("button:has-text('Devam')")
            log.info("Popup geçildi")
            _bekle(3, 5)
        except Exception:
            pass

        # Sonuç sayfası
        try:
            sayfa.wait_for_url("**/MemberRezvResults**", timeout=30000)
        except Exception:
            sayfa.wait_for_load_state("networkidle", timeout=20000)

        _bekle(3, 5)
        return _sonuclari_oku(sayfa, nereden, nereye, direkt_mi, cfg)

    except Exception as e:
        log.error(f"Uçuş sorgulama hatası: {e}")
        _ss(sayfa, "hata_sorgula")
        return []


def _sehir_sec(sayfa, iata: str, tip: str):
    arama = SEHIR_ARAMA.get(iata, iata)
    # Sırayla denenecek selector'lar
    if tip == "nereden":
        adaylar = [
            "input[name='ORIGIN']", "input[name='origin']",
            "input[id*='origin']", "input[id*='Origin']",
            "input[id*='from']", "input[id*='From']",
            "input[placeholder*='Nereden']", "input[placeholder*='nereden']",
            "input[placeholder*='Kalkış']",
        ]
    else:
        adaylar = [
            "input[name='DESTINATION']", "input[name='destination']",
            "input[id*='destination']", "input[id*='Destination']",
            "input[id*='to']", "input[id*='To']",
            "input[placeholder*='Nereye']", "input[placeholder*='nereye']",
            "input[placeholder*='Varış']",
        ]

    girdi = None
    for sel in adaylar:
        try:
            el = sayfa.query_selector(sel)
            if el and el.is_visible():
                girdi = el
                log.info(f"Şehir alanı bulundu ({tip}): {sel}")
                break
        except Exception:
            continue

    if not girdi:
        log.warning(f"Şehir alanı bulunamadı ({tip}-{iata}), atlıyorum")
        return

    try:
        girdi.click()
        _bekle(0.3, 0.5)
        girdi.fill("")
        girdi.type(arama, delay=100)
        _bekle(1, 2)

        # Dropdown bekle ve seç
        dd_sels = [
            "[class*='suggestion'] li:first-child",
            "[class*='autocomplete'] li:first-child",
            "ul[class*='auto'] li:first-child",
            "[class*='dropdown'] li:first-child",
            "li[class*='result']:first-child",
        ]
        secildi = False
        for dd in dd_sels:
            try:
                sayfa.wait_for_selector(dd, timeout=3000)
                sayfa.click(dd)
                secildi = True
                break
            except Exception:
                continue

        if not secildi:
            sayfa.keyboard.press("ArrowDown")
            _bekle(0.3, 0.5)
            sayfa.keyboard.press("Enter")

        log.info(f"Şehir seçildi: {arama} ({tip})")
    except Exception as e:
        log.warning(f"Şehir seçim hatası ({tip}-{iata}): {e}")


def _tarih_sec(sayfa, tarih: str, tip: str):
    try:
        if not tarih:
            return
        p = tarih.split("-")
        if len(p) != 3:
            return
        gun, ay, yil = int(p[2]), int(p[1]), int(p[0])
        if tip == "gidis":
            sel = "input[id*='depart'], input[name*='depart'], input[placeholder*='Gidiş']"
        else:
            sel = "input[id*='return'], input[name*='return'], input[placeholder*='Dönüş']"
        sayfa.click(sel)
        _bekle(1, 2)
        _takvim_sec(sayfa, gun, ay, yil)
    except Exception as e:
        log.warning(f"Tarih hatası ({tip}): {e}")


def _takvim_sec(sayfa, gun: int, ay: int, yil: int):
    AYLAR = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",
              7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}
    try:
        for _ in range(24):
            _bekle(0.5, 1)
            baslik = sayfa.query_selector(
                "[class*='calendar-caption'], th[class*='month'], [class*='datepicker-title']"
            )
            if not baslik:
                break
            metin = baslik.inner_text()
            m_ay = m_yil = None
            for no, ad in AYLAR.items():
                if ad in metin:
                    m_ay = no
                    y = re.search(r'\d{4}', metin)
                    if y:
                        m_yil = int(y.group())
                    break
            if m_ay == ay and m_yil == yil:
                gunler = sayfa.query_selector_all(
                    "[class*='calendar'] td:not([class*='disabled']):not([class*='empty']), "
                    "[class*='datepicker'] td:not([class*='disabled'])"
                )
                for g in gunler:
                    if g.inner_text().strip() == str(gun):
                        g.click()
                        log.info(f"Tarih: {gun}.{ay}.{yil}")
                        return
            try:
                sayfa.click("[class*='calendar'] [class*='next'], th[class*='next'], button:has-text('>')")
            except Exception:
                break
    except Exception as e:
        log.warning(f"Takvim hatası: {e}")


def _yolcu_sec(sayfa, yetiskin: int, cocuk: int, bebek: int):
    try:
        try:
            sayfa.select_option("select[id*='adult'], select[name*='adult']", label=f"{yetiskin} Kişi")
        except Exception:
            pass
        _bekle(0.3, 0.5)
        try:
            sayfa.select_option("select[id*='child'], select[name*='child']", label=f"{cocuk} Çocuk")
        except Exception:
            pass
        _bekle(0.3, 0.5)
        try:
            sayfa.select_option("select[id*='infant'], select[name*='infant']", label=f"{bebek} Bebek")
        except Exception:
            pass
        log.info(f"Yolcu: {yetiskin}Y {cocuk}Ç {bebek}B")
    except Exception as e:
        log.warning(f"Yolcu hatası: {e}")


def _sonuclari_oku(sayfa, nereden, nereye, direkt_mi, cfg) -> list:
    try:
        sonuclar = []
        sayfa.wait_for_load_state("networkidle", timeout=20000)

        for link in sayfa.query_selector_all("a:has-text('Bütün Fiyatları Göster'), span:has-text('Bütün Fiyatları Göster')"):
            try:
                link.click()
                _bekle(0.5, 1)
            except Exception:
                pass

        _bekle(2, 3)
        _ss(sayfa, "05_sonuc_liste")

        satirlar = sayfa.query_selector_all(
            "tr:has(td):has([class*='flt']), tr:has(td[class*='flight']), "
            "[class*='flight-row'], table.table tbody tr"
        )
        log.info(f"{len(satirlar)} satır")
        komisyon = cfg.KOMISYON.get("pegasus", 8) / 100

        for satir in satirlar:
            try:
                metin = satir.inner_text().strip()
                if not metin:
                    continue
                if direkt_mi and ("bağlantı" in metin.lower() or "1 Bağlantı" in metin):
                    continue
                m = re.search(r'PC\d+', metin)
                if not m:
                    continue
                ucus_no = m.group()
                saatler = re.findall(r'\d{2}:\d{2}', metin)
                kalkis = saatler[0] if saatler else ""
                varis = saatler[1] if len(saatler) > 1 else ""
                sure_m = re.search(r'(\d+)\s*sa\s*(\d+)?\s*dk?', metin)
                sure = ""
                if sure_m:
                    sure = f"{sure_m.group(1)}sa"
                    if sure_m.group(2):
                        sure += f" {sure_m.group(2)}dk"

                fiyatlar = []
                for e in re.findall(r'([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*TRY', metin):
                    try:
                        d = float(e.replace(".", "").replace(",", "."))
                        if 100 < d < 500000 and d not in fiyatlar:
                            fiyatlar.append(d)
                    except Exception:
                        pass
                if not fiyatlar:
                    continue

                paketler = []
                for i, ad in enumerate(["Light", "Süper Eko", "Avantaj", "Comfort Flex"]):
                    if i < len(fiyatlar):
                        h = fiyatlar[i]
                        paketler.append({
                            "paket": ad,
                            "icerik": PAKET_ICERIKLERI.get(ad, ""),
                            "fiyat_haric": h,
                            "fiyat_dahil": round(h * (1 + komisyon), 2),
                        })
                if paketler:
                    sonuclar.append({
                        "havayolu": "Pegasus",
                        "ucus_no": ucus_no,
                        "nereden": nereden,
                        "nereye": nereye,
                        "kalkis": kalkis,
                        "varis": varis,
                        "sure": sure,
                        "paketler": paketler,
                        "en_ucuz_dahil": min(p["fiyat_dahil"] for p in paketler),
                    })
            except Exception as e:
                log.warning(f"Satır hatası: {e}")

        log.info(f"Pegasus: {len(sonuclar)} uçuş")
        return sonuclar

    except Exception as e:
        log.error(f"Sonuç okuma hatası: {e}")
        _ss(sayfa, "hata_sonuc")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 4. PAKET SEÇİMİ
# ─────────────────────────────────────────────────────────────────────────────

def pegasus_paket_sec(sayfa, ucus_no: str, paket_index: int) -> float:
    try:
        log.info(f"Paket seç: {ucus_no} index={paket_index}")
        satir = sayfa.query_selector(f"tr:has-text('{ucus_no}')")
        if not satir:
            log.error(f"Uçuş satırı yok: {ucus_no}")
            return 0.0

        radios = satir.query_selector_all("input[type='radio']")
        if radios and paket_index < len(radios):
            radios[paket_index].click()
        else:
            hucreler = satir.query_selector_all("td[class*='price'], td[class*='fare'], label")
            if paket_index < len(hucreler):
                hucreler[paket_index].click()

        _bekle(2, 3)
        sayfa.keyboard.press("End")
        _bekle(1, 2)
        toplam = _toplam_fiyat_oku(sayfa)
        log.info(f"Toplam: {toplam} TRY")

        sayfa.click("button:has-text('Devam'), a:has-text('Devam')")
        _bekle(3, 5)

        try:
            sayfa.wait_for_selector(
                "a:has-text('Mevcut Seçimlerle İlerle'), button:has-text('Mevcut Seçimlerle İlerle')",
                timeout=8000
            )
            sayfa.click("a:has-text('Mevcut Seçimlerle İlerle'), button:has-text('Mevcut Seçimlerle İlerle')")
            log.info("Paket yükseltme geçildi")
            _bekle(3, 5)
        except Exception:
            pass

        try:
            sayfa.wait_for_url("**/RezvPaxEntry**", timeout=20000)
        except Exception:
            sayfa.wait_for_load_state("networkidle", timeout=20000)

        return toplam

    except Exception as e:
        log.error(f"Paket hatası: {e}")
        _ss(sayfa, "hata_paket")
        return 0.0


def _toplam_fiyat_oku(sayfa) -> float:
    try:
        el = sayfa.query_selector(
            "[class*='total-price'], [class*='grand-total'], [id*='totalPrice'], strong:has-text('TRY')"
        )
        if el:
            m = re.search(r'([\d.,]+)\s*TRY', el.inner_text())
            if m:
                return float(m.group(1).replace(".", "").replace(",", "."))
    except Exception:
        pass
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 5. YOLCU BİLGİLERİ
# ─────────────────────────────────────────────────────────────────────────────

def pegasus_yolcu_doldur(sayfa, yolcular: list) -> bool:
    try:
        log.info(f"{len(yolcular)} yolcu dolduruluyor")
        sayfa.wait_for_load_state("networkidle", timeout=20000)
        _bekle(2, 3)

        yetiskinler = [y for y in yolcular if y.get("tip") not in ["cocuk", "bebek"]]
        cocuklar = [y for y in yolcular if y.get("tip") == "cocuk"]
        bebekler = [y for y in yolcular if y.get("tip") == "bebek"]

        _yetiskin_doldur(sayfa, yetiskinler)
        _cocuk_doldur(sayfa, cocuklar, len(yetiskinler))
        _bebek_doldur(sayfa, bebekler, len(yetiskinler) + len(cocuklar))
        _iletisim_doldur(sayfa)
        _onay_sec(sayfa)

        _bekle(1, 2)
        sayfa.click("button:has-text('Rezervasyonu Tamamla'), a:has-text('Rezervasyonu Tamamla')")
        _bekle(5, 8)
        _ek_hizmetler_gec(sayfa)
        return True

    except Exception as e:
        log.error(f"Yolcu doldurma hatası: {e}")
        _ss(sayfa, "hata_yolcu")
        return False


def _yetiskin_doldur(sayfa, yetiskinler: list):
    cinsiyet_sels = sayfa.query_selector_all("select[name*='gender'], select[id*='gender']")
    isim_sels = sayfa.query_selector_all("input[name*='firstName'], input[id*='firstName']")
    soyisim_sels = sayfa.query_selector_all("input[name*='lastName'], input[id*='lastName']")
    for i, y in enumerate(yetiskinler):
        try:
            if i < len(cinsiyet_sels):
                label = "Erkek" if y.get("cinsiyet", "E") == "E" else "Kadın"
                try:
                    cinsiyet_sels[i].select_option(label=label)
                except Exception:
                    cinsiyet_sels[i].select_option(value="E" if label == "Erkek" else "K")
                _bekle(0.3, 0.5)
            if i < len(isim_sels):
                isim_sels[i].fill(y.get("ad", "").upper())
            if i < len(soyisim_sels):
                soyisim_sels[i].fill(y.get("soyad", "").upper())
            _dogum_doldur(sayfa, i, y.get("dogum", ""))
            if y.get("tc_no"):
                tc_sels = sayfa.query_selector_all("input[name*='tckn'], input[id*='tckn'], input[placeholder*='TC']")
                if i < len(tc_sels):
                    tc_sels[i].fill(y["tc_no"])
            log.info(f"Yetişkin {i+1}: {y.get('ad')} {y.get('soyad')}")
        except Exception as e:
            log.warning(f"Yetişkin {i+1} hatası: {e}")


def _cocuk_doldur(sayfa, cocuklar: list, offset: int):
    if not cocuklar:
        return
    isim_sels = sayfa.query_selector_all("input[name*='firstName'], input[id*='firstName']")
    soyisim_sels = sayfa.query_selector_all("input[name*='lastName'], input[id*='lastName']")
    for i, c in enumerate(cocuklar):
        idx = offset + i
        try:
            if idx < len(isim_sels):
                isim_sels[idx].fill(c.get("ad", "").upper())
            if idx < len(soyisim_sels):
                soyisim_sels[idx].fill(c.get("soyad", "").upper())
            _dogum_doldur(sayfa, idx, c.get("dogum", ""))
        except Exception as e:
            log.warning(f"Çocuk {i+1} hatası: {e}")


def _bebek_doldur(sayfa, bebekler: list, offset: int):
    if not bebekler:
        return
    ebeveyn_sels = sayfa.query_selector_all(
        "select[name*='parent'], select[id*='parent'], select:near(:text('Ebeveyn'))"
    )
    isim_sels = sayfa.query_selector_all("input[name*='firstName'], input[id*='firstName']")
    soyisim_sels = sayfa.query_selector_all("input[name*='lastName'], input[id*='lastName']")
    for i, b in enumerate(bebekler):
        idx = offset + i
        try:
            if i < len(ebeveyn_sels):
                try:
                    ebeveyn_sels[i].select_option(index=1)
                except Exception:
                    pass
                _bekle(0.3, 0.5)
            if idx < len(isim_sels):
                isim_sels[idx].fill(b.get("ad", "").upper())
            if idx < len(soyisim_sels):
                soyisim_sels[idx].fill(b.get("soyad", "").upper())
            _dogum_doldur(sayfa, idx, b.get("dogum", ""))
        except Exception as e:
            log.warning(f"Bebek {i+1} hatası: {e}")


def _dogum_doldur(sayfa, index: int, dogum: str):
    try:
        if not dogum:
            return
        p = dogum.replace("/", ".").split(".")
        if len(p) != 3:
            return
        gun = p[0].lstrip("0") or "1"
        ay = p[1]
        yil = p[2]
        AYLAR = {"01":"Ocak","02":"Şubat","03":"Mart","04":"Nisan","05":"Mayıs",
                 "06":"Haziran","07":"Temmuz","08":"Ağustos","09":"Eylül",
                 "10":"Ekim","11":"Kasım","12":"Aralık"}
        gun_sels = sayfa.query_selector_all("select[name*='Day'], select[id*='Day']")
        ay_sels = sayfa.query_selector_all("select[name*='Month'], select[id*='Month']")
        yil_sels = sayfa.query_selector_all("select[name*='Year'], select[id*='Year']")
        if index < len(gun_sels):
            try:
                gun_sels[index].select_option(value=gun)
            except Exception:
                gun_sels[index].select_option(label=gun)
        if index < len(ay_sels):
            try:
                ay_sels[index].select_option(label=AYLAR.get(ay, ay))
            except Exception:
                ay_sels[index].select_option(value=str(int(ay)))
        if index < len(yil_sels):
            yil_sels[index].select_option(value=yil)
    except Exception as e:
        log.warning(f"Doğum hatası (idx={index}): {e}")


def _iletisim_doldur(sayfa):
    try:
        try:
            cb = sayfa.query_selector("input[type='checkbox']:near(:text('İlk Yolcu Bilgilerini Getir'))")
            if cb and not cb.is_checked():
                cb.click()
                _bekle(1, 2)
        except Exception:
            pass

        _bekle(1, 2)
        tel_sels = sayfa.query_selector_all("input[name*='phone'], input[id*='phone'], input[type='tel']")
        if len(tel_sels) >= 2:
            tel_sels[0].fill(ACENTE_TEL_ALAN)
            _bekle(0.3, 0.5)
            tel_sels[1].fill(ACENTE_TEL_NO)
        elif len(tel_sels) == 1:
            tel_sels[0].fill(ACENTE_TEL_ALAN + ACENTE_TEL_NO)
        if len(tel_sels) >= 4:
            tel_sels[2].fill(ACENTE_TEL_ALAN)
            _bekle(0.3, 0.5)
            tel_sels[3].fill(ACENTE_TEL_NO)

        email_sels = sayfa.query_selector_all("input[type='email'], input[name*='email'], input[id*='email']")
        if email_sels:
            email_sels[0].fill(ACENTE_EMAIL)

        log.info("İletişim dolduruldu ✅")
    except Exception as e:
        log.error(f"İletişim hatası: {e}")


def _onay_sec(sayfa):
    try:
        for cb in sayfa.query_selector_all("input[type='checkbox']"):
            try:
                etiket = cb.evaluate("el => el.closest('div,tr,p,label,td')?.innerText || ''")
                # Ücretli SMS (186,87 TRY), BolBol, İlk Yolcu, TC Vatandaşı kutularını atla
                if any(x in etiket for x in ["186", "SMS bedeli", "BolBol", "İlk Yolcu", "T.C. Vatandaşı"]):
                    continue
                if any(x in etiket.lower() for x in ["onaylıyorum", "kabul ediyorum", "sorumlu"]):
                    if not cb.is_checked():
                        cb.click()
                        log.info(f"Onay işaretlendi ✅: {etiket[:60]}")
            except Exception:
                continue
    except Exception as e:
        log.warning(f"Onay hatası: {e}")


def _ek_hizmetler_gec(sayfa):
    try:
        try:
            sayfa.wait_for_url("**/SellSsr**", timeout=15000)
        except Exception:
            try:
                sayfa.wait_for_selector(
                    "a:has-text('Ödemeye Devam Et'), button:has-text('Ödemeye Devam Et')",
                    timeout=10000
                )
            except Exception:
                log.info("Ek hizmetler sayfası yok")
                return
        _bekle(2, 3)
        sayfa.click("a:has-text('Ödemeye Devam Et'), button:has-text('Ödemeye Devam Et')")
        log.info("Ek hizmetler geçildi ✅")
        _bekle(3, 5)
    except Exception as e:
        log.warning(f"Ek hizmetler hatası: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. REZERVASYON BİLGİSİ
# ─────────────────────────────────────────────────────────────────────────────

def pegasus_rezervasyon_bilgisi_al(sayfa) -> dict:
    try:
        _bekle(3, 5)
        sayfa.wait_for_load_state("networkidle", timeout=20000)
        _ss(sayfa, "06_rezervasyon_sonuc")

        pnr = ""
        try:
            el = sayfa.query_selector("*:has-text('Rezervasyon (PNR) No')")
            if el:
                m = re.search(r'(?:PNR|No)[.\s:]*([A-Z0-9]{5,6})', el.inner_text())
                if m:
                    pnr = m.group(1)
        except Exception:
            pass

        if not pnr:
            try:
                el = sayfa.query_selector("[class*='pnr'], [id*='pnr']")
                if el:
                    m = re.search(r'\b([A-Z0-9]{5,6})\b', el.inner_text())
                    if m:
                        pnr = m.group(1)
            except Exception:
                pass

        log.info(f"PNR: {pnr or 'ALINAMADI'}")
        return {
            "pnr": pnr or "ALINAMADI",
            "mesaj": (
                f"✅ *Rezervasyon Oluşturuldu!*\n\n"
                f"PNR: `{pnr or 'ALINAMADI'}`\n\n"
                "Pegasus acente ekranından ödemeyi tamamlayın."
            ),
        }
    except Exception as e:
        log.error(f"PNR hatası: {e}")
        return {
            "pnr": "ALINAMADI",
            "mesaj": "⚠️ Rezervasyon tamamlandı ancak PNR alınamadı. Pegasus sistemini kontrol edin.",
        }
