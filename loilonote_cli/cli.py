import io
import json
import os
import re
import signal
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import click
from playwright.sync_api import TimeoutError as PWTimeout

import logging
from . import browser, selectors
from .browser import retry

logger = logging.getLogger("loilonote.cli")
__version__ = "0.4.0"

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

CACHE_DIR = Path(os.path.expanduser("~")) / ".loilonote"
COURSES_CACHE = CACHE_DIR / "courses.json"
OUT_DIR = CACHE_DIR / "out"


def out_dir():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR


def emit(ctx, obj, human=None):
    """Print result. Default JSON (AI-friendly). --human for readable."""
    if ctx.obj.get("human"):
        if human:
            click.echo(human)
        else:
            click.echo(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        click.echo(json.dumps(obj, ensure_ascii=False))


def fail(ctx, msg, code=1):
    emit(ctx, {"ok": False, "error": msg})
    sys.exit(code)


def goto(page, url, wait=10000, timeout=60000, wait_selector=None):
    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    if wait_selector:
        try:
            page.locator(wait_selector).first.wait_for(state="visible", timeout=wait)
        except PWTimeout:
            pass
    time.sleep(0.1)


def maybe_dump(ctx, page, name):
    d = out_dir()
    ts = int(time.time())
    html_path = d / f"{name}_{ts}.html"
    png_path = d / f"{name}_{ts}.png"
    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(png_path), full_page=True)
    return str(html_path), str(png_path)


def maybe_dump(ctx, page, name):
    """Dump page only if --dump flag is set. Returns (None, None) otherwise."""
    if ctx.obj.get("dump"):
        return maybe_dump(ctx, page, name)
    return None, None


def close(ctx_obj, pw, br, ctxb, page):
    if not ctx_obj.get("headed"):
        browser.close_all(pw, br, ctxb, page)


def load_courses():
    if COURSES_CACHE.exists():
        try:
            return json.loads(COURSES_CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_courses(courses):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    COURSES_CACHE.write_text(json.dumps(courses, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- auth token helpers ----------
AUTH_TOKEN_FILE = CACHE_DIR / "auth_token.json"


def load_auth_token():
    if AUTH_TOKEN_FILE.exists():
        try:
            data = json.loads(AUTH_TOKEN_FILE.read_text(encoding="utf-8"))
            return data.get("auth_token")
        except Exception:
            return None
    return None


def save_auth_token(token):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_TOKEN_FILE.write_text(json.dumps({"auth_token": token}, ensure_ascii=False), encoding="utf-8")


def get_auth_token(ctx):
    """Get auth_token, using cache or intercepting from browser."""
    token = load_auth_token()
    if token:
        return token
    if not browser.has_state():
        return None
    pw, br, ctxb, page = browser.new_page(headless=True, slow_mo=0, block_resources=False)
    captured = [None]

    def on_request(request):
        url = request.url
        if "auth_token=" in url and captured[0] is None:
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            if "auth_token" in qs:
                captured[0] = qs["auth_token"][0]

    page.on("request", on_request)
    goto(page, browser.BASE_URL, wait=5000, timeout=ctx.obj["timeout"])
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PWTimeout:
        pass
    time.sleep(1)
    browser.close_all(pw, br, ctxb, page)
    if captured[0]:
        save_auth_token(captured[0])
    return captured[0]


# Adapted from samcct-bit/loilonote-cli (MIT License)
# https://github.com/samcct-bit/loilonote-cli
# Original: packages/core/src/client.ts (getNote)
def fetch_note_zip(note_id, token):
    """Download note ZIP from API. Returns bytes."""
    url = f"https://n.loilo.tv/api/notes/{note_id}?auth_token={urllib.parse.quote(token)}"
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=60)
    return resp.read()


# Adapted from samcct-bit/loilonote-cli (MIT License)
# https://github.com/samcct-bit/loilonote-cli
# Original: packages/core/src/client.ts (getParsedNote, extractText, extractAssets)
def parse_note_zip(data):
    """Parse note ZIP bytes into structured dict."""
    zf = zipfile.ZipFile(io.BytesIO(data))
    namelist = zf.namelist()

    version = None
    header = None
    body = None

    if "version" in namelist:
        try:
            version = zf.read("version").decode("utf-8").strip()
        except Exception:
            pass
    if "header" in namelist:
        try:
            header = json.loads(zf.read("header").decode("utf-8"))
        except Exception:
            pass
    if "body" in namelist:
        try:
            body = json.loads(zf.read("body").decode("utf-8"))
        except Exception:
            pass

    frames = []
    if body and isinstance(body, dict):
        frames = body.get("data", {}).get("frames", [])

    frame_types = list(dict.fromkeys(f.get("type") for f in frames if f.get("type")))

    # Extract text
    texts = []
    for frame in frames:
        gadgets = frame.get("gadgets", {})
        if not isinstance(gadgets, dict):
            continue
        for key in gadgets:
            gadget = gadgets[key]
            if not isinstance(gadget, dict):
                continue
            if gadget.get("text") and isinstance(gadget["text"], str):
                texts.append(gadget["text"])
            if gadget.get("html") and isinstance(gadget["html"], str):
                texts.append(re.sub(r"<[^>]+>", "", gadget["html"]))

    # Extract assets (remote_id references)
    assets = []
    for frame in frames:
        gadgets = frame.get("gadgets", {})
        if not isinstance(gadgets, dict):
            continue
        drawn = gadgets.get("drawn")
        if isinstance(drawn, dict):
            asset = drawn.get("asset", {})
            if isinstance(asset, dict) and asset.get("remote_id"):
                assets.append({
                    "frame_id": frame.get("id"),
                    "frame_type": frame.get("type"),
                    "remote_id": asset["remote_id"],
                })
        bgm = gadgets.get("bgm")
        if isinstance(bgm, dict):
            img = bgm.get("image", {})
            if isinstance(img, dict) and img.get("remote_id"):
                assets.append({
                    "frame_id": frame.get("id"),
                    "frame_type": f"{frame.get('type')}-bg",
                    "remote_id": img["remote_id"],
                })

    return {
        "version": version,
        "header": header,
        "body": body,
        "zip_files": namelist,
        "frame_count": len(frames),
        "frame_types": frame_types,
        "texts": texts,
        "assets": assets,
    }


@click.group()
@click.option("--headed", is_flag=True, help="Show browser window.")
@click.option("--slow", type=int, default=0, help="Slow motion ms.")
@click.option("--human", is_flag=True, help="Human-readable output instead of JSON.")
@click.option("--timeout", type=int, default=60000, help="Navigation timeout ms.")
@click.option("--dump", is_flag=True, help="Save page HTML + screenshot after commands (default: off).")
@click.version_option(__version__, prog_name="loilonote")
@click.pass_context
def cli(ctx, headed, slow, human, timeout, dump):
    """LoiLoNote CLI (AI-first). Default output is JSON."""
    ctx.ensure_object(dict)
    ctx.obj["headed"] = headed
    ctx.obj["slow"] = slow
    ctx.obj["human"] = human
    ctx.obj["timeout"] = timeout
    ctx.obj["dump"] = dump
    ctx.obj["block_resources"] = False  # resource blocking disabled by default (can break SPA rendering)

    def _handle_sigint(sig, frame):
        logger.info("Interrupted by user")
        sys.exit(130)

    signal.signal(signal.SIGINT, _handle_sigint)

# ---------- status ----------
@cli.command()
@click.pass_context
def status(ctx):
    """Check session validity. Returns JSON with usable:true/false."""
    if not browser.has_state():
        emit(ctx, {"ok": True, "session": False, "usable": False})
        sys.exit(2)
    pw, br, ctxb, page = browser.new_page(headless=True, slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, browser.BASE_URL, wait=5000, timeout=ctx.obj["timeout"])
    usable = "/login" not in (page.url or "")
    res = {"ok": True, "session": True, "usable": usable, "url": page.url}
    browser.close_all(pw, br, ctxb, page)
    emit(ctx, res)
    sys.exit(0 if usable else 2)


# ---------- doctor ----------
@cli.command()
@click.pass_context
def doctor(ctx):
    """Check dependencies and environment."""
    res = {"ok": True}
    try:
        import click as _c
        res["click"] = _c.__version__
    except Exception as e:
        res["click"] = f"MISSING: {e}"; res["ok"] = False
    try:
        import playwright
        res["playwright"] = getattr(playwright, "__version__", "installed")
    except Exception as e:
        res["playwright"] = f"MISSING: {e}"; res["ok"] = False
    chromium_dir = Path(os.path.expanduser("~")) / "AppData" / "Local" / "ms-playwright"
    res["chromium_installed"] = chromium_dir.exists()
    if not chromium_dir.exists():
        res["ok"] = False
    res["session_exists"] = browser.has_state()
    emit(ctx, res)
    sys.exit(0 if res["ok"] else 1)


# ---------- login ----------
@cli.command()
@click.pass_context
def login(ctx):
    """Interactive login. Only command that requires human input."""
    pw, br, ctxb, page = browser.new_page(headless=False, slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, browser.BASE_URL, wait=5000, timeout=ctx.obj["timeout"])
    click.echo("Log in manually, then press Enter...")
    input()
    browser.save_state(ctxb.storage_state())
    browser.close_all(pw, br, ctxb, page)
    emit(ctx, {"ok": True, "saved": str(browser.STATE_FILE)})


# ---------- courses ----------
@cli.command()
@click.option("--refresh", is_flag=True, help="Re-discover course URLs.")
@click.option("--limit", type=int, default=0, help="Max courses to resolve.")
@click.pass_context
def courses(ctx, refresh, limit):
    """List courses with URLs. Cached after first run."""
    if not browser.has_state():
        fail(ctx, "no session; run login first", 2)
    cached = load_courses()
    if cached and not refresh:
        if limit:
            cached = cached[:limit]
        emit(ctx, {"ok": True, "count": len(cached), "courses": cached, "cached": True})
        return
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, browser.BASE_URL, wait=10000, timeout=ctx.obj["timeout"], wait_selector=selectors.COURSE_ITEM)
    items = page.query_selector_all(selectors.COURSE_ITEM)
    labels = []
    seen = set()
    for c in items:
        try:
            lab = c.get_attribute("aria-label") or c.inner_text().strip()
        except Exception:
            lab = None
        if lab and lab not in seen:
            seen.add(lab); labels.append(lab)
    if limit:
        labels = labels[:limit]
    results = []
    for lab in labels:
        try:
            goto(page, browser.BASE_URL, wait=10000, timeout=ctx.obj["timeout"], wait_selector=selectors.COURSE_ITEM)
            time.sleep(0.3)
            el = None
            for cc in page.query_selector_all(selectors.COURSE_ITEM):
                if (cc.get_attribute("aria-label") or "").strip() == lab.strip():
                    el = cc; break
            if not el:
                results.append({"name": lab, "url": None, "error": "not found"})
                continue
            el.scroll_into_view_if_needed()
            time.sleep(0.5)
            el.click()
            for _ in range(30):
                time.sleep(0.5)
                if "/_/" in page.url and "tab=" in page.url and page.url != browser.BASE_URL:
                    break
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PWTimeout:
                pass
            results.append({"name": lab, "url": page.url})
        except Exception as e:
            results.append({"name": lab, "url": None, "error": str(e)})
    save_courses(results)
    emit(ctx, {"ok": True, "count": len(results), "courses": results, "cached": False})
    close(ctx.obj, pw, br, ctxb, page)


# ---------- notes ----------
@cli.command()
@click.argument("url")
@click.pass_context
def notes(ctx, url):
    """List notes in a course (structured JSON)."""
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, url, wait=10000, timeout=ctx.obj["timeout"], wait_selector=selectors.NOTE_CARD)
    cards = page.query_selector_all(selectors.NOTE_CARD)
    result = []
    for card in cards:
        try:
            t = card.query_selector(selectors.NOTE_TITLE)
            title = t.inner_text().strip() if t else ""
        except Exception:
            title = ""
        try:
            d = card.query_selector(selectors.NOTE_DATE)
            date = d.inner_text().strip() if d else ""
        except Exception:
            date = ""
        nid = None
        try:
            labelled = card.get_attribute("aria-labelledby") or ""
            if labelled.startswith("notes-"):
                nid = labelled.split("-")[1]
        except Exception:
            pass
        result.append({"id": nid, "title": title, "updated": date})
    emit(ctx, {"ok": True, "url": page.url, "count": len(result), "notes": result})
    close(ctx.obj, pw, br, ctxb, page)


@cli.command()
@click.argument("url")
@click.pass_context
def note(ctx, url):
    """Get text content of a page/note (truncated 8000 chars)."""
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, url, wait=8000, timeout=ctx.obj["timeout"])
    text = page.inner_text("body")
    html_path, png_path = maybe_dump(ctx, page, "note")
    emit(ctx, {"ok": True, "url": page.url, "text": text[:8000], "length": len(text),
               "dump_html": html_path, "dump_png": png_path})
    close(ctx.obj, pw, br, ctxb, page)


# ---------- note-text (extract text from note by ID) ----------
@cli.command("note-text")
@click.argument("note_id")
@click.pass_context
def note_text(ctx, note_id):
    """Extract all text content from a note by its ID (downloads and parses the note ZIP)."""
    if not browser.has_state():
        fail(ctx, "no session; run login first", 2)
    token = get_auth_token(ctx)
    if not token:
        fail(ctx, "could not obtain auth_token; try running `loilonote login` first", 2)
    try:
        data = fetch_note_zip(note_id, token)
    except Exception as e:
        fail(ctx, f"failed to download note {note_id}: {e}")
    parsed = parse_note_zip(data)
    text = "\n---\n".join(parsed["texts"])
    emit(ctx, {
        "ok": True,
        "note_id": note_id,
        "text": text,
        "length": len(text),
        "text_count": len(parsed["texts"]),
        "frame_count": parsed["frame_count"],
    })


# ---------- note-inspect (parse note structure) ----------
@cli.command("note-inspect")
@click.argument("note_id")
@click.pass_context
def note_inspect(ctx, note_id):
    """Download and parse a note, showing its internal structure (cards, gadgets, frames)."""
    if not browser.has_state():
        fail(ctx, "no session; run login first", 2)
    token = get_auth_token(ctx)
    if not token:
        fail(ctx, "could not obtain auth_token; try running `loilonote login` first", 2)
    try:
        data = fetch_note_zip(note_id, token)
    except Exception as e:
        fail(ctx, f"failed to download note {note_id}: {e}")
    parsed = parse_note_zip(data)
    emit(ctx, {
        "ok": True,
        "note_id": note_id,
        "version": parsed["version"],
        "header": parsed["header"],
        "frame_count": parsed["frame_count"],
        "frame_types": parsed["frame_types"],
        "text_count": len(parsed["texts"]),
        "texts": parsed["texts"][:20],
        "asset_count": len(parsed["assets"]),
        "assets": parsed["assets"],
        "zip_files": parsed["zip_files"],
    })


# ---------- note-download (download note ZIP) ----------
@cli.command("note-download")
@click.argument("note_id")
@click.option("--output", "-o", default="", help="Output file path (default: ~/.loilonote/backups/note_{id}_{timestamp}.zip)")
@click.pass_context
def note_download(ctx, note_id, output):
    """Download a note as a ZIP file."""
    if not browser.has_state():
        fail(ctx, "no session; run login first", 2)
    token = get_auth_token(ctx)
    if not token:
        fail(ctx, "could not obtain auth_token; try running `loilonote login` first", 2)
    try:
        data = fetch_note_zip(note_id, token)
    except Exception as e:
        fail(ctx, f"failed to download note {note_id}: {e}")
    if output:
        out_path = Path(output)
    else:
        backup_dir = CACHE_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = backup_dir / f"note_{note_id}_{ts}.zip"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    emit(ctx, {
        "ok": True,
        "note_id": note_id,
        "path": str(out_path),
        "size": len(data),
    })


@cli.command("notes-search")
@click.argument("query")
@click.option("--course-url", default="", help="Limit to course URL.")
@click.pass_context
def notes_search(ctx, query, course_url):
    """Search note titles across cached courses."""
    courses = load_courses()
    if not courses:
        fail(ctx, "no cached courses; run `courses` first", 2)
    if course_url:
        targets = [c for c in courses if c.get("url") == course_url]
    else:
        targets = courses
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    results = []
    for c in targets:
        url = c.get("url")
        if not url:
            continue
        try:
            goto(page, url, wait=6000, timeout=ctx.obj["timeout"])
            time.sleep(1)
            for card in page.query_selector_all(selectors.NOTE_CARD):
                try:
                    t = card.query_selector(selectors.NOTE_TITLE)
                    title = t.inner_text().strip() if t else ""
                except Exception:
                    title = ""
                if query.lower() in title.lower():
                    nid = None
                    try:
                        labelled = card.get_attribute("aria-labelledby") or ""
                        if labelled.startswith("notes-"):
                            nid = labelled.split("-")[1]
                    except Exception:
                        pass
                    results.append({"course": c.get("name"), "note_id": nid, "title": title, "url": url})
        except Exception:
            pass
    emit(ctx, {"ok": True, "query": query, "count": len(results), "matches": results})
    close(ctx.obj, pw, br, ctxb, page)


# ---------- materials ----------
@cli.command()
@click.argument("url", default="https://loilonote.app/_/material-box")
@click.option("--folder", default="", help="Open sub-folder by name.")
@click.option("--path", default="", help="Navigate by path (e.g. '学内共有/81期国語科/１年次').")
@click.pass_context
def materials(ctx, url, folder, path):
    """List files/folders in materials box."""
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, url, wait=10000, timeout=ctx.obj["timeout"], wait_selector=selectors.MATERIAL_ITEM)
    # navigate by path
    if path:
        for part in path.split("/"):
            part = part.strip()
            if not part:
                continue
            time.sleep(1)
            found = False
            for e in page.query_selector_all(selectors.MATERIAL_ITEM):
                try:
                    label = e.get_attribute("aria-label") or e.inner_text()
                    if part in label and label.startswith("フォルダ"):
                        e.click()
                        found = True
                        time.sleep(2)
                        try:
                            page.wait_for_load_state("networkidle", timeout=8000)
                        except PWTimeout:
                            pass
                        break
                except Exception:
                    pass
            if not found:
                emit(ctx, {"ok": False, "error": f"folder not found: {part}", "url": page.url})
                close(ctx.obj, pw, br, ctxb, page)
                sys.exit(1)
    if folder:
        for e in page.query_selector_all(selectors.MATERIAL_ITEM):
            try:
                label = e.get_attribute("aria-label") or e.inner_text()
                if folder in label:
                    e.click()
                    time.sleep(2)
                    try:
                        page.wait_for_load_state("networkidle", timeout=8000)
                    except PWTimeout:
                        pass
                    break
            except Exception:
                pass
    items = []
    seen = set()
    for e in page.query_selector_all(selectors.MATERIAL_ITEM):
        try:
            label = e.get_attribute("aria-label") or e.inner_text().strip()
        except Exception:
            label = ""
        if label and label not in seen:
            seen.add(label)
            items.append(label)
    emit(ctx, {"ok": True, "url": page.url, "folder": folder or None, "path": path or None,
               "count": len(items), "items": items})
    close(ctx.obj, pw, br, ctxb, page)


@cli.command("materials-tree")
@click.option("--depth", type=int, default=4)
@click.pass_context
def materials_tree(ctx, depth):
    """Recursively list entire materials box as tree (JSON)."""
    if not browser.has_state():
        fail(ctx, "no session", 2)
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))

    def list_items():
        els = page.query_selector_all(selectors.MATERIAL_ITEM)
        out = []
        seen = set()
        for e in els:
            try:
                label = e.get_attribute("aria-label") or e.inner_text().strip()
            except Exception:
                label = ""
            if label and label not in seen:
                seen.add(label)
                out.append(label)
        return out

    def crawl(url, path, d):
        if d > depth:
            return []
        page.goto(url, wait_until="domcontentloaded", timeout=ctx.obj["timeout"])
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PWTimeout:
            pass
        time.sleep(1.5)
        result = []
        for label in list_items():
            full = (path + " / " + label).strip(" / ")
            node = {"name": label, "path": full, "children": []}
            if label.startswith("フォルダ"):
                els = page.query_selector_all(selectors.MATERIAL_ITEM)
                idx = None
                for i, e in enumerate(els):
                    try:
                        if (e.get_attribute("aria-label") or e.inner_text().strip()) == label:
                            idx = i; break
                    except Exception:
                        pass
                if idx is not None and idx < len(els):
                    try:
                        els[idx].click()
                        time.sleep(2)
                        try:
                            page.wait_for_load_state("networkidle", timeout=8000)
                        except PWTimeout:
                            pass
                        time.sleep(1)
                        child_url = page.url
                        if child_url != url:
                            node["children"] = crawl(child_url, full, d + 1)
                        page.goto(url, wait_until="domcontentloaded", timeout=ctx.obj["timeout"])
                        try:
                            page.wait_for_load_state("networkidle", timeout=8000)
                        except PWTimeout:
                            pass
                        time.sleep(1)
                    except Exception as e:
                        node["error"] = str(e)
            result.append(node)
        return result

    result = crawl("https://loilonote.app/_/material-box", "", 0)
    emit(ctx, {"ok": True, "root": "material-box", "children": result})
    close(ctx.obj, pw, br, ctxb, page)


@cli.command("materials-search")
@click.argument("query")
@click.option("--open", "open_first", is_flag=True, help="Open first match and return its text.")
@click.pass_context
def materials_search(ctx, query, open_first):
    """Search materials box by name using built-in search (fast)."""
    if not browser.has_state():
        fail(ctx, "no session", 2)
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, "https://loilonote.app/_/material-box", wait=5000, timeout=ctx.obj["timeout"], wait_selector="input[type='search'], input[placeholder*='検索'], input[aria-label*='検索']")
    inp = page.query_selector('input[type="search"], input[placeholder*="検索"], input[aria-label*="検索"]')
    if not inp:
        inp = page.query_selector("input")
    if not inp:
        fail(ctx, "search input not found")
    inp.fill(query)
    time.sleep(2)
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PWTimeout:
        pass
    items = []
    seen = set()
    for e in page.query_selector_all(selectors.MATERIAL_ITEM):
        try:
            label = e.get_attribute("aria-label") or e.inner_text().strip()
        except Exception:
            label = ""
        if label and label not in seen:
            seen.add(label)
            items.append(label)
    if open_first and items:
        for e in page.query_selector_all(selectors.MATERIAL_ITEM):
            try:
                label = e.get_attribute("aria-label") or e.inner_text().strip()
                if query.lower() in label.lower():
                    e.click()
                    time.sleep(3)
                    try:
                        page.wait_for_load_state("networkidle", timeout=12000)
                    except PWTimeout:
                        pass
                    time.sleep(2)
                    text = page.inner_text("body")
                    lines = [l for l in text.split("\n") if l.strip()]
                    cleaned = []
                    skip = False
                    for i, l in enumerate(lines):
                        if l.strip() == "1." and "動画" in (lines[i + 1] if i + 1 < len(lines) else ""):
                            skip = True
                        if skip and l.strip() == "わかった！":
                            skip = False
                            continue
                        if not skip:
                            cleaned.append(l)
                    cleaned_text = "\n".join(cleaned)
                    html_path, png_path = maybe_dump(ctx, page, "materials_get")
                    emit(ctx, {"ok": True, "query": query, "opened": label, "url": page.url,
                               "text": cleaned_text, "length": len(cleaned_text),
                               "dump_html": html_path, "dump_png": png_path})
                    close(ctx.obj, pw, br, ctxb, page)
                    return
            except Exception:
                pass
    try:
        inp.fill("")
    except Exception:
        pass
    emit(ctx, {"ok": True, "query": query, "count": len(items), "items": items})
    close(ctx.obj, pw, br, ctxb, page)


@cli.command("materials-get")
@click.argument("query")
@click.pass_context
def materials_get(ctx, query):
    """Search materials and open first match, returning its text content."""
    if not browser.has_state():
        fail(ctx, "no session", 2)
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, "https://loilonote.app/_/material-box", wait=5000, timeout=ctx.obj["timeout"], wait_selector="input[type='search'], input[placeholder*='検索'], input[aria-label*='検索']")
    inp = page.query_selector('input[type="search"], input[placeholder*="検索"], input[aria-label*="検索"]')
    if not inp:
        inp = page.query_selector("input")
    if not inp:
        fail(ctx, "search input not found")
    inp.fill(query)
    time.sleep(2)
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PWTimeout:
        pass

    clicked_label = None
    for e in page.query_selector_all(selectors.MATERIAL_ITEM):
        try:
            label = e.get_attribute("aria-label") or e.inner_text().strip()
            if query.lower() in label.lower():
                e.click()
                clicked_label = label
                break
        except Exception:
            pass
    if not clicked_label:
        els = page.query_selector_all(selectors.MATERIAL_ITEM)
        if els:
            try:
                els[0].click()
                clicked_label = els[0].get_attribute("aria-label") or els[0].inner_text().strip()
            except Exception:
                pass
    if not clicked_label:
        fail(ctx, "no match for " + query)

    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PWTimeout:
        pass
    time.sleep(1)

    text = page.inner_text("body")
    lines = [l for l in text.split("\n") if l.strip()]
    cleaned = []
    skip = False
    for l in lines:
        if l.strip() == "1." and "動画" in (lines[lines.index(l) + 1] if lines.index(l) + 1 < len(lines) else ""):
            skip = True
        if skip and l.strip() == "わかった！":
            skip = False
            continue
        if not skip:
            cleaned.append(l)
    cleaned_text = "\n".join(cleaned)
    html_path, png_path = maybe_dump(ctx, page, "materials_get")
    emit(ctx, {"ok": True, "query": query, "opened": clicked_label, "url": page.url,
               "text": cleaned_text, "length": len(cleaned_text),
               "dump_html": html_path, "dump_png": png_path})
    close(ctx.obj, pw, br, ctxb, page)
@cli.command("submissions")
@click.argument("url")
@click.pass_context
def submissions(ctx, url):
    """List submission boxes on a course's submissionBox tab."""
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, url, wait=8000, timeout=ctx.obj["timeout"])
    text = page.inner_text("body")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    items = []
    i = 0
    while i < len(lines):
        m = re.match(r"(\d{4}年\d{1,2}月\d{1,2}日\([^)]*\))\s*締切", lines[i])
        if m:
            deadline = m.group(1)
            title = lines[i + 1] if i + 1 < len(lines) else ""
            items.append({"deadline": deadline, "title": title})
            i += 2
        else:
            i += 1
    emit(ctx, {"ok": True, "url": page.url, "count": len(items), "submissions": items})
    close(ctx.obj, pw, br, ctxb, page)


# ---------- dump ----------
@cli.command()
@click.argument("url")
@click.pass_context
def dump(ctx, url):
    """Save page HTML + screenshot."""
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, url, wait=5000, timeout=ctx.obj["timeout"])
    # dump command always dumps (ignore --dump flag)
    ctx.obj["block_resources"] = False
    html_path, png_path = dump_page(page, "dump")
    emit(ctx, {"ok": True, "url": page.url, "html": html_path, "png": png_path})
    close(ctx.obj, pw, br, ctxb, page)


# ---------- create-note ----------
@cli.command("create-note")
@click.argument("title")
@click.argument("url")
@click.pass_context
def create_note(ctx, title, url):
    """Create a new note with TITLE at note list URL."""
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, url, wait=8000, timeout=ctx.obj["timeout"])
    btn = None
    for sel in selectors.CREATE_NOTE_BUTTON.split(","):
        btn = page.query_selector(sel.strip())
        if btn:
            break
    clicked = False
    if btn:
        btn.click(); clicked = True; time.sleep(0.5)
    ti = None
    for sel in selectors.NOTE_TITLE_INPUT.split(","):
        ti = page.query_selector(sel.strip())
        if ti:
            break
    filled = False
    if ti:
        ti.fill(title); filled = True
        time.sleep(0.3)
        # Try to confirm/save the note
        saved = False
        for sel in ["button[aria-label*='保存']", "button[aria-label*='save']", "button[aria-label*='確定']", "button[aria-label*='confirm']", "button:has-text('保存')", "button:has-text('作成')", "button:has-text('OK')", "button:has-text('完了')"]:
            save_btn = page.query_selector(sel)
            if save_btn:
                try:
                    save_btn.click(); saved = True; time.sleep(0.5)
                    break
                except Exception:
                    pass
        # Wait for save to complete
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except PWTimeout:
            pass
    html_path, png_path = maybe_dump(ctx, page, "create_note")
    emit(ctx, {"ok": True, "title": title, "create_clicked": clicked, "title_filled": filled,
               "dump_html": html_path, "dump_png": png_path})
    close(ctx.obj, pw, br, ctxb, page)


# ---------- submit ----------
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("url")
@click.pass_context
def submit(ctx, file, url):
    """Upload file to submission box at URL."""
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, url, wait=8000, timeout=ctx.obj["timeout"])
    fi = page.query_selector("input[type='file']")
    uploaded = False
    if fi:
        fi.set_input_files(file); uploaded = True
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PWTimeout:
            pass
        time.sleep(0.5)
    html_path, png_path = maybe_dump(ctx, page, "submit")
    emit(ctx, {"ok": True, "file": file, "uploaded": uploaded, "dump_html": html_path, "dump_png": png_path})
    close(ctx.obj, pw, br, ctxb, page)


# ---------- send ----------
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("url")
@click.option("--to", default="", help="Recipient name.")
@click.pass_context
def send(ctx, file, url, to):
    """Send file to individual at URL."""
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    goto(page, url, wait=8000, timeout=ctx.obj["timeout"])
    fi = page.query_selector("input[type='file']")
    uploaded = False
    if fi:
        fi.set_input_files(file); uploaded = True
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PWTimeout:
            pass
        time.sleep(0.5)
    recipient_filled = False
    if to:
        for sel in ["input[placeholder*='宛先']", "input[placeholder*='recipient']", "select"]:
            el = page.query_selector(sel)
            if el:
                try:
                    el.fill(to); recipient_filled = True; break
                except Exception:
                    try:
                        el.select_option(label=to); recipient_filled = True; break
                    except Exception:
                        pass
    html_path, png_path = maybe_dump(ctx, page, "send")
    emit(ctx, {"ok": True, "file": file, "to": to or None, "uploaded": uploaded,
               "recipient_filled": recipient_filled, "dump_html": html_path, "dump_png": png_path})
    close(ctx.obj, pw, br, ctxb, page)


# ---------- materials-upload ----------
@cli.command("materials-upload")
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@click.option("--path", default="", help="Target folder path in material box (e.g. 'マイフォルダ/同期用').")
@click.option("--folder-url", default="", help="Direct folder URL (skips path navigation, faster).")
@click.option("--url", default="https://loilonote.app/_/material-box", help="Material box URL.")
@click.pass_context
def materials_upload(ctx, files, path, folder_url, url):
    """Upload files to material box (e.g. personal material box)."""
    if not files:
        fail(ctx, "no files specified")
    if not browser.has_state():
        fail(ctx, "no session; run login first", 2)

    file_paths = [str(Path(f).resolve()) for f in files]
    pw, br, ctxb, page = browser.new_page(headless=not ctx.obj["headed"], slow_mo=ctx.obj["slow"], block_resources=ctx.obj.get("block_resources", True))
    try:
        if folder_url:
            goto(page, folder_url, wait=10000, timeout=ctx.obj["timeout"], wait_selector=selectors.MATERIAL_ITEM)
        else:
            goto(page, url, wait=10000, timeout=ctx.obj["timeout"], wait_selector=selectors.MATERIAL_ITEM)

            # Navigate to target path (same behavior as `materials --path`)
            if path:
                for part in path.split("/"):
                    part = part.strip()
                    if not part:
                        continue
                    time.sleep(0.3)
                    found = False
                    for e in page.query_selector_all(selectors.MATERIAL_ITEM):
                        try:
                            label = e.get_attribute("aria-label") or e.inner_text()
                            if part in label and label.startswith("フォルダ"):
                                e.click()
                                found = True
                                time.sleep(0.5)
                                try:
                                    page.wait_for_load_state("networkidle", timeout=3000)
                                except PWTimeout:
                                    pass
                                break
                        except Exception:
                            pass
                    if not found:
                        emit(ctx, {"ok": False, "error": f"folder not found: {part}", "url": page.url, "path": path})
                        close(ctx.obj, pw, br, ctxb, page)
                        sys.exit(1)

        # Upload flow discovered in live UI:
        #   1. Open the "more" (その他) menu (button with aria-haspopup="menu" / more_circle icon)
        #   2. Click the "アップロード" menu item (reveals a "ファイルを選択" button wrapping a file input)
        #   3. Click that "ファイルを選択" button and use the native file chooser
        uploaded = False
        upload_method = None

        # Step 1: open more menu
        more_btn = None
        for b in page.query_selector_all("[role='button']"):
            try:
                if b.get_attribute("aria-haspopup") == "menu":
                    more_btn = b
                    break
            except Exception:
                pass
        if more_btn is None:
            # fallback: find button whose icon has aria-label containing その他
            for b in page.query_selector_all("[role='button']"):
                try:
                    html = b.evaluate("el => el.outerHTML")
                    if "more_circle" in html:
                        more_btn = b
                        break
                except Exception:
                    pass

        if more_btn is not None:
            try:
                more_btn.click()
                time.sleep(0.3)
            except Exception as e:
                logger.warning("more button click failed: %s", e)

        # Step 2: click "アップロード" menu item
        upload_menu_item = None
        for e in page.query_selector_all("[role='menuitem']"):
            try:
                if "アップロード" in (e.inner_text() or ""):
                    upload_menu_item = e
                    break
            except Exception:
                pass
        if upload_menu_item is not None:
            try:
                upload_menu_item.click()
                time.sleep(0.5)
            except Exception as e:
                logger.warning("upload menu item click failed: %s", e)

        # Step 3: find "ファイルを選択" button (wraps hidden file input) and use file chooser
        file_select_btn = page.query_selector("div.uiPopoverItem:has(input[type='file'])")
        if file_select_btn is None:
            # fallback: any element containing a file input
            for container in page.query_selector_all(":has(> input[type='file'])"):
                file_select_btn = container
                break

        if file_select_btn is not None:
            try:
                with page.expect_file_chooser(timeout=10000) as fc_info:
                    file_select_btn.click()
                fc = fc_info.value
                fc.set_files(file_paths)
                uploaded = True
                upload_method = "file-chooser:uiPopoverItem"
            except PWTimeout:
                # Maybe clicking revealed a file input directly
                time.sleep(1)
                fi = page.query_selector("input[type='file']")
                if fi:
                    try:
                        fi.set_input_files(file_paths)
                        uploaded = True
                        upload_method = "file-input-after-upload-click"
                    except Exception as e:
                        logger.warning("file input set failed: %s", e)
            except Exception as e:
                logger.warning("file chooser error: %s", e)

        # Final fallback: try any visible/hidden file input
        if not uploaded:
            fi = page.query_selector("input[type='file']")
            if fi:
                try:
                    fi.set_input_files(file_paths)
                    uploaded = True
                    upload_method = "file-input-fallback"
                except Exception as e:
                    logger.warning("fallback file input failed: %s", e)

        if uploaded:
            # Give UI time to process uploads
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except PWTimeout:
                pass
            time.sleep(0.5)

        html_path, png_path = maybe_dump(ctx, page, "materials_upload")
        result = {
            "ok": bool(uploaded),
            "files": file_paths,
            "count": len(file_paths),
            "path": path or None,
            "url": page.url,
            "uploaded": uploaded,
            "method": upload_method,
            "dump_html": html_path,
            "dump_png": png_path,
        }
        if not uploaded:
            result["error"] = "upload control not found; check dump screenshot/html"
        emit(ctx, result)
    finally:
        close(ctx.obj, pw, br, ctxb, page)

    if not uploaded:
        sys.exit(1)


if __name__ == "__main__":
    cli()