from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from modules.logger import get_logger
import config

log = get_logger("tarayici")

_playwright = None
_browser: Browser = None
_konteks: BrowserContext = None


def tarayici_baslat() -> tuple[BrowserContext, Page]:
    global _playwright, _browser, _konteks
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=not config.TARAYICI_GORUNUR,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    _konteks = _browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
    )
    sayfa = _konteks.new_page()
    log.info("Tarayıcı başlatıldı.")
    return _konteks, sayfa


def tarayici_kapat():
    global _playwright, _browser, _konteks
    try:
        if _konteks:
            _konteks.close()
        if _browser:
            _browser.close()
        if _playwright:
            _playwright.stop()
    except Exception as e:
        log.warning(f"Tarayıcı kapatılırken hata: {e}")
    finally:
        _playwright = _browser = _konteks = None
    log.info("Tarayıcı kapatıldı.")
