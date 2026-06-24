"""
Masara Turizm — Acentebot
Telegram üzerinden Pegasus acentesi otomasyonu.
"""

import asyncio
import queue
import threading
import traceback
from typing import Callable

from telegram import Update, Voice, PhotoSize, Document
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    filters, ConversationHandler,
)

import config
from modules.logger import get_logger
from modules.dosya_kilidi import kilit_al, kilit_birak
from modules.komut_analiz import komut_analiz_et
from modules.ses_cozucu import ses_coz
from modules.pegasus_modul import (
    pegasus_giris_baslat, pegasus_otp_gir, pegasus_yeni_sayfa_bekle,
    pegasus_ucus_ara, pegasus_paket_sec, pegasus_yolcu_bilgisi_gir,
    pegasus_ek_hizmet_atla, pegasus_pnr_al,
)
from modules.tarayici import tarayici_baslat, tarayici_kapat
from modules.kimlik_okuyucu import pdf_oku, resim_oku, kimlik_bilgisi_cikart

import os

log = get_logger("main")
GECICI_DIR = os.path.join(os.path.dirname(__file__), "gecici")

# ─── Durum sabitleri ──────────────────────────────────────────────────────────
(
    IDLE,
    SMS_BEKLE,
    UCUS_LISTE,
    PAKET_BEKLE,
    KIMLIK_BEKLE,
    ONAY_BEKLE,
) = range(6)

# ─── Playwright Worker Thread ─────────────────────────────────────────────────
_pw_queue: queue.Queue = queue.Queue()
_pw_thread: threading.Thread = None
_konteks = None
_sayfa = None          # Giriş sayfası
_ana_sayfa = None      # Giriş sonrası açılan yeni pencere


def _pw_worker():
    """Tüm Playwright işlemlerini tek thread'de çalıştırır."""
    global _konteks, _sayfa, _ana_sayfa
    log.info("Playwright worker thread başladı.")
    while True:
        item = _pw_queue.get()
        if item is None:  # Kapatma sinyali
            break
        fn, args, result_queue = item
        try:
            sonuc = fn(*args)
            result_queue.put(("ok", sonuc))
        except Exception as e:
            log.error(f"PW worker hata: {e}\n{traceback.format_exc()}")
            result_queue.put(("hata", e))
    tarayici_kapat()
    log.info("Playwright worker thread sonlandı.")


def pw_run(fn: Callable, *args, timeout=120):
    """İşi PW queue'ya gönderir, sonucu bekler (sync)."""
    r = queue.Queue()
    _pw_queue.put((fn, args, r))
    durum, deger = r.get(timeout=timeout)
    if durum == "hata":
        raise deger
    return deger


async def pw_async(fn: Callable, *args, timeout=120):
    """pw_run'ı asyncio event loop'tan çağırmak için wrapper."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: pw_run(fn, *args, timeout=timeout))


def _pw_baslat():
    global _pw_thread, _konteks, _sayfa
    _konteks, _sayfa = tarayici_baslat()
    _pw_thread = threading.Thread(target=_pw_worker, daemon=True)
    _pw_thread.start()


# ─── Oturum verisi ────────────────────────────────────────────────────────────
# Her kullanıcı için bağımsız oturum verisi (user_id → dict)
_oturum: dict[int, dict] = {}


def oturum(user_id: int) -> dict:
    if user_id not in _oturum:
        _oturum[user_id] = {}
    return _oturum[user_id]


# ─── Yetki kontrolü ──────────────────────────────────────────────────────────
def yetkili(update: Update) -> bool:
    return update.effective_user.id == config.IZINLI_KULLANICI_ID


async def yetki_red(update: Update):
    await update.message.reply_text("Bu botu kullanma yetkiniz yok.")


# ─── /start komutu ───────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return await yetki_red(update)
    await update.message.reply_text(
        f"Merhaba! *{config.ISLETME_ADI}* botu hazır.\n\n"
        "Uçuş aramak için örnek:\n"
        "  `15 Temmuz İstanbul Ankara 1 kişi`\n"
        "Veya sesli mesaj gönderebilirsiniz.",
        parse_mode="Markdown",
    )
    return IDLE


# ─── Metin mesajı işleyici ────────────────────────────────────────────────────
async def metin_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return await yetki_red(update)

    uid = update.effective_user.id
    ses = oturum(uid)
    metin = update.message.text.strip()
    durum = ses.get("durum", IDLE)

    # SMS kodu bekleniyor
    if durum == SMS_BEKLE:
        return await sms_kodu_isle(update, context, metin)

    # Uçuş listesi gösterildikten sonra seçim
    if durum == UCUS_LISTE:
        return await ucus_secim_isle(update, context, metin)

    # Paket seçimi
    if durum == PAKET_BEKLE:
        return await paket_secim_isle(update, context, metin)

    # Onay bekleniyor
    if durum == ONAY_BEKLE:
        return await onay_isle(update, context, metin)

    # Normal mesaj → uçuş komutu analizi
    return await ucus_komutu_isle(update, context, metin)


async def ucus_komutu_isle(update: Update, context: ContextTypes.DEFAULT_TYPE, metin: str):
    uid = update.effective_user.id
    ses = oturum(uid)

    await update.message.reply_text("Komut analiz ediliyor...")
    arama = komut_analiz_et(metin)
    if not arama:
        await update.message.reply_text("Uçuş bilgisi anlaşılamadı. Tekrar dener misiniz?")
        return IDLE

    ses["arama"] = arama
    await update.message.reply_text(
        f"Arama: {arama['nereden']} → {arama['nereye']}\n"
        f"Tarih: {arama['gidis_tarihi']}\n"
        f"Yolcu: {arama['yetiskin']}Y {arama['cocuk']}Ç {arama['bebek']}B\n\n"
        "Pegasus'a giriş yapılıyor..."
    )

    # PW worker üzerinden giriş başlat
    def _giris():
        return pegasus_giris_baslat(_konteks, _sayfa)

    sonuc = await pw_async(_giris)
    if sonuc["durum"] == "hata":
        await update.message.reply_text(f"Giriş hatası: {sonuc['mesaj']}")
        return IDLE

    ses["durum"] = SMS_BEKLE
    await update.message.reply_text("SMS kodu telefonunuza gönderildi. Lütfen kodu yazın:")
    return SMS_BEKLE


async def sms_kodu_isle(update: Update, context: ContextTypes.DEFAULT_TYPE, kod: str):
    uid = update.effective_user.id
    ses = oturum(uid)

    await update.message.reply_text("OTP giriliyor...")

    def _otp():
        return pegasus_otp_gir(_sayfa, kod)

    sonuc = await pw_async(_otp)
    if sonuc["durum"] == "hata":
        await update.message.reply_text(f"OTP hatası: {sonuc['mesaj']}")
        ses["durum"] = IDLE
        return IDLE

    # Yeni pencereyi yakala
    def _yeni_sayfa():
        global _ana_sayfa
        _ana_sayfa = pegasus_yeni_sayfa_bekle(_konteks)
        return _ana_sayfa is not None

    basarili = await pw_async(_yeni_sayfa)
    if not basarili:
        await update.message.reply_text("Giriş sonrası sayfa açılamadı. Tekrar deneyin.")
        ses["durum"] = IDLE
        return IDLE

    await update.message.reply_text("Giriş başarılı! Uçuşlar aranıyor...")

    def _ara():
        return pegasus_ucus_ara(_ana_sayfa, ses["arama"])

    ucuslar = await pw_async(_ara)
    ses["ucuslar"] = ucuslar

    if not ucuslar:
        await update.message.reply_text("Uçuş bulunamadı.")
        ses["durum"] = IDLE
        return IDLE

    # Uçuş listesini gönder
    mesaj = "Bulunan uçuşlar:\n\n"
    for u in ucuslar[:10]:
        mesaj += f"*{u['index']}.* {u['ham_metin'][:120]}\n\n"
    mesaj += "Uçuş numarasını yazın (örn: `1`):"
    await update.message.reply_text(mesaj, parse_mode="Markdown")

    ses["durum"] = UCUS_LISTE
    return UCUS_LISTE


async def ucus_secim_isle(update: Update, context: ContextTypes.DEFAULT_TYPE, metin: str):
    uid = update.effective_user.id
    ses = oturum(uid)

    try:
        ucus_no = int(metin.strip())
    except ValueError:
        await update.message.reply_text("Geçerli bir numara girin.")
        return UCUS_LISTE

    ses["ucus_no"] = ucus_no
    await update.message.reply_text(
        "Hangi paketi seçmek istiyorsunuz?\n"
        "1. Light\n2. Süper Eko\n3. Avantaj\n4. Comfort Flex\n\n"
        "Paket adını yazın (örn: `Light`):"
    )
    ses["durum"] = PAKET_BEKLE
    return PAKET_BEKLE


async def paket_secim_isle(update: Update, context: ContextTypes.DEFAULT_TYPE, metin: str):
    uid = update.effective_user.id
    ses = oturum(uid)

    paket = metin.strip()

    def _paket():
        return pegasus_paket_sec(_ana_sayfa, ses["ucus_no"], paket)

    sonuc = await pw_async(_paket)
    if sonuc["durum"] == "hata":
        await update.message.reply_text(f"Paket seçim hatası: {sonuc['mesaj']}")
        return PAKET_BEKLE

    ses["paket"] = paket
    await update.message.reply_text(
        f"'{paket}' paketi seçildi.\n\n"
        "Yolcu kimlik bilgilerini gönderin:\n"
        "• Fotoğraf (TC kimlik)\n"
        "• PDF\n"
        "• Veya manuel: `Ad Soyad TC DoğumTarihi`"
    )
    ses["durum"] = KIMLIK_BEKLE
    return KIMLIK_BEKLE


async def onay_isle(update: Update, context: ContextTypes.DEFAULT_TYPE, metin: str):
    uid = update.effective_user.id
    ses = oturum(uid)

    if metin.lower() not in ("evet", "e", "yes", "tamam"):
        await update.message.reply_text("İptal edildi. Yeni arama için mesaj gönderin.")
        ses["durum"] = IDLE
        return IDLE

    await update.message.reply_text("Yolcu bilgileri giriliyor...")

    def _yolcu():
        return pegasus_yolcu_bilgisi_gir(_ana_sayfa, ses["yolcular"])

    sonuc = await pw_async(_yolcu)
    if sonuc["durum"] == "hata":
        await update.message.reply_text(f"Yolcu bilgisi hatası: {sonuc['mesaj']}")
        ses["durum"] = IDLE
        return IDLE

    def _ek():
        return pegasus_ek_hizmet_atla(_ana_sayfa)

    await pw_async(_ek)

    def _pnr():
        return pegasus_pnr_al(_ana_sayfa)

    pnr_sonuc = await pw_async(_pnr)
    await update.message.reply_text(
        f"Rezervasyon oluşturuldu!\n"
        f"PNR: *{pnr_sonuc.get('pnr', '?')}*\n"
        f"URL: {pnr_sonuc.get('url', '')}",
        parse_mode="Markdown",
    )
    ses["durum"] = IDLE
    return IDLE


# ─── Ses mesajı işleyici ──────────────────────────────────────────────────────
async def ses_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return await yetki_red(update)

    await update.message.reply_text("Ses mesajı işleniyor...")
    os.makedirs(GECICI_DIR, exist_ok=True)

    ses_dosyasi = await update.message.voice.get_file()
    yol = os.path.join(GECICI_DIR, f"{update.message.voice.file_id}.ogg")
    await ses_dosyasi.download_to_drive(yol)

    metin = ses_coz(yol)
    if not metin:
        await update.message.reply_text("Ses anlaşılamadı, tekrar dener misiniz?")
        return IDLE

    await update.message.reply_text(f"Anlaşılan: _{metin}_", parse_mode="Markdown")
    return await ucus_komutu_isle(update, context, metin)


# ─── Kimlik fotoğrafı / PDF işleyici ─────────────────────────────────────────
async def kimlik_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return await yetki_red(update)

    uid = update.effective_user.id
    ses = oturum(uid)

    if ses.get("durum") != KIMLIK_BEKLE:
        await update.message.reply_text("Şu an kimlik beklenmiyorum.")
        return ses.get("durum", IDLE)

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
        if yol.lower().endswith(".pdf"):
            metin = pdf_oku(yol)
        else:
            metin = resim_oku(yol)

    bilgi = kimlik_bilgisi_cikart(metin)
    if not bilgi:
        await update.message.reply_text(
            "Kimlik okunamadı. Manuel giriş için:\n`Ad Soyad TCno GG/AA/YYYY`"
        )
        return KIMLIK_BEKLE

    ses["yolcular"] = [{
        **bilgi,
        "cinsiyet": "BAY",
        "tip": "yetiskin",
    }]

    await update.message.reply_text(
        f"Kimlik okundu:\n"
        f"Ad: *{bilgi['ad']} {bilgi['soyad']}*\n"
        f"TC: `{bilgi['tc']}`\n"
        f"Doğum: {bilgi['dogum_tarihi']}\n\n"
        "Onaylıyor musunuz? (evet/hayır)",
        parse_mode="Markdown",
    )
    ses["durum"] = ONAY_BEKLE
    return ONAY_BEKLE


# ─── Manuel kimlik girişi ─────────────────────────────────────────────────────
async def manuel_kimlik_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kimlik bekleme durumunda gelen metin mesajını kimlik olarak işler."""
    if not yetkili(update):
        return await yetki_red(update)

    uid = update.effective_user.id
    ses = oturum(uid)

    if ses.get("durum") != KIMLIK_BEKLE:
        return await metin_isle(update, context)

    parcalar = update.message.text.strip().split()
    if len(parcalar) < 4:
        await update.message.reply_text("Format: `Ad Soyad TCno GG/AA/YYYY`")
        return KIMLIK_BEKLE

    ad, soyad, tc = parcalar[0], parcalar[1], parcalar[2]
    dogum = parcalar[3]  # GG/AA/YYYY → YYYY-MM-DD
    try:
        g, a, y = dogum.split("/")
        dogum_iso = f"{y}-{a}-{g}"
    except Exception:
        dogum_iso = dogum

    ses["yolcular"] = [{
        "ad": ad, "soyad": soyad, "tc": tc, "dogum_tarihi": dogum_iso,
        "cinsiyet": "BAY", "tip": "yetiskin",
    }]

    await update.message.reply_text(
        f"Kimlik:\n*{ad} {soyad}* — TC: `{tc}`\n\nOnaylıyor musunuz? (evet/hayır)",
        parse_mode="Markdown",
    )
    ses["durum"] = ONAY_BEKLE
    return ONAY_BEKLE


# ─── /iptal komutu ───────────────────────────────────────────────────────────
async def iptal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not yetkili(update):
        return
    uid = update.effective_user.id
    _oturum[uid] = {"durum": IDLE}
    await update.message.reply_text("İşlem iptal edildi.")
    return IDLE


# ─── Hata yakalayıcı ─────────────────────────────────────────────────────────
async def hata_yakala(update, context: ContextTypes.DEFAULT_TYPE):
    log.error(f"Hata: {context.error}", exc_info=context.error)
    if update and update.message:
        await update.message.reply_text("Bir hata oluştu, lütfen tekrar deneyin.")


# ─── Ana giriş noktası ───────────────────────────────────────────────────────
def main():
    kilit_al()
    try:
        # Playwright worker başlat
        global _konteks, _sayfa
        _konteks, _sayfa = tarayici_baslat()
        _pw_thread = threading.Thread(target=_pw_worker, daemon=True)
        _pw_thread.start()

        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

        # Mesaj yönlendirme
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("iptal", iptal))
        app.add_handler(MessageHandler(filters.VOICE, ses_isle))
        app.add_handler(MessageHandler(filters.PHOTO, kimlik_isle))
        app.add_handler(MessageHandler(filters.Document.ALL, kimlik_isle))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, metin_isle))
        app.add_error_handler(hata_yakala)

        log.info("Bot başlatıldı, dinleniyor...")
        app.run_polling(drop_pending_updates=True)

    finally:
        _pw_queue.put(None)  # Worker'ı durdur
        kilit_birak()


if __name__ == "__main__":
    main()
