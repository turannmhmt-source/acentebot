import re
import os
import pdfplumber
import pytesseract
from PIL import Image
from modules.logger import get_logger

log = get_logger("kimlik_okuyucu")

# Tesseract yolu (Windows için)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def pdf_oku(yol: str) -> str:
    metin = ""
    try:
        with pdfplumber.open(yol) as pdf:
            for sayfa in pdf.pages:
                metin += sayfa.extract_text() or ""
    except Exception as e:
        log.error(f"PDF okuma hatası: {e}")
    return metin


def resim_oku(yol: str) -> str:
    try:
        img = Image.open(yol)
        return pytesseract.image_to_string(img, lang="tur")
    except Exception as e:
        log.error(f"Resim OCR hatası: {e}")
        return ""


def kimlik_bilgisi_cikart(metin: str) -> dict | None:
    """TC kimliğinden ad, soyad, TC no, doğum tarihi çıkarır."""
    tc = re.search(r"\b(\d{11})\b", metin)
    if not tc:
        return None

    satirlar = [s.strip() for s in metin.splitlines() if s.strip()]
    ad = soyad = dogum_tarihi = ""

    for i, satir in enumerate(satirlar):
        if "ADI" in satir.upper() and i + 1 < len(satirlar):
            ad = satirlar[i + 1]
        if "SOYADI" in satir.upper() and i + 1 < len(satirlar):
            soyad = satirlar[i + 1]
        tarih = re.search(r"\b(\d{2})[./](\d{2})[./](\d{4})\b", satir)
        if tarih:
            dogum_tarihi = f"{tarih.group(3)}-{tarih.group(2)}-{tarih.group(1)}"

    return {
        "tc": tc.group(1),
        "ad": ad,
        "soyad": soyad,
        "dogum_tarihi": dogum_tarihi,
    }
