"""
Masara Turizm — Acentebot
Telegram botu + Playwright worker thread mimarisi
"""

import asyncio
import os
import queue
import re
import threading
import traceback
from typing import Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import config
from modules.logger import get_logger
from modules.dosya_kilidi import kilit_al, kilit_birak
from modules.komut_analiz import komut_analiz_et
from modules.ses_cozucu import ses_coz
from modules.kimlik_okuyucu import pdf_oku, resim_oku, kimlik_bilgisi_cikart
from modules.pegasus_modul import (
    pegasus_giris_baslat,
    pegasus_otp_gir,
    pegasus_ucus_sorgula,
    pegasus_paket_sec,
    pegasus_yolcu_doldur,
    pegasus_rezervasyon_bilgisi_al,
)

log = get_logger("main")
GECICI_DIR = os.path.join(os.path.dirname(__file__), "gecici")

# ─── Durum sabitleri ──────────────────────────────────────────────────────────
IDLE = "idle"
SMS_BEKLE = "sms_bekle"
UCUS_LISTE = "ucus_liste"
KIMLIK_BEKLE = "kimlik_bekle"
ONAY_BEKLE = "onay_bekle"

# ─── Playwright Worker Thread ─────────────────────────────────────────────────
_pw_queue: queue.Queue = queue.Queue()
_tarayici = None   # Browser nesnesi (pw_worker thread'de kullanılır)


def _pw_worker():
    """Tüm Playwright işlemlerini tek thread'de sırayla çalıştırır."""
    log.info("Playwright worker başladı ✅")
    while True:
        item = _pw_queue.get()
        if item is None:
            break
        fn, args, sonuc_queue = item
        try:
            deger = fn(*args)
            sonuc_queue.put(("ok", deger))
        except Exception as e:
            log.error(f"PW worker hata: {e}\n{traceback.format_exc()}")
            sonuc_queue.put(("hata", e))
    log.info("Playwright worker durdu.")


def pw_run(fn: Callable, *args, timeout=120):
    """Fonksiyonu PW queue'ya gönderir, sonucu bekler (sync)."""
    r: queue.Queue = queue.Queue()
    _pw_queue.put((fn, args, r))
    durum, deger = r.get(timeout=timeout)
    if durum == "hata":
        raise deger
    return deger


async def pw_async(fn: Callable, *args, timeout=120):
    """pw_run'ı asyncio event loop'tan çağırmak için async wrapper."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: pw_run(fn, *args, timeout=timeout))


# ─── Oturum yönetimi ─────────────────────────────────────────────────────────
_oturumlar: dict[int, dict] = {}


def ses(uid: int) -> dict:
    if uid not in _oturumlar:
        _oturumlar[uid] = {"durum": IDLE}
    return _oturumlar[uid]


def ses_sifirla(uid: int):
    _oturumlar[uid] = {"durum": IDLE}


# ─── Yetki ───────────────────────────────────────────────────────────────────
def yetkili(update: Update) -> bool:
    return update.effective_user.id == config.IZINLI_KULLANICI_ID


async def yetki_red(update: Update):
    await update.message.reply_text("Yetkisiz erişim.")


# ─── /start ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return await yetki_red(update)
    await update.message.reply_text(
        f"*{config.ISLETME_ADI}* botu hazır.\n\n"
        "Örnek: `15 Temmuz İstanbul Ankara`\n"
        "Sesli mesaj da gönderebilirsiniz.",
        parse_mode="Markdown",
    )


# ─── /iptal ──────────────────────────────────────────────────────────────────
async def cmd_iptal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return
    ses_sifirla(update.effective_user.id)
    await update.message.reply_text("İşlem iptal edildi.")


# ─── Metin mesajı ─────────────────────────────────────────────────────────────
async def metin_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return await yetki_red(update)

    uid = update.effective_user.id
    s = ses(uid)
    durum = s["durum"]
    metin = update.message.text.strip()

    if durum == SMS_BEKLE:
        await _sms_kodu_isle(update, s, metin)
    elif durum == UCUS_LISTE:
        await _ucus_secim_isle(update, s, metin)
    elif durum == KIMLIK_BEKLE:
        await _manuel_kimlik_isle(update, s, metin)
    elif durum == ONAY_BEKLE:
        await _onay_isle(update, s, metin)
    else:
        await _ucus_komutu_isle(update, s, metin)


async def _ucus_komutu_isle(update: Update, s: dict, metin: str):
    await update.message.reply_text("Komut analiz ediliyor...")
    komut = komut_analiz_et(metin)
    if not komut:
        await update.message.reply_text("Uçuş bilgisi anlaşılamadı. Tekrar dener misiniz?")
        return

    s["komut"] = komut
    nereden = komut.get("nereden", "?")
    nereye = komut.get("nereye", "?")
    tarih = komut.get("tarih") or komut.get("gidis_tarihi", "?")

    await update.message.reply_text(
        f"Arama: *{nereden} → {nereye}*\n"
        f"Tarih: {tarih}\n"
        f"Yolcu: {komut.get('yetiskin',1)}Y {komut.get('cocuk',0)}Ç {komut.get('bebek',0)}B\n\n"
        "Pegasus'a giriş yapılıyor...",
        parse_mode="Markdown",
    )

    def _giris():
        return pegasus_giris_baslat(_tarayici)

    konteks, sayfa = await pw_async(_giris)
    if not konteks or not sayfa:
        await update.message.reply_text("Pegasus giriş başlatılamadı. Tekrar deneyin.")
        ses_sifirla(update.effective_user.id)
        return

    s["pg_konteks"] = konteks
    s["pg_sayfa"] = sayfa
    s["durum"] = SMS_BEKLE
    await update.message.reply_text(
        "SMS telefonunuza gönderildi.\n\n"
        "Kodu yazın (örn: `1234`) veya SMS metnini yapıştırın:\n"
        "`A297TQ34 ile login için aktivasyon kodunuz fxop 'dir`",
        parse_mode="Markdown",
    )


async def _sms_kodu_isle(update: Update, s: dict, metin: str):
    await update.message.reply_text("Giriş yapılıyor...")

    konteks = s.get("pg_konteks")
    sayfa = s.get("pg_sayfa")

    def _otp():
        return pegasus_otp_gir(konteks, sayfa, metin)

    ana_sayfa = await pw_async(_otp)
    if not ana_sayfa:
        await update.message.reply_text("OTP hatası. /iptal yazıp tekrar deneyin.")
        ses_sifirla(update.effective_user.id)
        return

    s["pg_ana_sayfa"] = ana_sayfa
    await update.message.reply_text("Giriş başarılı ✅ Uçuşlar aranıyor...")

    def _ara():
        return pegasus_ucus_sorgula(ana_sayfa, s["komut"])

    ucuslar = await pw_async(_ara, timeout=180)
    s["ucuslar"] = ucuslar

    if not ucuslar:
        await update.message.reply_text("Uçuş bulunamadı. /iptal ile sıfırlayın.")
        ses_sifirla(update.effective_user.id)
        return

    s["durum"] = UCUS_LISTE

    satir = []
    for u in ucuslar[:8]:
        en_ucuz = u.get("en_ucuz_dahil", 0)
        satir.append(
            f"*{u['ucus_no']}* — {u.get('kalkis','')}→{u.get('varis','')} "
            f"({u.get('sure','')}) — {en_ucuz:.0f} TRY'den"
        )
    mesaj = "Bulunan uçuşlar:\n\n" + "\n".join(satir)
    mesaj += "\n\nUçuş numarası ve paket yazın (örn: `PC1234 Light`):"
    await update.message.reply_text(mesaj, parse_mode="Markdown")


async def _ucus_secim_isle(update: Update, s: dict, metin: str):
    """Kullanıcı 'PC1234 Light' gibi bir şey yazar."""
    parcalar = metin.strip().split()
    ucus_no = ""
    paket_adi = ""

    # PC ile başlayan uçuş numarası
    for p in parcalar:
        if re.match(r'^PC\d+', p, re.IGNORECASE):
            ucus_no = p.upper()
        elif p.lower() in ["light", "süper", "eko", "avantaj", "comfort", "flex"]:
            paket_adi = p

    # Paket adını birleştir (Süper Eko, Comfort Flex)
    if "süper" in metin.lower() or "eko" in metin.lower():
        paket_adi = "Süper Eko"
    elif "comfort" in metin.lower() or "flex" in metin.lower():
        paket_adi = "Comfort Flex"
    elif "avantaj" in metin.lower():
        paket_adi = "Avantaj"
    elif "light" in metin.lower():
        paket_adi = "Light"

    PAKET_IDX = {"Light": 0, "Süper Eko": 1, "Avantaj": 2, "Comfort Flex": 3}
    paket_index = PAKET_IDX.get(paket_adi, 0)

    if not ucus_no:
        await update.message.reply_text("Uçuş numarası anlaşılamadı. Örn: `PC1234 Light`", parse_mode="Markdown")
        return

    s["ucus_no"] = ucus_no
    s["paket_adi"] = paket_adi
    await update.message.reply_text(f"{ucus_no} — {paket_adi} paketi seçiliyor...")

    def _paket():
        return pegasus_paket_sec(s["pg_ana_sayfa"], ucus_no, paket_index)

    toplam = await pw_async(_paket, timeout=60)
    s["toplam_fiyat"] = toplam

    await update.message.reply_text(
        f"Paket seçildi ✅\nToplam: *{toplam:.2f} TRY*\n\n"
        "Yolcu kimliği gönderin:\n"
        "• TC kimlik fotoğrafı\n"
        "• PDF\n"
        "• Ya da manuel: `Ad Soyad TCno GG/AA/YYYY`",
        parse_mode="Markdown",
    )
    s["durum"] = KIMLIK_BEKLE


async def _manuel_kimlik_isle(update: Update, s: dict, metin: str):
    parcalar = metin.strip().split()
    if len(parcalar) < 4:
        await update.message.reply_text("Format: `Ad Soyad TCno GG/AA/YYYY`", parse_mode="Markdown")
        return

    ad, soyad, tc = parcalar[0], parcalar[1], parcalar[2]
    dogum_raw = parcalar[3]
    try:
        g, a, y = dogum_raw.replace("-", "/").split("/")
        dogum = f"{g.zfill(2)}.{a.zfill(2)}.{y}"
    except Exception:
        dogum = dogum_raw

    s["yolcular"] = [{"ad": ad, "soyad": soyad, "tc_no": tc, "dogum": dogum, "cinsiyet": "E", "tip": "yetiskin"}]
    await _onay_goster(update, s)


async def _onay_goster(update: Update, s: dict):
    y = s["yolcular"][0]
    await update.message.reply_text(
        f"Yolcu: *{y['ad']} {y['soyad']}*\n"
        f"TC: `{y.get('tc_no','')}`\n"
        f"Doğum: {y.get('dogum','')}\n\n"
        f"Toplam: *{s.get('toplam_fiyat', 0):.2f} TRY*\n\n"
        "Onaylıyor musunuz? (evet / hayır)",
        parse_mode="Markdown",
    )
    s["durum"] = ONAY_BEKLE


async def _onay_isle(update: Update, s: dict, metin: str):
    if metin.lower().strip() not in ("evet", "e", "yes", "tamam", "ok"):
        ses_sifirla(update.effective_user.id)
        await update.message.reply_text("İptal edildi. Yeni arama için komut gönderin.")
        return

    await update.message.reply_text("Yolcu bilgileri giriliyor...")

    def _yolcu():
        return pegasus_yolcu_doldur(s["pg_ana_sayfa"], s["yolcular"])

    basarili = await pw_async(_yolcu, timeout=120)
    if not basarili:
        await update.message.reply_text("Yolcu bilgisi hatası. /iptal ile sıfırlayın.")
        ses_sifirla(update.effective_user.id)
        return

    def _pnr():
        return pegasus_rezervasyon_bilgisi_al(s["pg_ana_sayfa"])

    sonuc = await pw_async(_pnr, timeout=60)
    await update.message.reply_text(sonuc["mesaj"], parse_mode="Markdown")
    ses_sifirla(update.effective_user.id)


# ─── Ses mesajı ───────────────────────────────────────────────────────────────
async def ses_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return await yetki_red(update)

    await update.message.reply_text("Ses mesajı işleniyor...")
    os.makedirs(GECICI_DIR, exist_ok=True)

    dosya = await update.message.voice.get_file()
    yol = os.path.join(GECICI_DIR, f"{update.message.voice.file_id}.ogg")
    await dosya.download_to_drive(yol)

    metin = ses_coz(yol)
    if not metin:
        await update.message.reply_text("Ses anlaşılamadı.")
        return

    await update.message.reply_text(f"Anlaşılan: _{metin}_", parse_mode="Markdown")
    uid = update.effective_user.id
    await _ucus_komutu_isle(update, ses(uid), metin)


# ─── Kimlik fotoğrafı / PDF ───────────────────────────────────────────────────
async def kimlik_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return await yetki_red(update)

    uid = update.effective_user.id
    s = ses(uid)
    if s["durum"] != KIMLIK_BEKLE:
        await update.message.reply_text("Şu an kimlik beklenmiyorum.")
        return

    os.makedirs(GECICI_DIR, exist_ok=True)
    metin = ""

    if update.message.photo:
        dosya = await update.message.photo[-1].get_file()
        yol = os.path.join(GECICI_DIR, f"{dosya.file_id}.jpg")
        await dosya.download_to_drive(yol)
        metin = resim_oku(yol)
    elif update.message.document:
        doc = update.message.document
        dosya = await doc.get_file()
        yol = os.path.join(GECICI_DIR, doc.file_name or f"{doc.file_id}.pdf")
        await dosya.download_to_drive(yol)
        metin = pdf_oku(yol) if yol.lower().endswith(".pdf") else resim_oku(yol)

    bilgi = kimlik_bilgisi_cikart(metin)
    if not bilgi:
        await update.message.reply_text(
            "Kimlik okunamadı. Manuel girin:\n`Ad Soyad TCno GG/AA/YYYY`",
            parse_mode="Markdown",
        )
        return

    s["yolcular"] = [{
        "ad": bilgi.get("ad", ""),
        "soyad": bilgi.get("soyad", ""),
        "tc_no": bilgi.get("tc", ""),
        "dogum": bilgi.get("dogum_tarihi", ""),
        "cinsiyet": "E",
        "tip": "yetiskin",
    }]
    await _onay_goster(update, s)


# ─── Hata yakalayıcı ─────────────────────────────────────────────────────────
async def hata_yakala(update, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Hata: {context.error}", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text("Bir hata oluştu. /iptal ile sıfırlayıp tekrar deneyin.")


# ─── Ana giriş ───────────────────────────────────────────────────────────────
def main():
    kilit_al()
    try:
        log.info("=" * 50)
        log.info("ACENTEBOT BAŞLIYOR")
        log.info("=" * 50)

        # Tarayıcıyı başlat (sync_playwright worker thread için)
        log.info("Playwright başlatılıyor...")
        from playwright.sync_api import sync_playwright

        _pw_start_done = threading.Event()
        _pw_error = []

        def _init_ve_worker():
            global _tarayici
            try:
                pw = sync_playwright().start()
                _tarayici = pw.chromium.launch(
                    headless=not config.TARAYICI_GORUNUR,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                )
                log.info("Yeni Chrome başlatıldı ✅")
            except Exception as e:
                _pw_error.append(e)
            finally:
                _pw_start_done.set()

            # Başlatma tamamsa worker döngüsüne gir
            if not _pw_error:
                log.info("Playwright worker hazır ✅")
                _pw_worker()
                if _tarayici:
                    try:
                        _tarayici.close()
                    except Exception:
                        pass

        t = threading.Thread(target=_init_ve_worker, daemon=True)
        t.start()
        _pw_start_done.wait(timeout=30)

        if _pw_error:
            raise _pw_error[0]

        log.info("Playwright hazır ✅")

        # Telegram botu
        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("iptal", cmd_iptal))
        app.add_handler(MessageHandler(filters.VOICE, ses_isle))
        app.add_handler(MessageHandler(filters.PHOTO, kimlik_isle))
        app.add_handler(MessageHandler(filters.Document.ALL, kimlik_isle))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, metin_isle))
        app.add_error_handler(hata_yakala)

        log.info("Bot hazır ✅")
        print("\n✅ BOT ÇALIŞIYOR — Telegram'dan /start yaz")
        print("Durmak: Ctrl+C\n")
        app.run_polling(drop_pending_updates=True)

    finally:
        _pw_queue.put(None)
        kilit_birak()


if __name__ == "__main__":
    main()
