"""Browser management for LoiLoNote CLI."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

logger = logging.getLogger("loilonote.browser")

STATE_DIR = Path(os.path.expanduser("~")) / ".loilonote"
STATE_FILE = STATE_DIR / "state.json"
BASE_URL = "https://loilonote.app"

REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

INIT_SCRIPT = """
(() => {
  let debounceTimer = null;
  const clean = () => {
    document.querySelectorAll('#continue, .tutorialContainer, .tutorialDialog').forEach(e => e.remove());
    document.querySelectorAll('[inert]').forEach(e => e.removeAttribute('inert'));
  };
  const debouncedClean = () => {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(clean, 150);
  };
  clean();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', clean, { once: true });
  }
  // Observe subtree but with debounced clean to reduce overhead
  if (document.body) {
    const obs = new MutationObserver(debouncedClean);
    obs.observe(document.body, { childList: true, subtree: true });
  }
})();
"""


def ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def has_state() -> bool:
    return STATE_FILE.exists()


def load_state() -> Optional[dict]:
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load state: %s", e)
        return None


def save_state(state: dict):
    ensure_state_dir()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def make_browser(headless: bool = True, slow_mo: int = 0):
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )
    return pw, browser


def make_context(browser, headless: bool = True, block_resources: bool = True):
    state = load_state()
    kwargs = {
        "viewport": {"width": 1400, "height": 900},
        "user_agent": REAL_UA,
        "locale": "ja-JP",
    }
    if state:
        kwargs["storage_state"] = state
    ctx = browser.new_context(**kwargs)
    ctx.add_init_script(INIT_SCRIPT)
    if block_resources:
        def _route_handler(route):
            if route.request.resource_type in {"image", "media"}:
                route.abort()
            else:
                route.continue_()
        ctx.route("**/*", _route_handler)
    return ctx


def new_page(headless: bool = True, slow_mo: int = 0, block_resources: bool = True) -> Tuple:
    pw, browser = make_browser(headless=headless, slow_mo=slow_mo)
    ctx = make_context(browser, headless=headless, block_resources=block_resources)
    page = ctx.new_page()
    return pw, browser, ctx, page


def close_all(pw, browser, ctx=None, page=None):
    for obj in (page, ctx, browser):
        if obj is None:
            continue
        try:
            obj.close()
        except Exception as e:
            logger.debug("Error closing %s: %s", type(obj).__name__, e)
    try:
        if pw is not None:
            pw.stop()
    except Exception as e:
        logger.debug("Error stopping playwright: %s", e)


def retry(func, retries: int = 3, delay: float = 1.0, exceptions=(Exception,)):
    """Retry a function with exponential backoff."""
    last_exc = None
    for attempt in range(retries):
        try:
            return func()
        except exceptions as e:
            last_exc = e
            if attempt < retries - 1:
                wait = delay * (2 ** attempt)
                logger.warning("Attempt %d failed: %s. Retrying in %.1fs...", attempt + 1, e, wait)
                time.sleep(wait)
    raise last_exc