import os
import tempfile
from openai import OpenAI
import config
from modules.logger import get_logger

log = get_logger("ses_cozucu")
_istemci = OpenAI(api_key=config.OPENAI_API_KEY)


def ses_coz(dosya_yolu: str) -> str | None:
    """Ses dosyasını Whisper ile metne çevirir."""
    try:
        with open(dosya_yolu, "rb") as f:
            transkript = _istemci.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="tr",
            )
        metin = transkript.text.strip()
        log.info(f"Ses çözüldü: {metin}")
        return metin
    except Exception as e:
        log.error(f"Ses çözme hatası: {e}")
        return None


def ogg_indir(dosya, gecici_dizin: str) -> str:
    """Telegram ses dosyasını gecici dizine indirir, yolunu döner."""
    os.makedirs(gecici_dizin, exist_ok=True)
    yol = os.path.join(gecici_dizin, f"{dosya.file_id}.ogg")
    dosya.download_to_drive(yol)
    return yol
