import json
import re
from groq import Groq
import config
from modules.logger import get_logger

log = get_logger("komut_analiz")
_istemci = Groq(api_key=config.GROQ_API_KEY)

SISTEM_PROMPTU = """Sen bir turizm acentesi asistanısın. Kullanıcının Türkçe uçuş komutunu JSON formatına çevir.

Havalimanı kodları:
- İstanbul (tümü) → IST, Sabiha Gökçen → SAW, Ankara → ESB/ANK, İzmir → ADB,
  Antalya → AYT, Bodrum → BJV, Trabzon → TZX, Samsun → SZF, Gaziantep → GZT,
  Dalaman → DLM, Adana → ADA, Konya → KYA, Erzurum → ERZ, Malatya → MLX

Çıktı (sadece JSON, başka hiçbir şey yok):
{
  "nereden": "IST",
  "nereye": "ESB",
  "gidis_tarihi": "2025-07-15",
  "donus_tarihi": null,
  "yetiskin": 1,
  "cocuk": 0,
  "bebek": 0,
  "tek_yon": true
}

donus_tarihi yoksa null yaz. Tarih formatı YYYY-MM-DD."""


def komut_analiz_et(metin: str) -> dict | None:
    try:
        yanit = _istemci.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": SISTEM_PROMPTU},
                {"role": "user", "content": metin},
            ],
            temperature=0,
            max_tokens=256,
        )
        ham = yanit.choices[0].message.content.strip()
        # JSON bloğunu çıkar
        eslesme = re.search(r"\{.*\}", ham, re.DOTALL)
        if eslesme:
            return json.loads(eslesme.group())
    except Exception as e:
        log.error(f"Komut analiz hatası: {e}")
    return None
