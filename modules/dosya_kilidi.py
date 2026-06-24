import os
import sys

KILIT_DOSYASI = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bot.lock")

def kilit_al():
    if os.path.exists(KILIT_DOSYASI):
        with open(KILIT_DOSYASI) as f:
            pid = f.read().strip()
        print(f"Bot zaten çalışıyor (PID: {pid}). Çıkılıyor.")
        sys.exit(1)
    os.makedirs(os.path.dirname(KILIT_DOSYASI), exist_ok=True)
    with open(KILIT_DOSYASI, "w") as f:
        f.write(str(os.getpid()))

def kilit_birak():
    if os.path.exists(KILIT_DOSYASI):
        os.remove(KILIT_DOSYASI)
