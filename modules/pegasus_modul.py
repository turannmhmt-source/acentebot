"""
pegasus_modul.py
Tüm selector'lar log'dan doğrulandı.
Hidden IATA field'lar: DEPPORT, ARRPORT
"""

import re
import time
import random
import os
from modules.logger import get_logger

log = get_logger("pegasus")

PEGASUS_URL    = "https://acente.flypgs.com/"
PEGASUS_FORM   = "https://acente.flypgs.com/MemberRezvEntry.jsp"
GECICI_DIR     = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gecici")

SEHIR_ARAMA = {
    "IST": "İstanbul Tümü", "SAW": "Sabiha",      "ESB": "Ankara",
    "ADB": "İzmir",         "AYT": "Antalya",      "BJV": "Bodrum",
    "DLM": "Dalaman",       "TZX": "Trabzon",      "GZT": "Gaziantep",
    "ADA": "Adana",         "ASR": "Kayseri",       "SZF": "Samsun",
    "DIY": "Diyarbakır",    "VAN": "Van",           "MLX": "Malatya",
    "ERZ": "Erzurum",       "HTY": "Hatay",         "KYA": "Konya",
    "NAV": "Nevşehir",      "SJJ": "Saraybosna",
}

PAKET_ICERIKLERI = {
    "Light":       "Koltuk altı çanta (40x30x15 cm, 3 kg)",
    "Süper Eko":   "Koltuk altı çanta + kabin bagaj + 20 kg bagaj",
    "Avantaj":     "Koltuk altı çanta + kabin + 20 kg + koltuk seçimi",
    "Comfort Flex":"Koltuk altı + kabin + 20 kg + esnek değişiklik + koltuk",
}

ACENTE_TEL_ALAN = "555"
ACENTE_TEL_NO   = "0094805"
ACENTE_EMAIL    = "masaraturizm@gmail.com"


def _w(a=0.8, b=2.0):
    time.sleep(random.uniform(a, b))


def _ss(sayfa, ad):
    os.makedirs(GECICI_DIR, exist_ok=True)
    from datetime import datetime
    p = os.path.join(GECICI_DIR, f"{ad}_{datetime.now().strftime('%H%M%S')}.png")
    try:
        sayfa.screenshot(path=p, full_page=True)
        log.info(f"SS: {p}")
    except Exception:
        pass
    return p


# ──────────────────────────────────────────────
# 1. GİRİŞ
# ──────────────────────────────────────────────

def pegasus_giris_baslat(tarayici):
    import config as cfg
    sayfa = konteks = None
    try:
        konteks = tarayici.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
        )
        sayfa = konteks.new_page()
        sayfa.goto(PEGASUS_URL, wait_until="domcontentloaded", timeout=30000)
        _w(2, 3)

        sayfa.wait_for_selector("input[name='USERNAME']", state="visible", timeout=20000)
        sayfa.fill("input[name='USERNAME']", cfg.PEGASUS_KULLANICI)
        _w(0.4, 0.7)
        sayfa.fill("input[name='PASSWORD']", cfg.PEGASUS_SIFRE)
        _w(0.4, 0.7)
        log.info("Kimlik dolduruldu")

        # Enter ile submit — buton aramak gerekmez
        sayfa.press("input[name='PASSWORD']", "Enter")
        log.info("Enter basıldı")
        _w(3, 5)
        _ss(sayfa, "01_login")

        # OTP ekranını bekle
        sayfa.wait_for_selector("input[name='OTP_INPUT']", state="visible", timeout=15000)
        log.info("OTP ekranı açıldı ✅")

        # SMS Gönder
        try:
            sayfa.get_by_text("SMS Gönder", exact=True).click(timeout=5000)
            log.info("SMS Gönder tıklandı ✅")
        except Exception:
            sayfa.locator("text=SMS Gönder").first.click(timeout=5000)
            log.info("SMS Gönder tıklandı ✅")
        _w(2, 3)
        _ss(sayfa, "02_sms")
        log.info("SMS gönderildi — OTP bekleniyor")
        return konteks, sayfa

    except Exception as e:
        log.error(f"Giriş hatası: {e}")
        if sayfa:
            _ss(sayfa, "hata_giris")
        return None, None


# ──────────────────────────────────────────────
# 2. OTP
# ──────────────────────────────────────────────

def pegasus_otp_gir(konteks, sayfa, otp_metin: str):
    try:
        kod = _otp_cikart(otp_metin)
        log.info(f"OTP kodu: {kod}")

        sayfa.fill("input[name='OTP_INPUT']", kod)
        _w(0.4, 0.7)

        try:
            sayfa.get_by_text("Giriş yap", exact=True).click(timeout=5000)
        except Exception:
            sayfa.press("input[name='OTP_INPUT']", "Enter")
        log.info("Giriş yap tıklandı ✅")

        # Popup pencere dene, yoksa mevcut sayfada devam
        yeni = None
        try:
            with konteks.expect_page(timeout=8000) as bilgi:
                pass
            yeni = bilgi.value
            yeni.wait_for_load_state("domcontentloaded", timeout=30000)
            log.info(f"Yeni pencere: {yeni.url}")
        except Exception:
            sayfa.wait_for_load_state("domcontentloaded", timeout=30000)
            _w(3, 5)
            yeni = sayfa
            log.info(f"Mevcut sayfa: {sayfa.url}")

        _w(1, 2)
        _ss(yeni, "03_anasayfa")
        if "acente.flypgs.com" in yeni.url:
            log.info("Ana ekran ✅")
            return yeni
        log.error(f"Beklenmeyen URL: {yeni.url}")
        return None

    except Exception as e:
        log.error(f"OTP hatası: {e}")
        _ss(sayfa, "hata_otp")
        return None


def _otp_cikart(metin: str) -> str:
    m = re.search(r"kodunuz\s+([A-Za-z0-9]+)", metin, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Za-z0-9]{4,8})\b", metin.strip())
    return m.group(1) if m else metin.strip()


# ──────────────────────────────────────────────
# 3. UÇUŞ SORGULAMA
# ──────────────────────────────────────────────

def pegasus_ucus_sorgula(sayfa, komut: dict) -> list:
    import config as cfg
    try:
        tip      = komut.get("tip", "tek_yon")
        nereden  = komut.get("nereden", "IST")
        nereye   = komut.get("nereye", "")
        yetiskin = komut.get("yetiskin", 1)
        cocuk    = komut.get("cocuk", 0)
        bebek    = komut.get("bebek", 0)
        direkt   = komut.get("direkt_mi", True)
        tarih    = komut.get("tarih") or komut.get("gidis_tarihi", "")

        log.info(f"Sorgu: {nereden}→{nereye} {tarih} {tip}")
        sayfa.goto(PEGASUS_FORM, wait_until="domcontentloaded", timeout=30000)
        _w(3, 5)
        _ss(sayfa, "04_form")

        # Uçuş tipi tab
        _tab_sec(sayfa, "Tek Yön" if tip == "tek_yon" else "Gidiş - Dönüş")
        _w(0.8, 1.5)

        # Şehir seç
        _sehir_sec(sayfa, nereden, "nereden")
        _w(1.5, 2.5)
        _sehir_sec(sayfa, nereye, "nereye")
        _w(1.5, 2.5)
        _ss(sayfa, "05_sehir")

        # Tarih
        _tarih_sec(sayfa, tarih)
        _w(0.8, 1.5)

        # Yolcu
        _yolcu_sec(sayfa, yetiskin, cocuk, bebek)
        _w(0.8, 1.5)

        # Submit öncesi logla
        try:
            dp = sayfa.input_value("input[name='DEPPORT']")
            ar = sayfa.input_value("input[name='ARRPORT']")
            dt = sayfa.input_value("input[name='FLTDATE']")
            log.info(f"DEPPORT='{dp}' ARRPORT='{ar}' FLTDATE='{dt}'")
        except Exception:
            pass
        _ss(sayfa, "06_form_dolu")

        # Ara
        _ara_tikla(sayfa)
        _w(3, 5)

        # Popup kapat
        for sel in ["button:has-text('Devam')", "a:has-text('Devam')",
                    "button:has-text('Tamam')", "button:has-text('Kapat')"]:
            try:
                sayfa.wait_for_selector(sel, timeout=3000)
                sayfa.click(sel)
                _w(1, 2)
                break
            except Exception:
                pass

        # Sonuç sayfasını bekle — networkidle yeterli
        _w(3, 5)
        try:
            sayfa.wait_for_load_state("networkidle", timeout=60000)
        except Exception:
            pass
        _w(2, 3)

        log.info(f"Sonuç URL: {sayfa.url}")
        _ss(sayfa, "07_sonuc")

        if "Error.jsp" in sayfa.url or "error" in sayfa.url.lower():
            try:
                log.error(f"Hata sayfası içeriği: {sayfa.inner_text('body')[:400]}")
            except Exception:
                pass
            return []

        return _sonuclari_oku(sayfa, nereden, nereye, direkt, cfg)

    except Exception as e:
        log.error(f"Sorgulama hatası: {e}")
        _ss(sayfa, "hata_sorgula")
        return []


def _tab_sec(sayfa, metin: str):
    for sel in [f"a:has-text('{metin}')", f"button:has-text('{metin}')",
                f"li:has-text('{metin}')", f"span:has-text('{metin}')"]:
        try:
            el = sayfa.query_selector(sel)
            if el and el.is_visible():
                el.click()
                log.info(f"Tab: {metin}")
                return
        except Exception:
            pass


def _sehir_sec(sayfa, iata: str, tip: str):
    arama       = SEHIR_ARAMA.get(iata, iata)
    lab         = "input[name='LAB_DEPPORT']" if tip == "nereden" else "input[name='LAB_ARRPORT']"
    hidden_name = "DEPPORT" if tip == "nereden" else "ARRPORT"
    log.info(f"Şehir: {iata}→'{arama}' ({tip})")

    # 1. Yaz
    try:
        sayfa.fill(lab, "")
        _w(0.1, 0.2)
        sayfa.type(lab, arama, delay=80)
        log.info(f"Yazıldı: '{arama}'")
        _w(2.0, 3.0)
    except Exception as e:
        log.warning(f"Yazma hatası ({tip}): {e}")

    # 2. Dropdown'dan ilk seçenek
    secildi = False
    for dsel in [
        "[class*='suggestion'] li",
        "[class*='Suggestion'] li",
        "[class*='autocomplete'] li",
        "[class*='SelectBox__list'] li",
        "[class*='selectBox__list'] li",
        "[role='option']",
        "[role='listbox'] li",
        "ul[style*='block'] li",
    ]:
        try:
            el = sayfa.locator(dsel).first
            if el.is_visible(timeout=800):
                el.click(timeout=2000)
                _w(0.5, 1.0)
                log.info(f"Dropdown tıklandı ({dsel})")
                secildi = True
                break
        except Exception:
            continue

    if not secildi:
        try:
            sayfa.keyboard.press("ArrowDown")
            _w(0.4, 0.6)
            sayfa.keyboard.press("Enter")
            _w(0.5, 0.8)
            log.info(f"ArrowDown+Enter ({tip})")
        except Exception as e:
            log.warning(f"Klavye hatası ({tip}): {e}")

    # 3. Hidden DEPPORT/ARRPORT — her koşulda IATA kodunu yaz
    try:
        mevcut = sayfa.input_value(f"input[name='{hidden_name}']")
        if not mevcut:
            sayfa.evaluate(
                f"() => {{ var h = document.querySelector(\"input[name='{hidden_name}']\"); if(h) h.value='{iata}'; }}"
            )
            log.info(f"{hidden_name}='{iata}' JS ile set edildi ✅")
        else:
            log.info(f"{hidden_name}='{mevcut}' (zaten dolu)")
    except Exception as ex:
        log.warning(f"Hidden set hatası ({tip}): {ex}")


def _tarih_sec(sayfa, tarih: str):
    try:
        if not tarih:
            return
        p = tarih.split("-")
        if len(p) != 3:
            return
        tarih_str = f"{p[2]}/{p[1]}/{p[0]}"   # DD/MM/YYYY
        sayfa.fill("input[name='FLTDATE']", tarih_str)
        log.info(f"Tarih: {tarih_str}")
    except Exception as e:
        log.warning(f"Tarih hatası: {e}")


def _yolcu_sec(sayfa, yetiskin: int, cocuk: int, bebek: int):
    for (sel, label) in [
        ("select[name*='ADULT']",  f"{yetiskin} Kişi"),
        ("select[name*='CHILD']",  f"{cocuk} Çocuk"),
        ("select[name*='INFANT']", f"{bebek} Bebek"),
    ]:
        try:
            el = sayfa.query_selector(sel)
            if el:
                el.select_option(label=label)
                log.info(f"Yolcu: {label}")
        except Exception as e:
            log.warning(f"Yolcu seçim hatası ({sel}): {e}")
        _w(0.2, 0.4)


def _ara_tikla(sayfa):
    try:
        sonuc = sayfa.evaluate("""
            () => {
                var inp = document.querySelector("input[name='LAB_DEPPORT']");
                if (!inp) return 'LAB_DEPPORT yok';
                var frm = inp.closest('form');
                if (!frm) return 'form yok';
                var sub = frm.querySelector('input[type=submit]');
                if (sub && sub.offsetParent) { sub.click(); return 'input[submit]:' + sub.value; }
                var els = frm.querySelectorAll('button,a');
                for (var i=0; i<els.length; i++) {
                    var v = (els[i].innerText||'').trim();
                    if (v === 'Ara' && els[i].offsetParent) { els[i].click(); return 'btn:' + v; }
                }
                frm.submit();
                return 'form.submit';
            }
        """)
        log.info(f"Ara: {sonuc}")
    except Exception as e:
        log.warning(f"Ara hatası: {e}")


def _sonuclari_oku(sayfa, nereden, nereye, direkt, cfg) -> list:
    try:
        sayfa.wait_for_load_state("networkidle", timeout=20000)
        for lnk in sayfa.query_selector_all("a:has-text('Bütün Fiyatları Göster')"):
            try:
                lnk.click()
                _w(0.5, 1)
            except Exception:
                pass
        _w(2, 3)
        _ss(sayfa, "08_liste")

        komisyon = cfg.KOMISYON.get("pegasus", 8) / 100
        sonuclar = []
        for satir in sayfa.query_selector_all(
            "tr:has(td):has([class*='flt']), [class*='flight-row'], table.table tbody tr"
        ):
            try:
                metin = satir.inner_text().strip()
                if not metin:
                    continue
                if direkt and "bağlantı" in metin.lower():
                    continue
                m = re.search(r'PC\d+', metin)
                if not m:
                    continue
                ucus_no = m.group()
                saatler = re.findall(r'\d{2}:\d{2}', metin)
                kalkis  = saatler[0] if saatler else ""
                varis   = saatler[1] if len(saatler) > 1 else ""
                sure_m  = re.search(r'(\d+)\s*sa\s*(\d+)?\s*dk?', metin)
                sure    = ""
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
                        "havayolu": "Pegasus", "ucus_no": ucus_no,
                        "nereden": nereden, "nereye": nereye,
                        "kalkis": kalkis, "varis": varis, "sure": sure,
                        "paketler": paketler,
                        "en_ucuz_dahil": min(p["fiyat_dahil"] for p in paketler),
                    })
            except Exception as e:
                log.warning(f"Satır hatası: {e}")

        log.info(f"Pegasus: {len(sonuclar)} uçuş bulundu")
        return sonuclar
    except Exception as e:
        log.error(f"Sonuç okuma hatası: {e}")
        _ss(sayfa, "hata_sonuc")
        return []


# ──────────────────────────────────────────────
# 4. PAKET SEÇİMİ
# ──────────────────────────────────────────────

def pegasus_paket_sec(sayfa, ucus_no: str, paket_index: int) -> float:
    try:
        log.info(f"Paket: {ucus_no} idx={paket_index}")
        satir = sayfa.query_selector(f"tr:has-text('{ucus_no}')")
        if not satir:
            log.error(f"Uçuş bulunamadı: {ucus_no}")
            return 0.0

        radios = satir.query_selector_all("input[type='radio']")
        if radios and paket_index < len(radios):
            radios[paket_index].click()
        else:
            hucreler = satir.query_selector_all("td[class*='price'], td[class*='fare'], label")
            if paket_index < len(hucreler):
                hucreler[paket_index].click()

        _w(2, 3)
        toplam = _toplam_fiyat_oku(sayfa)
        log.info(f"Toplam: {toplam} TRY")

        for sel in ["button:has-text('Devam')", "a:has-text('Devam')"]:
            try:
                sayfa.click(sel, timeout=5000)
                break
            except Exception:
                pass
        _w(3, 5)

        try:
            sayfa.wait_for_selector(
                "a:has-text('Mevcut Seçimlerle İlerle'), button:has-text('Mevcut Seçimlerle İlerle')",
                timeout=8000,
            )
            sayfa.click("a:has-text('Mevcut Seçimlerle İlerle'), button:has-text('Mevcut Seçimlerle İlerle')")
            log.info("Yükseltme geçildi")
            _w(3, 5)
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
            m = re.search(r'([\d.,]+)', el.inner_text())
            if m:
                return float(m.group(1).replace(".", "").replace(",", "."))
    except Exception:
        pass
    return 0.0


# ──────────────────────────────────────────────
# 5. YOLCU
# ──────────────────────────────────────────────

def pegasus_yolcu_doldur(sayfa, yolcular: list) -> bool:
    try:
        sayfa.wait_for_load_state("networkidle", timeout=20000)
        _w(2, 3)

        yet  = [y for y in yolcular if y.get("tip") not in ["cocuk", "bebek"]]
        coc  = [y for y in yolcular if y.get("tip") == "cocuk"]
        beb  = [y for y in yolcular if y.get("tip") == "bebek"]

        _yetiskin_doldur(sayfa, yet)
        _cocuk_doldur(sayfa, coc, len(yet))
        _bebek_doldur(sayfa, beb, len(yet) + len(coc))
        _iletisim_doldur(sayfa)
        _onay_sec(sayfa)

        _w(1, 2)
        for sel in ["button:has-text('Rezervasyonu Tamamla')", "a:has-text('Rezervasyonu Tamamla')"]:
            try:
                sayfa.click(sel, timeout=5000)
                break
            except Exception:
                pass
        _w(5, 8)
        _ek_hizmetler_gec(sayfa)
        return True
    except Exception as e:
        log.error(f"Yolcu hatası: {e}")
        _ss(sayfa, "hata_yolcu")
        return False


def _yetiskin_doldur(sayfa, liste):
    cin  = sayfa.query_selector_all("select[name*='gender'], select[id*='gender']")
    isim = sayfa.query_selector_all("input[name*='firstName'], input[id*='firstName']")
    soy  = sayfa.query_selector_all("input[name*='lastName'],  input[id*='lastName']")
    for i, y in enumerate(liste):
        try:
            if i < len(cin):
                try:
                    cin[i].select_option(label="Erkek" if y.get("cinsiyet","E")=="E" else "Kadın")
                except Exception:
                    cin[i].select_option(value="E" if y.get("cinsiyet","E")=="E" else "K")
            if i < len(isim): isim[i].fill(y.get("ad","").upper())
            if i < len(soy):  soy[i].fill(y.get("soyad","").upper())
            _dogum_doldur(sayfa, i, y.get("dogum",""))
            if y.get("tc_no"):
                tc_els = sayfa.query_selector_all("input[name*='tckn'], input[id*='tckn']")
                if i < len(tc_els): tc_els[i].fill(y["tc_no"])
            log.info(f"Yetişkin {i+1}: {y.get('ad')} {y.get('soyad')}")
        except Exception as e:
            log.warning(f"Yetişkin {i+1} hatası: {e}")


def _cocuk_doldur(sayfa, liste, offset):
    isim = sayfa.query_selector_all("input[name*='firstName'], input[id*='firstName']")
    soy  = sayfa.query_selector_all("input[name*='lastName'],  input[id*='lastName']")
    for i, c in enumerate(liste):
        idx = offset + i
        try:
            if idx < len(isim): isim[idx].fill(c.get("ad","").upper())
            if idx < len(soy):  soy[idx].fill(c.get("soyad","").upper())
            _dogum_doldur(sayfa, idx, c.get("dogum",""))
        except Exception as e:
            log.warning(f"Çocuk {i+1} hatası: {e}")


def _bebek_doldur(sayfa, liste, offset):
    ebe  = sayfa.query_selector_all("select[name*='parent'], select[id*='parent']")
    isim = sayfa.query_selector_all("input[name*='firstName'], input[id*='firstName']")
    soy  = sayfa.query_selector_all("input[name*='lastName'],  input[id*='lastName']")
    for i, b in enumerate(liste):
        idx = offset + i
        try:
            if i < len(ebe):
                try: ebe[i].select_option(index=1)
                except Exception: pass
            if idx < len(isim): isim[idx].fill(b.get("ad","").upper())
            if idx < len(soy):  soy[idx].fill(b.get("soyad","").upper())
            _dogum_doldur(sayfa, idx, b.get("dogum",""))
        except Exception as e:
            log.warning(f"Bebek {i+1} hatası: {e}")


def _dogum_doldur(sayfa, idx, dogum):
    try:
        if not dogum: return
        p = dogum.replace("/",".").split(".")
        if len(p) != 3: return
        gun, ay, yil = p[0].lstrip("0") or "1", p[1], p[2]
        AYLAR = {"01":"Ocak","02":"Şubat","03":"Mart","04":"Nisan","05":"Mayıs",
                 "06":"Haziran","07":"Temmuz","08":"Ağustos","09":"Eylül",
                 "10":"Ekim","11":"Kasım","12":"Aralık"}
        g_els = sayfa.query_selector_all("select[name*='Day'],   select[id*='Day']")
        a_els = sayfa.query_selector_all("select[name*='Month'], select[id*='Month']")
        y_els = sayfa.query_selector_all("select[name*='Year'],  select[id*='Year']")
        if idx < len(g_els):
            try: g_els[idx].select_option(value=gun)
            except: g_els[idx].select_option(label=gun)
        if idx < len(a_els):
            try: a_els[idx].select_option(label=AYLAR.get(ay,ay))
            except: a_els[idx].select_option(value=str(int(ay)))
        if idx < len(y_els):
            y_els[idx].select_option(value=yil)
    except Exception as e:
        log.warning(f"Doğum hatası idx={idx}: {e}")


def _iletisim_doldur(sayfa):
    try:
        _w(1, 2)
        tel = sayfa.query_selector_all("input[name*='phone'], input[id*='phone'], input[type='tel']")
        if len(tel) >= 2:
            tel[0].fill(ACENTE_TEL_ALAN)
            _w(0.2, 0.4)
            tel[1].fill(ACENTE_TEL_NO)
        elif tel:
            tel[0].fill(ACENTE_TEL_ALAN + ACENTE_TEL_NO)
        if len(tel) >= 4:
            tel[2].fill(ACENTE_TEL_ALAN)
            _w(0.2, 0.4)
            tel[3].fill(ACENTE_TEL_NO)
        mail = sayfa.query_selector_all("input[type='email'], input[name*='email'], input[id*='email']")
        if mail: mail[0].fill(ACENTE_EMAIL)
        log.info("İletişim dolduruldu ✅")
    except Exception as e:
        log.error(f"İletişim hatası: {e}")


def _onay_sec(sayfa):
    # ÜCRETLİ SMS (186 TRY) KUTUSUNA KESINLIKLE DOKUNMA
    try:
        for cb in sayfa.query_selector_all("input[type='checkbox']"):
            try:
                etiket = cb.evaluate("el => el.closest('div,tr,p,label,td')?.innerText || ''")
                if any(x in etiket for x in ["186", "SMS bedeli", "BolBol", "İlk Yolcu", "T.C. Vatandaşı"]):
                    continue
                if any(x in etiket.lower() for x in ["onaylıyorum", "kabul ediyorum", "sorumlu"]):
                    if not cb.is_checked():
                        cb.click()
                        log.info(f"Onay: {etiket[:50]}")
            except Exception:
                pass
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
                log.info("Ek hizmetler yok")
                return
        _w(2, 3)
        for sel in ["a:has-text('Ödemeye Devam Et')", "button:has-text('Ödemeye Devam Et')"]:
            try:
                sayfa.click(sel, timeout=5000)
                log.info("Ek hizmetler geçildi ✅")
                _w(3, 5)
                return
            except Exception:
                pass
    except Exception as e:
        log.warning(f"Ek hizmetler hatası: {e}")


# ──────────────────────────────────────────────
# 6. REZERVASYON BİLGİSİ
# ──────────────────────────────────────────────

def pegasus_rezervasyon_bilgisi_al(sayfa) -> dict:
    try:
        _w(3, 5)
        sayfa.wait_for_load_state("networkidle", timeout=20000)
        _ss(sayfa, "09_pnr")
        pnr = ""
        for sel in ["*:has-text('PNR')", "[class*='pnr']", "[id*='pnr']"]:
            try:
                el = sayfa.query_selector(sel)
                if el:
                    m = re.search(r'\b([A-Z0-9]{5,6})\b', el.inner_text())
                    if m:
                        pnr = m.group(1)
                        break
            except Exception:
                pass
        log.info(f"PNR: {pnr or 'ALINAMADI'}")
        return {
            "pnr": pnr or "ALINAMADI",
            "mesaj": (
                f"✅ *Rezervasyon Oluşturuldu!*\n\nPNR: `{pnr or 'ALINAMADI'}`\n\n"
                "Pegasus acente ekranından ödemeyi tamamlayın."
            ),
        }
    except Exception as e:
        log.error(f"PNR hatası: {e}")
        return {"pnr": "ALINAMADI", "mesaj": "⚠️ PNR alınamadı. Pegasus'u kontrol edin."}
