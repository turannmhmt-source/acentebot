"""
pegasus_modul.py — Pegasus acente otomasyonu
Tüm selector'lar log'dan doğrulandı.
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
    import config as cfg
    sayfa = None
    konteks = None
    try:
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
        sayfa.goto(PEGASUS_URL, wait_until="domcontentloaded", timeout=30000)
        _bekle(2, 3)

        sayfa.wait_for_selector("input[name='USERNAME']", state="visible", timeout=20000)
        sayfa.fill("input[name='USERNAME']", cfg.PEGASUS_KULLANICI)
        _bekle(0.5, 1.0)
        sayfa.fill("input[name='PASSWORD']", cfg.PEGASUS_SIFRE)
        _bekle(0.5, 1.0)
        log.info(f"Kimlik dolduruldu: {cfg.PEGASUS_KULLANICI}")
        _ss(sayfa, "01_kimlik_doldu")

        sayfa.press("input[name='PASSWORD']", "Enter")
        log.info("Enter basıldı...")
        _bekle(3, 5)
        _ss(sayfa, "02_enter_sonrasi")

        try:
            sayfa.wait_for_selector("input[name='OTP_INPUT']", state="visible", timeout=10000)
            log.info("OTP ekranı açıldı ✅")
        except Exception:
            log.warning("OTP direkt açılmadı, bekleniyor...")
            _bekle(3, 5)
            sayfa.wait_for_selector("input[name='OTP_INPUT']", state="visible", timeout=15000)

        try:
            sayfa.get_by_text("SMS Gönder", exact=True).click(timeout=5000)
            log.info("SMS Gönder tıklandı ✅")
            _bekle(3, 4)
        except Exception:
            try:
                sayfa.locator("text=SMS Gönder").first.click(timeout=5000)
                log.info("SMS Gönder tıklandı ✅")
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


# ─────────────────────────────────────────────────────────────────────────────
# 2. OTP
# ─────────────────────────────────────────────────────────────────────────────

def pegasus_otp_gir(konteks, sayfa, otp_kodu: str):
    try:
        kod = _otp_cikart(otp_kodu)
        log.info(f"OTP: {kod}")

        sayfa.fill("input[name='OTP_INPUT']", kod)
        _bekle(0.5, 1.0)

        try:
            sayfa.get_by_text("Giriş yap", exact=True).click(timeout=5000)
            log.info("Giriş yap tıklandı ✅")
        except Exception:
            try:
                sayfa.locator("text=Giriş yap").first.click(timeout=5000)
                log.info("Giriş yap tıklandı ✅")
            except Exception:
                sayfa.press("input[name='OTP_INPUT']", "Enter")
                log.info("Giriş yap — Enter ✅")

        yeni_sayfa = None
        try:
            with konteks.expect_page(timeout=8000) as yeni_bilgi:
                pass
            yeni_sayfa = yeni_bilgi.value
            yeni_sayfa.wait_for_load_state("domcontentloaded", timeout=30000)
            log.info(f"Yeni pencere: {yeni_sayfa.url}")
        except Exception:
            log.info("Popup yok, mevcut sayfa...")
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
    metin = metin.strip()
    m = re.search(r"kodunuz\s+([A-Za-z0-9]+)", metin, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Za-z0-9]{4,8})\b", metin)
    if m:
        return m.group(1)
    return metin


# ─────────────────────────────────────────────────────────────────────────────
# 3. UÇUŞ SORGULAMA
# ─────────────────────────────────────────────────────────────────────────────

def pegasus_ucus_sorgula(sayfa, komut: dict) -> list:
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
        _bekle(3, 5)
        _ss(sayfa, "05_form_acildi")

        # Uçuş tipi
        if tip == "tek_yon":
            _tab_sec(sayfa, "Tek Yön")
        elif tip == "gidis_donus":
            _tab_sec(sayfa, "Gidiş - Dönüş")
        _bekle(1, 2)

        # Şehirler
        _sehir_sec(sayfa, nereden, "nereden")
        _bekle(1.5, 2.5)
        _sehir_sec(sayfa, nereye, "nereye")
        _bekle(1.5, 2.5)
        _ss(sayfa, "05b_sehir_sonrasi")

        # Tarih
        if tip == "tek_yon":
            _tarih_sec(sayfa, komut.get("tarih", ""))
        else:
            _tarih_sec(sayfa, komut.get("gidis_tarihi", ""))
        _bekle(1, 2)

        # Yolcu
        _yolcu_sec(sayfa, yetiskin, cocuk, bebek)
        _bekle(1, 2)

        # Submit öncesi hidden değerleri logla
        try:
            dp = sayfa.input_value("input[name='DEPPORT']")
            ar = sayfa.input_value("input[name='ARRPORT']")
            dt = sayfa.input_value("input[name='FLTDATE']")
            log.info(f"Submit öncesi: DEPPORT='{dp}' ARRPORT='{ar}' FLTDATE='{dt}'")
        except Exception:
            pass

        _ss(sayfa, "05c_form_dolu")
        _ara_tikla(sayfa)
        _bekle(3, 5)

        # Popup geç
        for sel in ["button:has-text('Devam')", "a:has-text('Devam')",
                    "button:has-text('Tamam')", "button:has-text('Kapat')"]:
            try:
                sayfa.wait_for_selector(sel, timeout=4000)
                sayfa.click(sel)
                log.info(f"Popup geçildi: {sel}")
                _bekle(2, 3)
                break
            except Exception:
                pass

        try:
            sayfa.wait_for_url("**/MemberRezvResults**", timeout=45000)
        except Exception:
            try:
                sayfa.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass

        _bekle(3, 5)
        _ss(sayfa, "05d_sonuc")
        return _sonuclari_oku(sayfa, nereden, nereye, direkt_mi, cfg)

    except Exception as e:
        log.error(f"Uçuş sorgulama hatası: {e}")
        _ss(sayfa, "hata_sorgula")
        return []


def _tab_sec(sayfa, metin: str):
    for sel in [f"a:has-text('{metin}')", f"li:has-text('{metin}')",
                f"span:has-text('{metin}')", f"button:has-text('{metin}')"]:
        try:
            el = sayfa.query_selector(sel)
            if el and el.is_visible():
                el.click()
                log.info(f"Tab seçildi: {metin}")
                return
        except Exception:
            continue


def _sehir_sec(sayfa, iata: str, tip: str):
    """
    Gizli field'lar (log'dan doğrulandı): DEPPORT / ARRPORT
    Görünür field'lar: LAB_DEPPORT / LAB_ARRPORT
    """
    arama = SEHIR_ARAMA.get(iata, iata)
    lab_sel = "input[name='LAB_DEPPORT']" if tip == "nereden" else "input[name='LAB_ARRPORT']"
    hidden_name = "DEPPORT" if tip == "nereden" else "ARRPORT"
    log.info(f"Şehir seçimi: {iata}→'{arama}' ({tip})")

    # 1. Görünür input'u temizle ve şehir adını yaz
    try:
        sayfa.fill(lab_sel, "")
        _bekle(0.2, 0.3)
        sayfa.type(lab_sel, arama, delay=100)
        log.info(f"Şehir yazıldı: '{arama}'")
        _bekle(2.0, 3.0)
    except Exception as e:
        log.warning(f"Şehir yazma hatası ({tip}): {e}")

    # 2. Dropdown'dan ilk seçeneği tıkla
    dropdown_sels = [
        "[class*='suggestion'] li",
        "[class*='Suggestion'] li",
        "[class*='SelectBox__list'] li",
        "[class*='selectBox__list'] li",
        "[class*='autocomplete'] li",
        "[class*='dropdown-item']",
        "[role='option']",
        "ul[style*='display: block'] li",
        "ul[style*='display:block'] li",
    ]
    secildi = False
    for dsel in dropdown_sels:
        try:
            ilk = sayfa.locator(dsel).first
            if ilk.is_visible(timeout=800):
                ilk.click(timeout=2000)
                _bekle(0.5, 1)
                log.info(f"Dropdown tıklandı ({dsel}): {tip}")
                secildi = True
                break
        except Exception:
            continue

    if not secildi:
        # ArrowDown+Enter fallback
        try:
            sayfa.keyboard.press("ArrowDown")
            _bekle(0.4, 0.6)
            sayfa.keyboard.press("Enter")
            _bekle(0.5, 0.8)
            log.info(f"ArrowDown+Enter ({tip})")
        except Exception as e:
            log.warning(f"Klavye hatası ({tip}): {e}")

    # 3. Hidden DEPPORT/ARRPORT değerini kontrol et, boşsa JS ile set et
    try:
        mevcut = sayfa.input_value(f"input[name='{hidden_name}']")
        log.info(f"{hidden_name} değeri: '{mevcut}'")
        if not mevcut:
            sayfa.evaluate(f"() => {{ const h = document.querySelector(\"input[name='{hidden_name}']\"); if(h) h.value = '{iata}'; }}")
            log.info(f"{hidden_name}='{iata}' JS ile set edildi")
    except Exception as ex:
        log.warning(f"Hidden field kontrol hatası ({tip}): {ex}")


def _tarih_sec(sayfa, tarih: str):
    try:
        if not tarih:
            return
        p = tarih.split("-")
        if len(p) != 3:
            return
        tarih_str = f"{p[2]}/{p[1]}/{p[0]}"  # DD/MM/YYYY
        sayfa.fill("input[name='FLTDATE']", tarih_str)
        log.info(f"Tarih set edildi: {tarih_str}")
    except Exception as e:
        log.warning(f"Tarih hatası: {e}")


def _yolcu_sec(sayfa, yetiskin: int, cocuk: int, bebek: int):
    try:
        el = sayfa.query_selector("select[name*='ADULT']")
        if el:
            el.select_option(label=f"{yetiskin} Kişi")
            log.info(f"Yetişkin: {yetiskin}")
    except Exception as e:
        log.warning(f"Yetişkin seçim hatası: {e}")
    _bekle(0.3, 0.5)
    try:
        el = sayfa.query_selector("select[name*='CHILD']")
        if el:
            el.select_option(label=f"{cocuk} Çocuk")
            log.info(f"Çocuk: {cocuk}")
    except Exception as e:
        log.warning(f"Çocuk seçim hatası: {e}")
    _bekle(0.3, 0.5)
    try:
        el = sayfa.query_selector("select[name*='INFANT']")
        if el:
            el.select_option(label=f"{bebek} Bebek")
            log.info(f"Bebek: {bebek}")
    except Exception as e:
        log.warning(f"Bebek seçim hatası: {e}")
    log.info(f"Yolcu: {yetiskin}Y {cocuk}Ç {bebek}B")


def _ara_tikla(sayfa):
    """
    LAB_DEPPORT'un formunu bul, input[type=submit] tıkla.
    Sekme butonlarını (Tek Yön / Gidiş-Dönüş) atla.
    """
    TAB_TEXTS = {"Gidiş - Dönüş", "Tek Yön", "Çoklu Uçuş", "Gidiş", "Dönüş"}
    try:
        ok = sayfa.evaluate("""
            () => {
                const inp = document.querySelector("input[name='LAB_DEPPORT']");
                if (!inp) return null;
                const frm = inp.closest('form');
                if (!frm) return null;
                // input[type=submit] — en güvenilir
                for (const el of frm.querySelectorAll('input[type=submit]')) {
                    if (el.offsetParent !== null) {
                        el.click();
                        return 'input[type=submit]:' + el.value;
                    }
                }
                // button veya a ile value/text = 'Ara'
                for (const el of frm.querySelectorAll('button, a')) {
                    const v = (el.innerText || el.value || '').trim();
                    if (v === 'Ara' && el.offsetParent !== null) {
                        el.click();
                        return 'btn:' + v;
                    }
                }
                frm.submit();
                return 'form.submit';
            }
        """)
        log.info(f"Ara: {ok}")
    except Exception as e:
        log.warning(f"Ara hatası: {e}")


def _sonuclari_oku(sayfa, nereden, nereye, direkt_mi, cfg) -> list:
    try:
        sonuclar = []
        sayfa.wait_for_load_state("networkidle", timeout=20000)

        for link in sayfa.query_selector_all(
            "a:has-text('Bütün Fiyatları Göster'), span:has-text('Bütün Fiyatları Göster')"
        ):
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
        log.info(f"{len(satirlar)} satır bulundu")
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

        for sel in ["button:has-text('Devam')", "a:has-text('Devam')"]:
            try:
                sayfa.click(sel, timeout=5000)
                break
            except Exception:
                pass
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
        for sel in ["button:has-text('Rezervasyonu Tamamla')", "a:has-text('Rezervasyonu Tamamla')"]:
            try:
                sayfa.click(sel, timeout=5000)
                break
            except Exception:
                pass
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
                tc_sels = sayfa.query_selector_all(
                    "input[name*='tckn'], input[id*='tckn'], input[placeholder*='TC']"
                )
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
        "select[name*='parent'], select[id*='parent']"
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
        AYLAR = {
            "01": "Ocak", "02": "Şubat", "03": "Mart", "04": "Nisan",
            "05": "Mayıs", "06": "Haziran", "07": "Temmuz", "08": "Ağustos",
            "09": "Eylül", "10": "Ekim", "11": "Kasım", "12": "Aralık",
        }
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
            cb = sayfa.query_selector(
                "input[type='checkbox']:near(:text('İlk Yolcu Bilgilerini Getir'))"
            )
            if cb and not cb.is_checked():
                cb.click()
                _bekle(1, 2)
        except Exception:
            pass

        _bekle(1, 2)
        tel_sels = sayfa.query_selector_all(
            "input[name*='phone'], input[id*='phone'], input[type='tel']"
        )
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

        email_sels = sayfa.query_selector_all(
            "input[type='email'], input[name*='email'], input[id*='email']"
        )
        if email_sels:
            email_sels[0].fill(ACENTE_EMAIL)

        log.info("İletişim dolduruldu ✅")
    except Exception as e:
        log.error(f"İletişim hatası: {e}")


def _onay_sec(sayfa):
    """Onay kutularını işaretle — ücretli SMS (186 TRY) kutusuna dokunma."""
    try:
        for cb in sayfa.query_selector_all("input[type='checkbox']"):
            try:
                etiket = cb.evaluate(
                    "el => el.closest('div,tr,p,label,td')?.innerText || ''"
                )
                # Ücretli SMS ve diğer atlanacaklar
                if any(x in etiket for x in [
                    "186", "SMS bedeli", "BolBol", "İlk Yolcu", "T.C. Vatandaşı"
                ]):
                    continue
                if any(x in etiket.lower() for x in [
                    "onaylıyorum", "kabul ediyorum", "sorumlu"
                ]):
                    if not cb.is_checked():
                        cb.click()
                        log.info(f"Onay işaretlendi: {etiket[:60]}")
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
                    timeout=10000,
                )
            except Exception:
                log.info("Ek hizmetler sayfası yok")
                return
        _bekle(2, 3)
        for sel in ["a:has-text('Ödemeye Devam Et')", "button:has-text('Ödemeye Devam Et')"]:
            try:
                sayfa.click(sel, timeout=5000)
                log.info("Ek hizmetler geçildi ✅")
                _bekle(3, 5)
                return
            except Exception:
                pass
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
        for sel in ["*:has-text('Rezervasyon (PNR) No')", "[class*='pnr']", "[id*='pnr']"]:
            try:
                el = sayfa.query_selector(sel)
                if el:
                    m = re.search(r'(?:PNR|No)[.\s:]*([A-Z0-9]{5,6})', el.inner_text())
                    if not m:
                        m = re.search(r'\b([A-Z0-9]{5,6})\b', el.inner_text())
                    if m:
                        pnr = m.group(1)
                        break
            except Exception:
                continue

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
