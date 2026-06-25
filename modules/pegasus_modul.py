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
    MemberRezvEntry.jsp formunu doldurur, uçuş listesini döner.
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
        _bekle(3, 5)
        _ss(sayfa, "05_ana_ekran")

        # ── Tüm form elemanlarını logla (kalıcı diagnostic) ──────────────────
        try:
            elemanlar = sayfa.evaluate("""
                () => Array.from(document.querySelectorAll(
                    'input:not([type=hidden]), select, textarea, button, a[onclick]'
                ))
                .filter(el => el.offsetParent !== null)
                .map(el => ({
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    cls: (el.className || '').substring(0, 40),
                    val: (el.value || '').substring(0, 20),
                    txt: (el.innerText || '').trim().substring(0, 20)
                }))
            """)
            log.info(f"Form elemanları ({len(elemanlar)} adet):")
            for e in elemanlar[:30]:
                log.info(f"  {e['tag']}|{e['type']}|name={e['name']}|id={e['id']}|ph={e['placeholder']}|cls={e['cls']}|val={e['val']}|txt={e['txt']}")
        except Exception as ex:
            log.warning(f"Eleman log hatası: {ex}")

        # ── Uçuş tipi seç ─────────────────────────────────────────────────────
        if tip == "tek_yon":
            _tab_sec(sayfa, "Tek Yön")
        elif tip == "gidis_donus":
            _tab_sec(sayfa, "Gidiş - Dönüş")
        _bekle(1, 2)

        # ── Şehir ─────────────────────────────────────────────────────────────
        _sehir_sec(sayfa, nereden, "nereden")
        _bekle(1.5, 2.5)
        _sehir_sec(sayfa, nereye, "nereye")
        _bekle(1.5, 2.5)
        _ss(sayfa, "05b_sehir_sonrasi")

        # ── Tarih ─────────────────────────────────────────────────────────────
        if tip == "tek_yon":
            _tarih_sec(sayfa, komut.get("tarih", ""), "gidis")
        else:
            _tarih_sec(sayfa, komut.get("gidis_tarihi", ""), "gidis")
            _bekle(0.5, 1)
            _tarih_sec(sayfa, komut.get("donus_tarihi", ""), "donus")
        _bekle(1, 2)

        # ── Yolcu ─────────────────────────────────────────────────────────────
        _yolcu_sec(sayfa, yetiskin, cocuk, bebek)
        _bekle(1, 2)
        _ss(sayfa, "05c_form_dolu")

        # ── Ara butonu ────────────────────────────────────────────────────────
        _ara_tikla(sayfa)
        _bekle(3, 5)

        # ── Popup varsa geç ───────────────────────────────────────────────────
        for popup_sel in ["button:has-text('Devam')", "a:has-text('Devam')",
                          "button:has-text('Tamam')", "button:has-text('Kapat')"]:
            try:
                sayfa.wait_for_selector(popup_sel, timeout=5000)
                sayfa.click(popup_sel)
                log.info(f"Popup geçildi: {popup_sel}")
                _bekle(2, 3)
                break
            except Exception:
                pass

        # ── Sonuç sayfasını bekle ─────────────────────────────────────────────
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
    """Tek Yön / Gidiş-Dönüş / Çoklu Uçuş tabını seç."""
    for sel in [f"a:has-text('{metin}')", f"li:has-text('{metin}')",
                f"span:has-text('{metin}')", f"button:has-text('{metin}')",
                f"[class*='tab']:has-text('{metin}')"]:
        try:
            el = sayfa.query_selector(sel)
            if el and el.is_visible():
                el.click()
                log.info(f"Tab seçildi: {metin}")
                return
        except Exception:
            continue


def _sehir_input_bul(sayfa, tip: str):
    """
    Nereden/Nereye input elementini bul.
    Kesin bilinen: LAB_DEPPORT (nereden), LAB_ARRPORT (nereye)
    """
    # ── Strateji 0: Kesin bilinen selector'lar (logdan öğrenildi) ────────────
    kesin = ["input[name='LAB_DEPPORT']","input[id='LAB_DEPPORT']"] if tip == "nereden" \
        else ["input[name='LAB_ARRPORT']","input[id='LAB_ARRPORT']"]
    for sel in kesin:
        try:
            el = sayfa.query_selector(sel)
            if el:
                log.info(f"Şehir input ({tip}) kesin: {sel}")
                return el
        except Exception:
            continue

    label_metin = "Nereden" if tip == "nereden" else "Nereye"

    # ── Strateji 1: JS label proximity ───────────────────────────────────────
    info = sayfa.evaluate(f"""
        () => {{
            // Tüm visible elemanlar içinde exact metin eşleşmesi
            const lbl = Array.from(document.querySelectorAll('label,th,td,div,span,p'))
                .find(el => el.offsetParent !== null
                    && el.innerText && el.innerText.trim() === '{label_metin}');
            if (!lbl) return null;

            // label[for] → doğrudan input
            if (lbl.tagName === 'LABEL' && lbl.htmlFor) {{
                const inp = document.getElementById(lbl.htmlFor);
                if (inp && inp.type !== 'hidden') return {{id: inp.id, name: inp.name, via:'label[for]'}};
            }}

            // Aynı kapsayıcı içindeki ilk input
            for (const scope of [lbl.parentElement, lbl.closest('td'), lbl.closest('div'), lbl.closest('tr')]) {{
                if (!scope) continue;
                for (const inp of scope.querySelectorAll('input:not([type=hidden])')) {{
                    if (inp.offsetParent !== null) return {{id: inp.id, name: inp.name, via:'scope'}};
                }}
            }}

            // Sonraki sibling'larda input ara (max 5 adım)
            let cur = lbl.nextElementSibling;
            for (let i=0; i<5 && cur; i++, cur=cur.nextElementSibling) {{
                if (cur.tagName==='INPUT' && cur.type!=='hidden' && cur.offsetParent!==null)
                    return {{id: cur.id, name: cur.name, via:'nextSibling'}};
                const inp = cur.querySelector && cur.querySelector('input:not([type=hidden])');
                if (inp && inp.offsetParent!==null) return {{id: inp.id, name: inp.name, via:'siblingChild'}};
            }}
            return null;
        }}
    """)

    if info:
        for attr in ['id', 'name']:
            v = info.get(attr)
            if v:
                sel = f"input[{attr}='{v}']"
                try:
                    el = sayfa.query_selector(sel)
                    if el and el.is_visible():
                        log.info(f"Şehir input ({tip}) JS ile bulundu: {sel} via={info.get('via')}")
                        return el
                except Exception:
                    pass

    # ── Strateji 2: Bilinen selector listesi ─────────────────────────────────
    if tip == "nereden":
        adaylar = [
            "input[name='ORIGIN_CITY']","input[name='originCity']",
            "input[name='ORIGIN']","input[name='origin']",
            "input[name='FROM']","input[name='from']",
            "input[name='KALKIS']","input[name='kalkis']",
            "input[id*='rigin']","input[id*='Origin']",
            "input[id*='from']","input[id*='From']",
            "input[id*='kalkis']","input[id*='Kalkis']",
            "input[placeholder*='Nereden']","input[placeholder*='nereden']",
            "input[placeholder*='Kalkış']","input[placeholder*='kalkış']",
        ]
    else:
        adaylar = [
            "input[name='DESTINATION_CITY']","input[name='destinationCity']",
            "input[name='DESTINATION']","input[name='destination']",
            "input[name='DEST']","input[name='dest']",
            "input[name='TO']","input[name='to']",
            "input[name='VARIS']","input[name='varis']",
            "input[id*='estination']","input[id*='Destination']",
            "input[id*='to']","input[id*='To']",
            "input[id*='varis']","input[id*='Varis']",
            "input[placeholder*='Nereye']","input[placeholder*='nereye']",
            "input[placeholder*='Varış']","input[placeholder*='varış']",
        ]
    for sel in adaylar:
        try:
            el = sayfa.query_selector(sel)
            if el and el.is_visible():
                log.info(f"Şehir input ({tip}) selector ile bulundu: {sel}")
                return el
        except Exception:
            continue

    # ── Strateji 3: Sayfadaki tüm görünür text input'lar — sıra indexi ───────
    idx = 0 if tip == "nereden" else 1
    try:
        tum = sayfa.evaluate("""
            () => Array.from(document.querySelectorAll('input'))
                .filter(el => el.offsetParent !== null
                    && el.type !== 'hidden'
                    && el.type !== 'submit'
                    && el.type !== 'checkbox'
                    && el.type !== 'radio'
                    && el.type !== 'button')
                .map(el => ({id: el.id, name: el.name}))
        """)
        if len(tum) > idx:
            info2 = tum[idx]
            for attr in ['id', 'name']:
                v = info2.get(attr)
                if v:
                    sel = f"input[{attr}='{v}']"
                    el = sayfa.query_selector(sel)
                    if el and el.is_visible():
                        log.info(f"Şehir input ({tip}) index={idx} ile bulundu: {sel}")
                        return el
    except Exception:
        pass

    log.warning(f"Şehir input bulunamadı ({tip})")
    return None


def _sehir_sec(sayfa, iata: str, tip: str):
    arama = SEHIR_ARAMA.get(iata, iata)
    girdi = _sehir_input_bul(sayfa, tip)

    if not girdi:
        log.warning(f"Şehir alanı bulunamadı ({tip}-{iata}), atlıyorum")
        return

    try:
        # ── Tıkla ve temizle ─────────────────────────────────────────────────
        # Selector string: click_count için gerekli
        sel_str = "input[name='LAB_DEPPORT']" if tip == "nereden" else "input[name='LAB_ARRPORT']"

        girdi.click()
        _bekle(0.3, 0.5)
        # ElementHandle.triple_click yok — click_count kullan
        try:
            sayfa.click(sel_str, click_count=3)
        except Exception:
            girdi.click()
        _bekle(0.1, 0.2)

        # ── Yaz — React/custom input için native value setter + events ─────────
        girdi.click()
        _bekle(0.2, 0.3)
        girdi.fill("")

        # React synthetic event ile yaz (custom SelectBox için gerekli)
        try:
            sayfa.evaluate(f"""
                () => {{
                    const sel = "input[name='LAB_DEPPORT'], input[id='LAB_DEPPORT'], input[name='LAB_ARRPORT'], input[id='LAB_ARRPORT']";
                    const inputs = document.querySelectorAll(sel);
                    const inp = document.activeElement && document.activeElement.name &&
                        (document.activeElement.name === 'LAB_DEPPORT' || document.activeElement.name === 'LAB_ARRPORT')
                        ? document.activeElement
                        : Array.from(inputs).find(el => el.offsetParent !== null);
                    if (!inp) return;
                    const nativeSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    nativeSetter.call(inp, {repr(arama)});
                    inp.dispatchEvent(new Event('input', {{bubbles:true}}));
                    inp.dispatchEvent(new Event('change', {{bubbles:true}}));
                    inp.dispatchEvent(new KeyboardEvent('keyup', {{bubbles:true, key:'a'}}));
                }}
            """)
        except Exception:
            pass

        # Ek olarak karakter karakter de yaz (fallback)
        try:
            for c in arama:
                girdi.press(c)
                time.sleep(0.06)
        except Exception:
            pass

        _bekle(2, 3)
        _ss(sayfa, f"sehir_yazildi_{tip}")

        # ── Dropdown açıldıktan sonra ne göründüğünü logla ───────────────────
        try:
            gorunen = sayfa.evaluate("""
                () => Array.from(document.querySelectorAll('li, [class*="option"], [class*="item"], [role="option"]'))
                    .filter(el => el.offsetParent !== null && el.innerText.trim().length > 0)
                    .slice(0, 10)
                    .map(el => el.tagName + '|' + (el.className||'').substring(0,50) + '|' + el.innerText.trim().substring(0,30))
            """)
            log.info(f"Dropdown elemanları ({tip}): {gorunen}")
        except Exception:
            pass

        # ── BRUTE FORCE: Sayfadaki tüm visible leaf node'ları tara ───────────
        # Dropdown hangi class'la gelirse gelsin, arama metnini içeren ilk
        # tıklanabilir elementi bul.
        secildi = False
        try:
            eslesen = sayfa.evaluate(f"""
                () => {{
                    const ara = {repr(arama.lower())};
                    // Aktif input'u ve onun genel alanını bul
                    const aktif = document.activeElement;

                    // Tüm visible elemanları tara — leaf node veya az çocuklu
                    const adaylar = Array.from(document.querySelectorAll('*'))
                        .filter(el => {{
                            if (!el.offsetParent) return false;
                            if (el === aktif) return false;
                            if (['SCRIPT','STYLE','HEAD','BODY','HTML'].includes(el.tagName)) return false;
                            const txt = (el.innerText || '').trim();
                            if (!txt.toLowerCase().includes(ara)) return false;
                            // Leaf node veya çok az çocuk
                            const visKids = Array.from(el.children).filter(c => c.offsetParent);
                            return visKids.length <= 2;
                        }});

                    if (adaylar.length === 0) return null;
                    adaylar[0].click();
                    return adaylar[0].innerText.trim().substring(0, 40);
                }}
            """)
            if eslesen:
                secildi = True
                log.info(f"Şehir brute-force seçildi ({tip}): '{eslesen}'")
        except Exception as be:
            log.warning(f"Brute-force hatası ({tip}): {be}")

        if not secildi:
            # Son çare: ArrowDown + Enter
            sayfa.keyboard.press("ArrowDown")
            _bekle(0.4, 0.6)
            sayfa.keyboard.press("Enter")
            log.info(f"Şehir ArrowDown+Enter ({tip})")

        _bekle(0.5, 1)
        log.info(f"Şehir seçildi: {arama} ({iata}-{tip})")

    except Exception as e:
        log.warning(f"Şehir seçim hatası ({tip}-{iata}): {e}")


def _tarih_sec(sayfa, tarih: str, tip: str):
    try:
        if not tarih:
            return
        p = tarih.split("-")
        if len(p) != 3:
            return
        # tarih formatı: YYYY-MM-DD
        yil, ay, gun = int(p[0]), int(p[1]), int(p[2])
        tarih_str = f"{gun:02d}/{ay:02d}/{yil}"  # DD/MM/YYYY

        # ── Tarih input'unu bul ───────────────────────────────────────────────
        if tip == "gidis":
            adaylar = [
                "input[name='FLTDATE']","input[id='FLTDATE']",  # Pegasus kesin
                "input[name='DEPARTURE_DATE']","input[name='departureDate']",
                "input[name='DEPART_DATE']","input[name='departDate']",
                "input[name='DEPART']","input[name='depart']",
                "input[name='GIDIS_TARIHI']","input[name='gidisTarihi']",
                "input[name='DATE']","input[name='date']",
                "input[id*='depart']","input[id*='Depart']","input[id*='DEPART']",
                "input[id*='gidis']","input[id*='date']","input[id*='Date']",
                "input[placeholder*='Gidiş']","input[placeholder*='gidiş']",
                "input[placeholder*='Kalkış']",
            ]
            label_ara = "Gidiş Tarihi"
        else:
            adaylar = [
                "input[name='RETURN_DATE']","input[name='returnDate']",
                "input[name='RETURN']","input[name='return']",
                "input[name='DONUS_TARIHI']","input[name='donusTarihi']",
                "input[id*='return']","input[id*='Return']","input[id*='RETURN']",
                "input[id*='donus']","input[id*='Donus']",
                "input[placeholder*='Dönüş']","input[placeholder*='dönüş']",
            ]
            label_ara = "Dönüş Tarihi"

        girdi = None
        for sel in adaylar:
            try:
                el = sayfa.query_selector(sel)
                if el and el.is_visible():
                    girdi = el
                    log.info(f"Tarih input ({tip}): {sel}")
                    break
            except Exception:
                continue

        # JS label proximity fallback
        if not girdi:
            info = sayfa.evaluate(f"""
                () => {{
                    const lbl = Array.from(document.querySelectorAll('*'))
                        .find(el => el.offsetParent!==null && el.innerText
                            && el.innerText.trim().startsWith('{label_ara}')
                            && !['INPUT','SELECT'].includes(el.tagName));
                    if (!lbl) return null;
                    for (const scope of [lbl.parentElement, lbl.closest('td'), lbl.closest('div'), lbl.closest('tr')]) {{
                        if (!scope) continue;
                        const inp = scope.querySelector('input:not([type=hidden])');
                        if (inp && inp.offsetParent!==null) return {{id:inp.id, name:inp.name}};
                    }}
                    return null;
                }}
            """)
            if info:
                for attr in ['id','name']:
                    v = info.get(attr)
                    if v:
                        el = sayfa.query_selector(f"input[{attr}='{v}']")
                        if el and el.is_visible():
                            girdi = el
                            log.info(f"Tarih input ({tip}) JS ile bulundu: {attr}={v}")
                            break

        if not girdi:
            log.warning(f"Tarih alanı bulunamadı ({tip}), atlıyorum")
            return

        # ── Direkt değer yaz (masked input desteği) ──────────────────────────
        try:
            girdi.click()
            _bekle(0.3, 0.5)
            # Masked input için triple_click + type
            girdi.triple_click()
            girdi.type(tarih_str, delay=60)
            sayfa.keyboard.press("Tab")
            _bekle(0.5, 1)
            # Değer settiyse takvim açılmadı demektir — kontrol et
            deger = girdi.input_value()
            if tarih_str in deger or str(gun) in deger:
                log.info(f"Tarih direkt yazıldı ({tip}): {tarih_str}")
                return
        except Exception:
            pass

        # ── Takvim popup ile seç ─────────────────────────────────────────────
        try:
            girdi.click()
            _bekle(1, 1.5)
        except Exception:
            pass
        _takvim_sec(sayfa, gun, ay, yil)

    except Exception as e:
        log.warning(f"Tarih hatası ({tip}): {e}")


def _takvim_sec(sayfa, gun: int, ay: int, yil: int):
    AYLAR = {1:"Ocak",2:"Şubat",3:"Mart",4:"Nisan",5:"Mayıs",6:"Haziran",
              7:"Temmuz",8:"Ağustos",9:"Eylül",10:"Ekim",11:"Kasım",12:"Aralık"}

    BASLIK_SELS = [
        "[class*='calendar-caption']",
        "[class*='datepicker-title']",
        "[class*='datepicker-switch']",
        "th[class*='month']",
        ".ui-datepicker-title",
        "[class*='month-title']",
        "[class*='cal-header']",
    ]
    ILERI_SELS = [
        "[class*='calendar'] [class*='next']",
        ".ui-datepicker-next",
        "th[class*='next']",
        "button[class*='next']",
        "a[class*='next']",
        "[title*='Sonraki']","[title*='Next']","[title*='İleri']",
        "button:has-text('>')","a:has-text('>')","span:has-text('>')",
    ]
    GUN_SELS = [
        "[class*='datepicker'] td a:not([class*='disabled'])",
        "[class*='datepicker'] td:not([class*='disabled']):not([class*='empty'])",
        "[class*='calendar'] td:not([class*='disabled']):not([class*='empty'])",
        ".ui-datepicker td:not(.ui-datepicker-unselectable) a",
        ".ui-datepicker td:not(.ui-datepicker-unselectable)",
        "table[class*='cal'] td:not([class*='off'])",
    ]

    try:
        _bekle(1, 1.5)
        for _ in range(36):  # max 36 ay ileri
            # Başlık bul
            baslik_el = None
            for bsel in BASLIK_SELS:
                try:
                    el = sayfa.query_selector(bsel)
                    if el and el.is_visible():
                        baslik_el = el
                        break
                except Exception:
                    continue

            if not baslik_el:
                log.warning("Takvim başlığı bulunamadı")
                break

            metin = baslik_el.inner_text().strip()
            m_ay = m_yil = None
            for no, ad in AYLAR.items():
                if ad in metin:
                    m_ay = no
                    y = re.search(r'\d{4}', metin)
                    if y:
                        m_yil = int(y.group())
                    break

            if m_ay == ay and m_yil == yil:
                # Doğru ay — günü bul
                for gsel in GUN_SELS:
                    try:
                        gunler = sayfa.query_selector_all(gsel)
                        for g in gunler:
                            try:
                                txt = g.inner_text().strip()
                                if txt == str(gun):
                                    g.click()
                                    log.info(f"Tarih takvimden seçildi: {gun}.{ay}.{yil}")
                                    _bekle(0.5, 1)
                                    return
                            except Exception:
                                continue
                    except Exception:
                        continue
                log.warning(f"Gün {gun} takvimde bulunamadı")
                break

            # Bir sonraki aya geç
            gecildi = False
            for isel in ILERI_SELS:
                try:
                    el = sayfa.query_selector(isel)
                    if el and el.is_visible():
                        el.click()
                        _bekle(0.4, 0.8)
                        gecildi = True
                        break
                except Exception:
                    continue
            if not gecildi:
                log.warning("Takvim ileri butonu bulunamadı")
                break

    except Exception as e:
        log.warning(f"Takvim hatası: {e}")


def _yolcu_sec(sayfa, yetiskin: int, cocuk: int, bebek: int):
    """
    Screenshottaki 3 select dropdown: '1 Kişi', '0 Çocuk', '0 Bebek'
    Strateji: selector listesi → JS label proximity → index fallback
    """

    def _select_sec(adaylar: list, label_ara: str, deger_label: str, deger_idx: int):
        """Select'i bul ve istenen değeri seç."""
        girdi = None

        # Selector listesini dene
        for sel in adaylar:
            try:
                el = sayfa.query_selector(sel)
                if el and el.is_visible():
                    girdi = el
                    log.info(f"Select bulundu: {sel}")
                    break
            except Exception:
                continue

        # JS label proximity
        if not girdi:
            info = sayfa.evaluate(f"""
                () => {{
                    const lbl = Array.from(document.querySelectorAll('*'))
                        .find(el => el.offsetParent!==null && el.innerText
                            && el.innerText.trim().includes('{label_ara}')
                            && el.tagName!=='SELECT');
                    if (!lbl) return null;
                    for (const scope of [lbl.parentElement, lbl.closest('td'), lbl.closest('div'), lbl.closest('tr')]) {{
                        if (!scope) continue;
                        const sel = scope.querySelector('select');
                        if (sel && sel.offsetParent!==null) return {{id:sel.id, name:sel.name}};
                    }}
                    return null;
                }}
            """)
            if info:
                for attr in ['id','name']:
                    v = info.get(attr)
                    if v:
                        el = sayfa.query_selector(f"select[{attr}='{v}']")
                        if el and el.is_visible():
                            girdi = el
                            log.info(f"Select JS ile bulundu: {attr}={v}")
                            break

        # Index fallback — sayfadaki kaçıncı select
        if not girdi:
            try:
                tum = sayfa.query_selector_all("select")
                vis = [el for el in tum if el.is_visible()]
                if len(vis) > deger_idx:
                    girdi = vis[deger_idx]
                    log.info(f"Select index={deger_idx} ile bulundu")
            except Exception:
                pass

        if not girdi:
            log.warning(f"Select bulunamadı: {label_ara}")
            return

        # Değeri seç — label ile, başarısızsa index ile
        try:
            girdi.select_option(label=deger_label)
            log.info(f"Select seçildi (label): {deger_label}")
            return
        except Exception:
            pass
        try:
            girdi.select_option(index=deger_idx)
            log.info(f"Select seçildi (index): {deger_idx}")
        except Exception as e:
            log.warning(f"Select seçim hatası ({label_ara}): {e}")

    try:
        _select_sec(
            ["select[name*='ADULT']","select[name*='adult']","select[name*='PAX']",
             "select[name*='pax']","select[id*='adult']","select[id*='ADULT']",
             "select[id*='kisi']","select[name*='kisi']"],
            "Kişi", f"{yetiskin} Kişi", yetiskin - 1
        )
        _bekle(0.3, 0.5)
        _select_sec(
            ["select[name*='CHILD']","select[name*='child']","select[id*='child']",
             "select[id*='CHILD']","select[name*='cocuk']","select[id*='cocuk']"],
            "Çocuk", f"{cocuk} Çocuk", cocuk
        )
        _bekle(0.3, 0.5)
        _select_sec(
            ["select[name*='INFANT']","select[name*='infant']","select[id*='infant']",
             "select[id*='INFANT']","select[name*='bebek']","select[id*='bebek']"],
            "Bebek", f"{bebek} Bebek", bebek
        )
        log.info(f"Yolcu seçildi: {yetiskin}Y {cocuk}Ç {bebek}B")
    except Exception as e:
        log.warning(f"Yolcu hatası: {e}")


def _ara_tikla(sayfa):
    """
    Uçuş arama formunu submit et.
    LAB_DEPPORT input'unun bulunduğu formu bul ve o formu submit et.
    Araç kiralama gibi başka 'Ara' butonlarına BASMAMAK için form bazlı yaklaşım.
    """
    # ── 1. LAB_DEPPORT'un bulunduğu formda input[type=submit] ara ────────────
    # Dikkat: formun içindeki ilk button sekme (Gidiş-Dönüş/Tek Yön) olabilir,
    # onları atla — sadece input[type=submit] veya value='Ara' olan butonu bul.
    try:
        ok = sayfa.evaluate("""
            () => {
                const inp = document.querySelector(
                    "input[name='LAB_DEPPORT'], input[id='LAB_DEPPORT']"
                );
                if (!inp) return null;
                const frm = inp.closest('form');
                if (!frm) return null;

                // Önce input[type=submit] dene (en güvenli)
                const sub = frm.querySelector('input[type=submit]');
                if (sub && sub.offsetParent !== null) {
                    sub.click();
                    return 'input[type=submit]:' + (sub.value||'').trim();
                }

                // Değeri 'Ara' olan input/button
                for (const el of frm.querySelectorAll('input, button, a')) {
                    const v = (el.value || el.innerText || '').trim();
                    const tabTexts = ['Gidiş','Dönüş','Tek Yön','Çoklu'];
                    if (v === 'Ara' && !tabTexts.some(t => v.includes(t))) {
                        if (el.offsetParent !== null) {
                            el.click();
                            return 'Ara-el:' + el.tagName + ':' + v;
                        }
                    }
                }

                // Son çare: form submit
                frm.submit();
                return 'form.submit';
            }
        """)
        if ok:
            log.info(f"Ara (form tabanlı): {ok}")
            return
    except Exception as e:
        log.warning(f"Form submit hatası: {e}")

    # ── 2. Spesifik selector'lar ──────────────────────────────────────────────
    for sel in [
        "input[value='Ara']","input[value='ARA']","input[value='SEARCH']",
        "[class*='tstnm_fly_search_search']","[class*='tstnm_search']",
        "[class*='fly-search'] input[type='submit']",
        "[class*='searchButton']","[class*='search-button']",
    ]:
        try:
            el = sayfa.query_selector(sel)
            if el and el.is_visible():
                el.click()
                log.info(f"Ara tıklandı: {sel}")
                return
        except Exception:
            continue

    log.warning("Ara butonu bulunamadı — hiçbir strateji çalışmadı")


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
