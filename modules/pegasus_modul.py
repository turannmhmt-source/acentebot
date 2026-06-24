import time
import re
from modules.logger import get_logger
from modules.tarayici import insan_gibi_bekle, hata_screenshot

log = get_logger("pegasus")

PEGASUS_URL = "https://acente.flypgs.com/"
PEGASUS_ANA_URL = "https://acente.flypgs.com/MemberRezvEntry.jsp"
ACENTE_TEL_ALAN = "555"
ACENTE_TEL_NO = "0094805"
ACENTE_EMAIL = "masaraturizm@gmail.com"

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


def _yeni_sayfa_ac(tarayici):
    try:
        konteks = tarayici.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        sayfa = konteks.new_page()
        log.info("Yeni context açıldı")
        return konteks, sayfa
    except Exception as e:
        log.warning(f"new_context hatası: {e}")

    try:
        if hasattr(tarayici, 'new_page'):
            konteks = tarayici
            sayfa = konteks.new_page()
            log.info("Persistent context kullanıldı")
            return konteks, sayfa
    except Exception as e:
        log.warning(f"persistent new_page hatası: {e}")

    try:
        if hasattr(tarayici, 'contexts') and tarayici.contexts:
            konteks = tarayici.contexts[0]
            sayfa = konteks.new_page()
            log.info("Mevcut context kullanıldı")
            return konteks, sayfa
    except Exception as e:
        log.warning(f"Mevcut context hatası: {e}")

    raise Exception("Sayfa açılamadı")


def pegasus_giris_baslat(tarayici) -> tuple:
    sayfa = None
    konteks = None
    try:
        import config as cfg

        konteks, sayfa = _yeni_sayfa_ac(tarayici)

        log.info("Pegasus açılıyor...")
        sayfa.goto(PEGASUS_URL, wait_until="domcontentloaded", timeout=30000)
        insan_gibi_bekle(2, 3)

        # USERNAME alanı görünene kadar bekle (sayfanın JS'i yüklemesi için)
        try:
            sayfa.wait_for_selector(
                "input[name='USERNAME']",
                timeout=20000,
                state="visible"
            )
        except Exception as e:
            log.error(f"USERNAME alanı bulunamadı: {e}")
            hata_screenshot(sayfa, "pegasus_username_yok")
            return None, None

        log.info(f"URL: {sayfa.url}")

        # Kullanıcı adı
        sayfa.fill("input[name='USERNAME']", cfg.PEGASUS_KULLANICI)
        insan_gibi_bekle(0.5, 1)
        log.info(f"Kullanıcı adı: {cfg.PEGASUS_KULLANICI}")

        # Şifre
        sayfa.fill("input[name='PASSWORD']", cfg.PEGASUS_SIFRE)
        insan_gibi_bekle(0.5, 1)
        log.info("Şifre dolduruldu")

        # Mevcut butonları logla (debug)
        butonlar = sayfa.query_selector_all("button")
        log.info(f"{len(butonlar)} buton bulundu:")
        for b in butonlar:
            try:
                log.info(f"  → '{b.inner_text().strip()}'")
            except:
                pass

        tiklandi = False

        # Yöntem 1: Password alanında Enter bas (en güvenilir — form submit)
        if not tiklandi:
            try:
                sayfa.press("input[name='PASSWORD']", "Enter")
                insan_gibi_bekle(2, 3)
                # OTP ekranı veya farklı bir sayfa açıldıysa başarılı say
                if "OTP" in sayfa.url or sayfa.query_selector("input[name='OTP_INPUT']"):
                    tiklandi = True
                    log.info("Yöntem 1: Enter ile submit ✅")
                else:
                    # Sayfa değişti mi kontrol et
                    tiklandi = sayfa.url != PEGASUS_URL
                    if tiklandi:
                        log.info(f"Yöntem 1: Enter çalıştı, yeni URL: {sayfa.url} ✅")
            except Exception as e:
                log.warning(f"Yöntem 1 (Enter): {e}")

        # Yöntem 2: Frame'lerde buton ara
        if not tiklandi:
            try:
                tum_frameler = sayfa.frames
                log.info(f"{len(tum_frameler)} frame bulundu")
                for frame in tum_frameler:
                    try:
                        btn = frame.query_selector("button:has-text('Üye Girişi')")
                        if not btn:
                            btn = frame.query_selector("input[type='submit']")
                        if btn and btn.is_visible():
                            btn.click()
                            tiklandi = True
                            log.info("Yöntem 2: Frame içinde buton tıklandı ✅")
                            break
                    except:
                        continue
            except Exception as e:
                log.warning(f"Yöntem 2 (frame): {e}")

        # Yöntem 3: Ana sayfada metin ile ara
        if not tiklandi:
            try:
                btn = sayfa.query_selector("button:has-text('Üye Girişi')")
                if btn and btn.is_visible():
                    btn.click()
                    tiklandi = True
                    log.info("Yöntem 3: Ana sayfada buton tıklandı ✅")
            except Exception as e:
                log.warning(f"Yöntem 3 (metin): {e}")

        # Yöntem 4: JavaScript — tüm tıklanabilir elementleri tara
        if not tiklandi:
            try:
                sonuc = sayfa.evaluate("""
                    () => {
                        const elems = Array.from(
                            document.querySelectorAll('button, input[type=submit], a, div[onclick], span[onclick]')
                        );
                        for (let el of elems) {
                            const t = (el.textContent || el.value || el.innerText || '').trim();
                            if (t.includes('ye Giri') || t.includes('Üye') || t.includes('Login')) {
                                el.click();
                                return t;
                            }
                        }
                        return null;
                    }
                """)
                if sonuc:
                    tiklandi = True
                    log.info(f"Yöntem 4: JS tıklandı ✅: {sonuc}")
            except Exception as e:
                log.warning(f"Yöntem 4 (JS): {e}")

        # Yöntem 5: Tab + Enter klavye navigasyonu
        if not tiklandi:
            try:
                sayfa.focus("input[name='PASSWORD']")
                insan_gibi_bekle(0.3, 0.5)
                for _ in range(5):
                    sayfa.keyboard.press("Tab")
                    insan_gibi_bekle(0.2, 0.3)
                    focused = sayfa.evaluate("() => document.activeElement?.tagName")
                    if focused in ("BUTTON", "INPUT", "A"):
                        sayfa.keyboard.press("Enter")
                        tiklandi = True
                        log.info(f"Yöntem 5: Tab+Enter ✅ (element: {focused})")
                        break
            except Exception as e:
                log.warning(f"Yöntem 5 (Tab+Enter): {e}")

        # Yöntem 6: Form submit JS
        if not tiklandi:
            try:
                sonuc = sayfa.evaluate("""
                    () => {
                        const form = document.querySelector('form');
                        if (form) { form.submit(); return true; }
                        return false;
                    }
                """)
                if sonuc:
                    tiklandi = True
                    log.info("Yöntem 6: form.submit() ✅")
            except Exception as e:
                log.warning(f"Yöntem 6 (form submit): {e}")

        if not tiklandi:
            log.error("Üye Girişi butonu bulunamadı — tüm yöntemler başarısız")
            hata_screenshot(sayfa, "pegasus_buton_yok")
            return None, None

        insan_gibi_bekle(3, 5)
        hata_screenshot(sayfa, "pegasus_giris_sonrasi")

        # OTP ekranı
        try:
            sayfa.wait_for_selector(
                "input[name='OTP_INPUT']",
                timeout=15000,
                state="visible"
            )
            log.info("OTP ekranı açıldı ✅")
        except Exception:
            log.error("OTP ekranı açılmadı")
            hata_screenshot(sayfa, "pegasus_otp_yok")
            return None, None

        # SMS Gönder
        try:
            sms = sayfa.query_selector("button:has-text('SMS Gönder')")
            if sms and sms.is_visible():
                sms.click()
                log.info("SMS Gönder tıklandı ✅")
                insan_gibi_bekle(2, 3)
        except Exception as e:
            log.warning(f"SMS buton hatası: {e}")

        hata_screenshot(sayfa, "pegasus_otp_ekrani")
        log.info("SMS gönderildi — kod bekleniyor")
        return konteks, sayfa

    except Exception as e:
        log.error(f"Pegasus giriş hatası: {e}")
        if sayfa:
            hata_screenshot(sayfa, "pegasus_hata")
        return None, None


def pegasus_otp_gir(konteks, sayfa, otp_kodu: str):
    try:
        log.info(f"OTP giriliyor: {otp_kodu}")
        sayfa.fill("input[name='OTP_INPUT']", otp_kodu.strip())
        insan_gibi_bekle(0.5, 1)

        with konteks.expect_page(timeout=30000) as yeni_bilgi:
            sayfa.click("button:has-text('Giriş yap')")

        yeni_sayfa = yeni_bilgi.value
        yeni_sayfa.wait_for_load_state("networkidle", timeout=30000)
        insan_gibi_bekle(3, 5)

        log.info(f"Yeni pencere: {yeni_sayfa.url}")
        hata_screenshot(yeni_sayfa, "pegasus_ana_ekran")

        if "acente.flypgs.com" in yeni_sayfa.url:
            log.info("Pegasus ana ekranı açıldı ✅")
            return yeni_sayfa
        else:
            log.error(f"Beklenmeyen URL: {yeni_sayfa.url}")
            return None

    except Exception as e:
        log.error(f"OTP hatası: {e}")
        if sayfa:
            hata_screenshot(sayfa, "pegasus_otp_hata")
        return None


def pegasus_ucus_sorgula(sayfa, komut: dict) -> list:
    try:
        import config as cfg

        tip = komut.get("tip", "tek_yon")
        nereden = komut.get("nereden", "IST")
        nereye = komut.get("nereye", "")
        yetiskin = komut.get("yetiskin", 1)
        cocuk = komut.get("cocuk", 0)
        bebek = komut.get("bebek", 0)
        direkt_mi = komut.get("direkt_mi", True)

        log.info(f"Sorgu: {nereden}→{nereye} tip={tip}")

        sayfa.goto(PEGASUS_ANA_URL, wait_until="networkidle", timeout=30000)
        insan_gibi_bekle(2, 3)

        if tip == "tek_yon":
            try:
                sayfa.click("a:has-text('Tek Yön'), li:has-text('Tek Yön')")
                insan_gibi_bekle(1, 2)
            except:
                pass
        elif tip == "gidis_donus":
            try:
                sayfa.click("a:has-text('Gidiş - Dönüş')")
                insan_gibi_bekle(1, 2)
            except:
                pass

        _sehir_sec(sayfa, nereden, "nereden")
        insan_gibi_bekle(1, 2)
        _sehir_sec(sayfa, nereye, "nereye")
        insan_gibi_bekle(1, 2)

        if tip == "tek_yon":
            _tarih_sec(sayfa, komut.get("tarih", ""), "gidis")
        else:
            _tarih_sec(sayfa, komut.get("gidis_tarihi", ""), "gidis")
            insan_gibi_bekle(0.5, 1)
            _tarih_sec(sayfa, komut.get("donus_tarihi", ""), "donus")
        insan_gibi_bekle(1, 2)

        _yolcu_sec(sayfa, yetiskin, cocuk, bebek)
        insan_gibi_bekle(1, 2)

        sayfa.click("button:has-text('Ara'), input[value='Ara']")
        insan_gibi_bekle(3, 5)

        try:
            sayfa.wait_for_selector("button:has-text('Devam')", timeout=6000)
            sayfa.click("button:has-text('Devam')")
            log.info("Uyarı popup geçildi")
            insan_gibi_bekle(3, 5)
        except:
            pass

        try:
            sayfa.wait_for_url("**/MemberRezvResults**", timeout=30000)
        except:
            sayfa.wait_for_load_state("networkidle", timeout=20000)

        insan_gibi_bekle(3, 5)
        return _sonuclari_oku(sayfa, nereden, nereye, direkt_mi, cfg)

    except Exception as e:
        log.error(f"Uçuş sorgulama hatası: {e}")
        hata_screenshot(sayfa, "pegasus_sorgula_hata")
        return []


def _sehir_sec(sayfa, iata: str, tip: str):
    try:
        arama = SEHIR_ARAMA.get(iata, iata)
        if tip == "nereden":
            sel = "input[placeholder*='Nereden'], input[id*='from'], input[name*='from']"
        else:
            sel = "input[placeholder*='Nereye'], input[id*='to'], input[name*='to']"

        sayfa.wait_for_selector(sel, timeout=10000)
        sayfa.fill(sel, "")
        sayfa.type(sel, arama, delay=100)
        insan_gibi_bekle(1, 2)

        try:
            dd = (
                "[class*='suggestion'] li:first-child, "
                "[class*='autocomplete'] li:first-child, "
                "ul[class*='auto'] li:first-child"
            )
            sayfa.wait_for_selector(dd, timeout=5000)
            sayfa.click(dd)
        except:
            sayfa.keyboard.press("ArrowDown")
            insan_gibi_bekle(0.3, 0.5)
            sayfa.keyboard.press("Enter")

        log.info(f"Şehir: {arama} ({tip})")
    except Exception as e:
        log.warning(f"Şehir hatası ({tip}-{iata}): {e}")


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
        insan_gibi_bekle(1, 2)
        _takvim_sec(sayfa, gun, ay, yil)
    except Exception as e:
        log.warning(f"Tarih hatası ({tip}): {e}")


def _takvim_sec(sayfa, gun: int, ay: int, yil: int):
    AYLAR = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
        5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
        9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
    }
    try:
        for _ in range(24):
            insan_gibi_bekle(0.5, 1)
            baslik = sayfa.query_selector(
                "[class*='calendar-caption'], th[class*='month'], "
                "[class*='datepicker-title']"
            )
            if not baslik:
                break
            metin = baslik.inner_text()
            mevcut_ay = None
            mevcut_yil = None
            for no, ad in AYLAR.items():
                if ad in metin:
                    mevcut_ay = no
                    y = re.search(r'\d{4}', metin)
                    if y:
                        mevcut_yil = int(y.group())
                    break
            if mevcut_ay == ay and mevcut_yil == yil:
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
                sayfa.click(
                    "[class*='calendar'] [class*='next'], "
                    "th[class*='next'], button:has-text('>')"
                )
            except:
                break
    except Exception as e:
        log.warning(f"Takvim hatası: {e}")


def _yolcu_sec(sayfa, yetiskin: int, cocuk: int, bebek: int):
    try:
        try:
            sayfa.select_option(
                "select[id*='adult'], select[name*='adult']",
                label=f"{yetiskin} Kişi"
            )
        except:
            pass
        insan_gibi_bekle(0.3, 0.5)
        try:
            sayfa.select_option(
                "select[id*='child'], select[name*='child']",
                label=f"{cocuk} Çocuk"
            )
        except:
            pass
        insan_gibi_bekle(0.3, 0.5)
        try:
            sayfa.select_option(
                "select[id*='infant'], select[name*='infant']",
                label=f"{bebek} Bebek"
            )
        except:
            pass
        log.info(f"Yolcu: {yetiskin} Kişi, {cocuk} Çocuk, {bebek} Bebek")
    except Exception as e:
        log.warning(f"Yolcu hatası: {e}")


def _sonuclari_oku(sayfa, nereden, nereye, direkt_mi, cfg) -> list:
    try:
        sonuclar = []
        insan_gibi_bekle(2, 3)
        sayfa.wait_for_load_state("networkidle", timeout=20000)

        fiyat_linkleri = sayfa.query_selector_all(
            "a:has-text('Bütün Fiyatları Göster'), "
            "span:has-text('Bütün Fiyatları Göster')"
        )
        log.info(f"{len(fiyat_linkleri)} fiyat linki")
        for link in fiyat_linkleri:
            try:
                link.click()
                insan_gibi_bekle(0.5, 1)
            except:
                pass

        insan_gibi_bekle(2, 3)
        hata_screenshot(sayfa, "pegasus_sonuc_liste")

        ucus_satirlari = sayfa.query_selector_all(
            "tr:has(td):has([class*='flt']), "
            "tr:has(td[class*='flight']), "
            "[class*='flight-row'], "
            "table.table tbody tr"
        )
        log.info(f"{len(ucus_satirlari)} satır")
        komisyon = cfg.KOMISYON.get("pegasus", 8) / 100

        for satir in ucus_satirlari:
            try:
                metin = satir.inner_text().strip()
                if not metin:
                    continue
                if direkt_mi and (
                    "bağlantı" in metin.lower() or "1 Bağlantı" in metin
                ):
                    continue
                ucus_no_bul = re.search(r'PC\d+', metin)
                if not ucus_no_bul:
                    continue
                ucus_no = ucus_no_bul.group()
                saatler = re.findall(r'\d{2}:\d{2}', metin)
                kalkis = saatler[0] if len(saatler) > 0 else ""
                varis = saatler[1] if len(saatler) > 1 else ""
                sure_bul = re.search(r'(\d+)\s*sa\s*(\d+)?\s*dk?', metin)
                sure = ""
                if sure_bul:
                    sure = f"{sure_bul.group(1)}sa"
                    if sure_bul.group(2):
                        sure += f" {sure_bul.group(2)}dk"
                hava_limani = ""
                if "SAW" in metin or "Sabiha" in metin:
                    hava_limani = "SAW"
                elif "IST" in metin:
                    hava_limani = "IST"
                fiyat_listesi = []
                _fiyat_cek(metin, fiyat_listesi)
                if not fiyat_listesi:
                    continue
                paket_adlari = ["Light", "Süper Eko", "Avantaj", "Comfort Flex"]
                paketler = []
                for i, ad in enumerate(paket_adlari):
                    if i < len(fiyat_listesi):
                        haric = fiyat_listesi[i]
                        dahil = round(haric * (1 + komisyon), 2)
                        paketler.append({
                            "paket": ad,
                            "icerik": PAKET_ICERIKLERI.get(ad, ""),
                            "fiyat_haric": haric,
                            "fiyat_dahil": dahil,
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
                        "hava_limani": hava_limani,
                        "paketler": paketler,
                        "en_ucuz_haric": min(p["fiyat_haric"] for p in paketler),
                        "en_ucuz_dahil": min(p["fiyat_dahil"] for p in paketler),
                    })
            except Exception as e:
                log.warning(f"Satır hatası: {e}")
                continue

        log.info(f"Pegasus: {len(sonuclar)} uçuş")
        return sonuclar

    except Exception as e:
        log.error(f"Sonuç okuma hatası: {e}")
        hata_screenshot(sayfa, "pegasus_sonuc_hata")
        return []


def _fiyat_cek(metin: str, liste: list):
    eslesme = re.findall(
        r'([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*TRY', metin
    )
    for e in eslesme:
        temiz = e.replace(".", "").replace(",", ".")
        try:
            deger = float(temiz)
            if 100 < deger < 500000 and deger not in liste:
                liste.append(deger)
        except:
            pass


def pegasus_paket_sec(sayfa, ucus_no: str, paket_index: int) -> float:
    try:
        log.info(f"Paket: {ucus_no} index={paket_index}")
        ucus_satiri = sayfa.query_selector(f"tr:has-text('{ucus_no}')")
        if not ucus_satiri:
            log.error(f"Uçuş satırı yok: {ucus_no}")
            return 0.0

        radio_butonlar = ucus_satiri.query_selector_all("input[type='radio']")
        if radio_butonlar and paket_index < len(radio_butonlar):
            radio_butonlar[paket_index].click()
        else:
            fiyat_hucreler = ucus_satiri.query_selector_all(
                "td[class*='price'], td[class*='fare'], label"
            )
            if paket_index < len(fiyat_hucreler):
                fiyat_hucreler[paket_index].click()

        insan_gibi_bekle(2, 3)
        sayfa.keyboard.press("End")
        insan_gibi_bekle(1, 2)
        toplam = _toplam_fiyat_oku(sayfa)
        log.info(f"Toplam: {toplam} TRY")

        sayfa.click("button:has-text('Devam'), a:has-text('Devam')")
        insan_gibi_bekle(3, 5)

        try:
            sayfa.wait_for_selector(
                "a:has-text('Mevcut Seçimlerle İlerle'), "
                "button:has-text('Mevcut Seçimlerle İlerle')",
                timeout=8000
            )
            sayfa.click(
                "a:has-text('Mevcut Seçimlerle İlerle'), "
                "button:has-text('Mevcut Seçimlerle İlerle')"
            )
            log.info("Paket yükseltme geçildi")
            insan_gibi_bekle(3, 5)
        except:
            pass

        try:
            sayfa.wait_for_url("**/RezvPaxEntry**", timeout=20000)
        except:
            sayfa.wait_for_load_state("networkidle", timeout=20000)

        return toplam

    except Exception as e:
        log.error(f"Paket hatası: {e}")
        hata_screenshot(sayfa, "pegasus_paket_hata")
        return 0.0


def _toplam_fiyat_oku(sayfa) -> float:
    try:
        el = sayfa.query_selector(
            "[class*='total-price'], [class*='grand-total'], "
            "[id*='totalPrice'], strong:has-text('TRY')"
        )
        if el:
            metin = el.inner_text()
            bul = re.search(r'([\d.,]+)\s*TRY', metin)
            if bul:
                return float(bul.group(1).replace(".", "").replace(",", "."))
    except:
        pass
    return 0.0


def pegasus_yolcu_doldur(sayfa, yolcular: list) -> bool:
    try:
        log.info(f"{len(yolcular)} yolcu dolduruluyor")
        sayfa.wait_for_load_state("networkidle", timeout=20000)
        insan_gibi_bekle(2, 3)

        yetiskinler = [y for y in yolcular if y.get("tip") not in ["cocuk", "bebek"]]
        cocuklar = [y for y in yolcular if y.get("tip") == "cocuk"]
        bebekler = [y for y in yolcular if y.get("tip") == "bebek"]

        _yetiskin_doldur(sayfa, yetiskinler)
        _cocuk_doldur(sayfa, cocuklar, len(yetiskinler))
        _bebek_doldur(sayfa, bebekler, len(yetiskinler) + len(cocuklar))
        _iletisim_doldur(sayfa)
        _onay_sec(sayfa)

        insan_gibi_bekle(1, 2)
        sayfa.click(
            "button:has-text('Rezervasyonu Tamamla'), "
            "a:has-text('Rezervasyonu Tamamla')"
        )
        insan_gibi_bekle(5, 8)
        _ek_hizmetler_gec(sayfa)
        return True

    except Exception as e:
        log.error(f"Yolcu doldurma hatası: {e}")
        hata_screenshot(sayfa, "pegasus_yolcu_hata")
        return False


def _yetiskin_doldur(sayfa, yetiskinler: list):
    cinsiyet_sels = sayfa.query_selector_all(
        "select[name*='gender'], select[id*='gender']"
    )
    isim_sels = sayfa.query_selector_all(
        "input[name*='firstName'], input[id*='firstName']"
    )
    soyisim_sels = sayfa.query_selector_all(
        "input[name*='lastName'], input[id*='lastName']"
    )
    for i, y in enumerate(yetiskinler):
        try:
            if i < len(cinsiyet_sels):
                label = "Erkek" if y.get("cinsiyet", "E") == "E" else "Kadın"
                try:
                    cinsiyet_sels[i].select_option(label=label)
                except:
                    cinsiyet_sels[i].select_option(
                        value="E" if label == "Erkek" else "K"
                    )
                insan_gibi_bekle(0.3, 0.5)
            if i < len(isim_sels):
                isim_sels[i].fill(y.get("ad", "").upper())
                insan_gibi_bekle(0.2, 0.4)
            if i < len(soyisim_sels):
                soyisim_sels[i].fill(y.get("soyad", "").upper())
                insan_gibi_bekle(0.2, 0.4)
            _dogum_doldur(sayfa, i, y.get("dogum", ""))
            if not y.get("tc_vatandasi", True):
                _tc_degil_sec(sayfa, i)
            elif y.get("tc_no"):
                tc_sels = sayfa.query_selector_all(
                    "input[name*='tckn'], input[id*='tckn'], "
                    "input[placeholder*='TC']"
                )
                if i < len(tc_sels):
                    tc_sels[i].fill(y.get("tc_no", ""))
            log.info(f"Yetişkin {i+1}: {y.get('ad')} {y.get('soyad')}")
        except Exception as e:
            log.warning(f"Yetişkin {i+1} hatası: {e}")


def _cocuk_doldur(sayfa, cocuklar: list, offset: int):
    if not cocuklar:
        return
    isim_sels = sayfa.query_selector_all(
        "input[name*='firstName'], input[id*='firstName']"
    )
    soyisim_sels = sayfa.query_selector_all(
        "input[name*='lastName'], input[id*='lastName']"
    )
    for i, c in enumerate(cocuklar):
        idx = offset + i
        try:
            if idx < len(isim_sels):
                isim_sels[idx].fill(c.get("ad", "").upper())
            if idx < len(soyisim_sels):
                soyisim_sels[idx].fill(c.get("soyad", "").upper())
            _dogum_doldur(sayfa, idx, c.get("dogum", ""))
            if not c.get("tc_vatandasi", True):
                _tc_degil_sec(sayfa, idx)
            log.info(f"Çocuk {i+1} dolduruldu")
        except Exception as e:
            log.warning(f"Çocuk {i+1} hatası: {e}")


def _bebek_doldur(sayfa, bebekler: list, offset: int):
    if not bebekler:
        return
    ebeveyn_sels = sayfa.query_selector_all(
        "select[name*='parent'], select[id*='parent'], "
        "select:near(:text('Ebeveyn'))"
    )
    isim_sels = sayfa.query_selector_all(
        "input[name*='firstName'], input[id*='firstName']"
    )
    soyisim_sels = sayfa.query_selector_all(
        "input[name*='lastName'], input[id*='lastName']"
    )
    for i, b in enumerate(bebekler):
        idx = offset + i
        try:
            if i < len(ebeveyn_sels):
                try:
                    ebeveyn_sels[i].select_option(index=1)
                except:
                    pass
                insan_gibi_bekle(0.3, 0.5)
            if idx < len(isim_sels):
                isim_sels[idx].fill(b.get("ad", "").upper())
            if idx < len(soyisim_sels):
                soyisim_sels[idx].fill(b.get("soyad", "").upper())
            _dogum_doldur(sayfa, idx, b.get("dogum", ""))
            log.info(f"Bebek {i+1} dolduruldu")
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
            "01": "Ocak", "02": "Şubat", "03": "Mart",
            "04": "Nisan", "05": "Mayıs", "06": "Haziran",
            "07": "Temmuz", "08": "Ağustos", "09": "Eylül",
            "10": "Ekim", "11": "Kasım", "12": "Aralık"
        }
        ay_adi = AYLAR.get(ay, ay)
        gun_sels = sayfa.query_selector_all(
            "select[name*='Day'], select[name*='day'], select[id*='Day']"
        )
        ay_sels = sayfa.query_selector_all(
            "select[name*='Month'], select[name*='month'], select[id*='Month']"
        )
        yil_sels = sayfa.query_selector_all(
            "select[name*='Year'], select[name*='year'], select[id*='Year']"
        )
        if index < len(gun_sels):
            try:
                gun_sels[index].select_option(value=gun)
            except:
                gun_sels[index].select_option(label=gun)
        if index < len(ay_sels):
            try:
                ay_sels[index].select_option(label=ay_adi)
            except:
                ay_sels[index].select_option(value=str(int(ay)))
        if index < len(yil_sels):
            yil_sels[index].select_option(value=yil)
    except Exception as e:
        log.warning(f"Doğum hatası (idx={index}): {e}")


def _tc_degil_sec(sayfa, index: int):
    try:
        cbs = sayfa.query_selector_all(
            "input[type='checkbox']:near(:text('T.C. Vatandaşı Değil'))"
        )
        if index < len(cbs) and not cbs[index].is_checked():
            cbs[index].click()
    except Exception as e:
        log.warning(f"TC değil hatası: {e}")


def _iletisim_doldur(sayfa):
    try:
        log.info("İletişim dolduruluyor")
        try:
            cb = sayfa.query_selector(
                "input[type='checkbox']:near(:text('İlk Yolcu Bilgilerini Getir'))"
            )
            if cb and not cb.is_checked():
                cb.click()
                insan_gibi_bekle(1, 2)
        except:
            pass

        insan_gibi_bekle(1, 2)

        tel_sels = sayfa.query_selector_all(
            "input[name*='phone'], input[id*='phone'], input[type='tel']"
        )
        if len(tel_sels) >= 2:
            tel_sels[0].fill(ACENTE_TEL_ALAN)
            insan_gibi_bekle(0.3, 0.5)
            tel_sels[1].fill(ACENTE_TEL_NO)
        elif len(tel_sels) == 1:
            tel_sels[0].fill(ACENTE_TEL_ALAN + ACENTE_TEL_NO)

        if len(tel_sels) >= 4:
            tel_sels[2].fill(ACENTE_TEL_ALAN)
            insan_gibi_bekle(0.3, 0.5)
            tel_sels[3].fill(ACENTE_TEL_NO)

        insan_gibi_bekle(0.5, 1)

        email_sels = sayfa.query_selector_all(
            "input[type='email'], input[name*='email'], input[id*='email']"
        )
        if email_sels:
            email_sels[0].fill(ACENTE_EMAIL)

        log.info("İletişim dolduruldu ✅")
    except Exception as e:
        log.error(f"İletişim hatası: {e}")


def _onay_sec(sayfa):
    try:
        tum_cbs = sayfa.query_selector_all("input[type='checkbox']")
        son_onay = None
        for cb in tum_cbs:
            try:
                parent_metin = cb.evaluate(
                    "el => el.closest('div,tr,p,label,td')?.innerText || ''"
                )
                if any(x in parent_metin for x in [
                    "186", "SMS bedeli", "BolBol",
                    "İlk Yolcu", "T.C. Vatandaşı"
                ]):
                    continue
                if any(x in parent_metin for x in [
                    "onaylıyorum", "kabul ediyorum", "sorumlu"
                ]):
                    son_onay = cb
            except:
                continue

        if son_onay and not son_onay.is_checked():
            son_onay.click()
            log.info("Onay kutucuğu işaretlendi ✅")
        else:
            log.warning("Onay kutucuğu bulunamadı")
    except Exception as e:
        log.warning(f"Onay hatası: {e}")


def _ek_hizmetler_gec(sayfa):
    try:
        try:
            sayfa.wait_for_url("**/SellSsr**", timeout=15000)
        except:
            try:
                sayfa.wait_for_selector(
                    "a:has-text('Ödemeye Devam Et'), "
                    "button:has-text('Ödemeye Devam Et')",
                    timeout=10000
                )
            except:
                log.info("Ek hizmetler sayfası yok")
                return

        insan_gibi_bekle(2, 3)
        sayfa.click(
            "a:has-text('Ödemeye Devam Et'), "
            "button:has-text('Ödemeye Devam Et')"
        )
        log.info("Ek hizmetler geçildi ✅")
        insan_gibi_bekle(3, 5)
    except Exception as e:
        log.warning(f"Ek hizmetler hatası: {e}")


def pegasus_rezervasyon_bilgisi_al(sayfa) -> dict:
    try:
        insan_gibi_bekle(3, 5)
        sayfa.wait_for_load_state("networkidle", timeout=20000)
        hata_screenshot(sayfa, "pegasus_rezervasyon_sonuc")

        pnr = ""
        try:
            el = sayfa.query_selector("*:has-text('Rezervasyon (PNR) No')")
            if el:
                metin = el.inner_text()
                bul = re.search(r'(?:PNR|No)[.\s:]*([A-Z0-9]{5,6})', metin)
                if bul:
                    pnr = bul.group(1)
        except:
            pass

        if not pnr:
            try:
                el = sayfa.query_selector("[class*='pnr'], [id*='pnr']")
                if el:
                    bul = re.search(r'\b([A-Z0-9]{5,6})\b', el.inner_text())
                    if bul:
                        pnr = bul.group(1)
            except:
                pass

        log.info(f"PNR: {pnr or 'ALINAMADI'}")
        return {
            "pnr": pnr or "ALINAMADI",
            "mesaj": (
                f"✅ *Rezervasyon Oluşturuldu!*\n\n"
                f"PNR: `{pnr or 'ALINAMADI'}`\n\n"
                f"Lütfen Pegasus acente ekranından ödemeyi tamamlayın."
            )
        }
    except Exception as e:
        log.error(f"PNR hatası: {e}")
        return {
            "pnr": "ALINAMADI",
            "mesaj": (
                "⚠️ Rezervasyon tamamlandı ancak PNR alınamadı.\n"
                "Lütfen Pegasus sistemini kontrol edin."
            )
        }
