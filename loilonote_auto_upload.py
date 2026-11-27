#!/usr/bin/env python3
"""
LoiLoNote Auto-Upload Watcher

Watches a folder for new files and automatically uploads them to
LoiLoNote School's material box (personal folder).

Usage:
    python loilonote_auto_upload.py
    python loilonote_auto_upload.py --watch-dir /path/to/watch --folder-id 123456789
    python loilonote_auto_upload.py --once
    python loilonote_auto_upload.py --dump   # debug mode

Requirements:
    - loilonote-cli must be installed and logged in:  loilonote login
    - Python 3.9+ (no extra deps beyond loilonote-cli)

Note:
    - This is an unofficial tool using LoiLoNote's internal API.
    - Use in accordance with your school/organization's rules.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path

# ===== Defaults =====
DEFAULT_WATCH_DIR = Path.home() / "Desktop" / "loilonote-upload"
DEFAULT_FOLDER_ID = 287069612  # "同期用" folder
DEFAULT_INTERVAL = 2
DEFAULT_STABLE_CHECKS = 2
DEFAULT_MAX_RETRIES = 3

EXCLUDE_SUFFIXES = {".tmp", ".part", ".crdownload", ".download", ".bat", ".cmd", ".ps1", ".lnk", ".py"}
EXCLUDE_NAMES = {"desktop.ini", "Thumbs.db"}


def log(msg: str, log_file: Path | None = None) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def load_state(state_file: Path) -> dict:
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            return {"uploaded": {}}
    return {"uploaded": {}}


def save_state(state: dict, state_file: Path) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(state_file)


def load_auth_token(auth_token_file: Path) -> str | None:
    if auth_token_file.exists():
        try:
            data = json.loads(auth_token_file.read_text(encoding="utf-8"))
            return data.get("auth_token")
        except Exception:
            return None
    return None


def save_auth_token(token: str, auth_token_file: Path) -> None:
    auth_token_file.parent.mkdir(parents=True, exist_ok=True)
    auth_token_file.write_text(json.dumps({"auth_token": token}, ensure_ascii=False), encoding="utf-8")


def get_auth_token_playwright(folder_url: str, loilonote_cwd: Path, auth_token_file: Path) -> str | None:
    """Get auth_token using Playwright (one-time, cached)."""
    try:
        sys.path.insert(0, str(loilonote_cwd))
        from loilonote_cli import browser
        pw, br, ctxb, page = browser.new_page(headless=True, slow_mo=0)
        auth_token = [None]

        def on_request(request):
            url = request.url
            if "auth_token=" in url and auth_token[0] is None:
                parsed = urllib.parse.urlparse(url)
                qs = urllib.parse.parse_qs(parsed.query)
                if "auth_token" in qs:
                    auth_token[0] = qs["auth_token"][0]

        page.on("request", on_request)
        page.goto(folder_url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        time.sleep(1)

        token = auth_token[0]
        browser.close_all(pw, br, ctxb, page)
        if token:
            save_auth_token(token, auth_token_file)
            log(f"auth_token取得: {token[:8]}...")
        return token
    except Exception as e:
        log(f"auth_token取得失敗: {e}")
        return None


def get_auth_token(auth_token_file: Path, folder_url: str, loilonote_cwd: Path) -> str | None:
    token = load_auth_token(auth_token_file)
    if token:
        return token
    return get_auth_token_playwright(folder_url, loilonote_cwd, auth_token_file)


def get_cookies(loilonote_dir: Path) -> str:
    state = json.load(open(str(loilonote_dir / "state.json"), encoding="utf-8"))
    return "; ".join(f"{c['name']}={c['value']}" for c in state["cookies"])


def upload_file_api(
    p: Path,
    auth_token: str,
    folder_id: int,
    cookies: str,
    debug: bool = False,
    log_file: Path | None = None,
) -> tuple[bool, str]:
    """Upload using 3-step API flow. Returns (success, detail)."""
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ext = p.suffix
    file_name = p.name

    import mimetypes
    mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"

    for attempt in range(1, DEFAULT_MAX_RETRIES + 1):
        try:
            with open(p, "rb") as f:
                file_data = f.read()

            # Step 1: Upload generic file
            if debug:
                log(f"  Step1: generic_files upload ({len(file_data)} bytes)", log_file)
            url1 = f"https://n.loilo.tv/api/generic_files?extension={urllib.parse.quote(ext)}&auth_token={auth_token}"
            req1 = urllib.request.Request(url1, data=file_data, method="POST")
            req1.add_header("Content-Type", mime)
            req1.add_header("Cookie", cookies)
            req1.add_header("User-Agent", ua)
            resp1 = urllib.request.urlopen(req1, timeout=60)
            result1 = json.loads(resp1.read().decode())
            generic_file_id = result1.get("id")
            if debug:
                log(f"  Step1 OK: generic_file_id={generic_file_id}", log_file)

            # Step 2: Create asset
            if debug:
                log(f"  Step2: create asset", log_file)

            # Determine metadata based on file type
            if mime.startswith("image/"):
                try:
                    from PIL import Image
                    with Image.open(p) as img:
                        w, h = img.size
                    metadata_str = json.dumps([{"width": w, "height": h}])
                except Exception:
                    metadata_str = json.dumps([{"width": 0, "height": 0}])
            else:
                metadata_str = json.dumps([{"duration": 0}])

            asset_body = json.dumps({
                "generic_file_id": generic_file_id,
                "page_count": 1,
                "metadata": metadata_str,
                "thumbnails": "[]",
                "auth_token": auth_token,
            })
            url2 = f"https://n.loilo.tv/api/assets?auth_token={auth_token}"
            req2 = urllib.request.Request(url2, data=asset_body.encode("utf-8"), method="POST")
            req2.add_header("Content-Type", "application/json;charset=UTF-8")
            req2.add_header("Cookie", cookies)
            req2.add_header("User-Agent", ua)
            resp2 = urllib.request.urlopen(req2, timeout=60)
            result2 = json.loads(resp2.read().decode())
            asset_id = result2.get("result")
            if debug:
                log(f"  Step2 OK: asset_id={asset_id}", log_file)

            # Step 3: Upload document material with asset
            if debug:
                log(f"  Step3: upload document material", log_file)
            body_params = urllib.parse.urlencode({
                "group_id": str(folder_id),
                "asset": asset_id,
                "name": file_name,
                "auth_token": auth_token,
            })
            url3 = "https://n.loilo.tv/api/documents/assets"
            req3 = urllib.request.Request(url3, data=body_params.encode("utf-8"), method="POST")
            req3.add_header("Content-Type", "application/x-www-form-urlencoded")
            req3.add_header("Cookie", cookies)
            req3.add_header("User-Agent", ua)
            resp3 = urllib.request.urlopen(req3, timeout=60)
            result3 = json.loads(resp3.read().decode())
            doc_id = result3.get("id")
            if debug:
                log(f"  Step3 OK: doc_id={doc_id}", log_file)

            return True, f"doc_id={doc_id}"

        except urllib.error.HTTPError as e:
            error_body = e.read().decode()[:300]
            if e.code == 401:
                return False, f"auth expired (401): {error_body}"
            if attempt < DEFAULT_MAX_RETRIES:
                log(f"  リトライ {attempt}/{DEFAULT_MAX_RETRIES}: HTTP {e.code}", log_file)
                time.sleep(1)
                continue
            return False, f"HTTP {e.code}: {error_body}"
        except Exception as e:
            if attempt < DEFAULT_MAX_RETRIES:
                log(f"  リトライ {attempt}/{DEFAULT_MAX_RETRIES}: {e}", log_file)
                time.sleep(1)
                continue
            return False, str(e)

    return False, "max retries exceeded"


def file_key(p: Path) -> str:
    st = p.stat()
    return f"{p.name}|{st.st_size}|{int(st.st_mtime)}"


def is_candidate(p: Path, watch_dir: Path, uploaded_dir: Path, failed_dir: Path, exclude_names: set) -> bool:
    if not p.exists() or not p.is_file():
        return False
    if p.name.startswith("."):
        return False
    if p.name in exclude_names:
        return False
    if p.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    try:
        rel = p.resolve().relative_to(watch_dir.resolve())
    except Exception:
        return False
    if rel.parts and rel.parts[0] in {"uploaded", "failed"}:
        return False
    return True


def wait_until_stable(p: Path, stable_checks: int = DEFAULT_STABLE_CHECKS) -> bool:
    last_size = -1
    stable = 0
    for _ in range(30):
        if not p.exists():
            return False
        try:
            size = p.stat().st_size
        except OSError:
            return False
        if size == last_size and size > 0:
            stable += 1
            if stable >= stable_checks:
                return True
        else:
            stable = 0
            last_size = size
        time.sleep(1)
    return p.exists() and p.is_file()


def move_to_dir(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists():
        stem, suf = src.stem, src.suffix
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = dst_dir / f"{stem}_{ts}{suf}"
    shutil.move(str(src), str(dst))
    return dst


def scan_and_upload(
    watch_dir: Path,
    uploaded_dir: Path,
    failed_dir: Path,
    state_file: Path,
    auth_token_file: Path,
    log_file: Path,
    folder_id: int,
    folder_url: str,
    loilonote_cwd: Path,
    material_path: str,
    debug: bool = False,
) -> int:
    watch_dir.mkdir(parents=True, exist_ok=True)
    uploaded_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    exclude_names = EXCLUDE_NAMES | {state_file.name, log_file.name, auth_token_file.name}

    files = sorted(
        [p for p in watch_dir.iterdir() if is_candidate(p, watch_dir, uploaded_dir, failed_dir, exclude_names)],
        key=lambda p: p.stat().st_mtime,
    )
    uploaded_count = 0

    auth_token = get_auth_token(auth_token_file, folder_url, loilonote_cwd)
    if not auth_token:
        log("auth_tokenが取得できません。loilonote-cliでログインしてください。", log_file)
        return 0

    loilonote_dir = Path.home() / ".loilonote"
    try:
        cookies = get_cookies(loilonote_dir)
    except Exception as e:
        log(f"Cookie取得失敗: {e}", log_file)
        return 0

    state = load_state(state_file)

    for p in files:
        key = file_key(p)
        if key in state.get("uploaded", {}):
            log(f"スキップ（アップロード済み履歴あり）: {p.name}", log_file)
            try:
                moved = move_to_dir(p, uploaded_dir)
                log(f"整理移動: {moved}", log_file)
            except Exception as e:
                log(f"整理移動失敗: {p.name}: {e}", log_file)
            continue

        if not wait_until_stable(p):
            log(f"スキップ（安定しない/消失）: {p.name}", log_file)
            continue

        if not p.exists():
            continue
        key = file_key(p)

        t0 = time.time()
        ok, detail = upload_file_api(p, auth_token, folder_id, cookies, debug=debug, log_file=log_file)
        elapsed = time.time() - t0

        # If auth expired, try to refresh token once
        if not ok and "auth expired" in detail:
            log("auth_token更新中...", log_file)
            auth_token = get_auth_token_playwright(folder_url, loilonote_cwd, auth_token_file)
            if auth_token:
                try:
                    cookies = get_cookies(loilonote_dir)
                except Exception:
                    pass
                ok, detail = upload_file_api(p, auth_token, folder_id, cookies, debug=debug, log_file=log_file)
                elapsed = time.time() - t0

        if ok:
            state.setdefault("uploaded", {})[key] = {
                "name": p.name,
                "uploaded_at": datetime.now().isoformat(timespec="seconds"),
                "target": material_path,
            }
            save_state(state, state_file)
            try:
                moved = move_to_dir(p, uploaded_dir)
                log(f"成功: {p.name} -> {moved} ({elapsed:.1f}s)", log_file)
            except Exception as e:
                log(f"アップロード成功だが移動失敗: {p.name}: {e}", log_file)
            uploaded_count += 1
        else:
            log(f"失敗: {p.name}: {detail} ({elapsed:.1f}s)", log_file)
            try:
                moved = move_to_dir(p, failed_dir)
                log(f"失敗ファイルを退避: {moved}", log_file)
            except Exception as e:
                log(f"失敗ファイル退避にも失敗: {p.name}: {e}", log_file)

    return uploaded_count


def main() -> int:
    parser = argparse.ArgumentParser(description="ロイロノート資料箱へ自動アップロード")
    parser.add_argument("--watch-dir", type=Path, default=DEFAULT_WATCH_DIR, help="監視フォルダ (デフォルト: ~/Desktop/loilonote-upload)")
    parser.add_argument("--folder-id", type=int, default=DEFAULT_FOLDER_ID, help="アップロード先フォルダID (デフォルト: 287069612)")
    parser.add_argument("--folder-url", type=str, default=None, help="アップロード先フォルダURL (auth_token取得用)")
    parser.add_argument("--material-path", type=str, default="マイフォルダ/同期用", help="表示用パス名")
    parser.add_argument("--loilonote-dir", type=Path, default=None, help="loilonote-cliのディレクトリ")
    parser.add_argument("--once", action="store_true", help="1回だけチェックして終了")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="監視間隔秒")
    parser.add_argument("--dump", action="store_true", help="デバッグ: API応答を詳細ログに出力")
    args = parser.parse_args()

    watch_dir = args.watch_dir
    uploaded_dir = watch_dir / "uploaded"
    failed_dir = watch_dir / "failed"
    state_file = watch_dir / ".upload_state.json"
    log_file = watch_dir / "upload.log"
    auth_token_file = watch_dir / ".auth_token.json"

    if args.loilonote_dir:
        loilonote_cwd = args.loilonote_dir
    else:
        # Try to find loilonote-cli (script's own dir first, since it lives there)
        candidates = [
            Path(__file__).resolve().parent,
            Path.home() / "OneDrive" / "ドキュメント" / "loilonote-cli",
            Path.cwd().parent / "loilonote-cli",
            Path.cwd() / "loilonote-cli",
        ]
        loilonote_cwd = None
        for c in candidates:
            if (c / "loilonote_cli" / "browser.py").exists():
                loilonote_cwd = c
                break
        if loilonote_cwd is None:
            loilonote_cwd = Path.cwd()

    folder_url = args.folder_url or f"https://loilonote.app/_/material-box/{args.folder_id}"

    watch_dir.mkdir(parents=True, exist_ok=True)
    uploaded_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    state = load_state(state_file)
    log(f"監視開始: {watch_dir}", log_file)
    log(f"アップロード先: {args.material_path} (フォルダID: {args.folder_id})", log_file)
    if args.dump:
        log("デバッグモード: ON", log_file)

    if args.once:
        count = scan_and_upload(
            watch_dir, uploaded_dir, failed_dir, state_file, auth_token_file,
            log_file, args.folder_id, folder_url, loilonote_cwd, args.material_path,
            debug=args.dump,
        )
        log(f"完了: {count}件アップロード", log_file)
        return 0

    try:
        while True:
            scan_and_upload(
                watch_dir, uploaded_dir, failed_dir, state_file, auth_token_file,
                log_file, args.folder_id, folder_url, loilonote_cwd, args.material_path,
                debug=args.dump,
            )
            time.sleep(max(1, args.interval))
    except KeyboardInterrupt:
        log("停止しました", log_file)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())