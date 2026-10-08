"""Login Kit + Content Posting API (subida FILE_UPLOAD desde el Mac)."""

from __future__ import annotations

import json
import os
import re
import secrets
import select
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from delfin_media.config import Config
from delfin_media.paths import ROOT, data_path

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
DIRECT_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
INBOX_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
DEFAULT_REDIRECT = "https://social.delfincheckin.com/oauth/tiktok"
LOCAL_PORT = 8765
TOKEN_FILE = data_path("tiktok_oauth.json")
FIVE_MB = 5 * 1024 * 1024
TEN_MB = 10 * 1024 * 1024
SIXTY_FOUR_MB = 64 * 1024 * 1024
TITLE_MAX = 2200


class TikTokError(RuntimeError):
    pass


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def client_key() -> str:
    return _env("TIKTOK_CLIENT_KEY")


def client_secret() -> str:
    return _env("TIKTOK_CLIENT_SECRET")


def redirect_uri() -> str:
    return _env("TIKTOK_REDIRECT_URI") or DEFAULT_REDIRECT


def require_app_credentials() -> tuple[str, str]:
    key, secret = client_key(), client_secret()
    if not key or not secret:
        raise TikTokError(
            "Faltan TIKTOK_CLIENT_KEY y TIKTOK_CLIENT_SECRET en .env. "
            "Usa las del Sandbox (no las de Production)."
        )
    return key, secret


def _token_path() -> Path:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    return TOKEN_FILE


def load_token() -> dict[str, Any] | None:
    path = _token_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_token(payload: dict[str, Any]) -> None:
    now = int(time.time())
    stored = {
        "access_token": payload["access_token"],
        "refresh_token": payload.get("refresh_token", ""),
        "open_id": payload.get("open_id", ""),
        "scope": payload.get("scope", ""),
        "token_type": payload.get("token_type", "Bearer"),
        "expires_at": now + int(payload.get("expires_in") or 0) - 60,
        "refresh_expires_at": now + int(payload.get("refresh_expires_in") or 0) - 60,
        "saved_at": now,
    }
    _token_path().write_text(
        json.dumps(stored, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _raise_oauth(data: dict[str, Any]) -> None:
    err = data.get("error")
    if err:
        desc = data.get("error_description") or data.get("message") or err
        raise TikTokError(f"TikTok OAuth: {desc}")


def _raise_api(data: dict[str, Any]) -> None:
    error = data.get("error") or {}
    code = error.get("code") or ""
    if code and code != "ok":
        raise TikTokError(
            f"TikTok API ({code}): {error.get('message') or code} "
            f"[log {error.get('log_id') or error.get('logid') or '-'}]"
        )


def exchange_code(code: str) -> dict[str, Any]:
    key, secret = require_app_credentials()
    with httpx.Client(timeout=30) as client:
        res = client.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": key,
                "client_secret": secret,
                "code": code.strip(),
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri(),
            },
        )
        data = res.json()
    _raise_oauth(data)
    if not data.get("access_token"):
        raise TikTokError(f"TikTok no devolvió access_token: {data}")
    save_token(data)
    return data


def refresh_access_token(token: dict[str, Any]) -> dict[str, Any]:
    key, secret = require_app_credentials()
    refresh = token.get("refresh_token") or ""
    if not refresh:
        raise TikTokError("No hay refresh_token. Vuelve a ejecutar: python -m delfin_media tiktok login")
    with httpx.Client(timeout=30) as client:
        res = client.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": key,
                "client_secret": secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
        )
        data = res.json()
    _raise_oauth(data)
    if not data.get("access_token"):
        raise TikTokError(f"TikTok no renovó el token: {data}")
    save_token(data)
    return load_token() or data


def valid_token() -> dict[str, Any]:
    token = load_token()
    if not token or not token.get("access_token"):
        raise TikTokError("No hay sesión de TikTok. Primero: python -m delfin_media tiktok login")
    if int(token.get("expires_at") or 0) <= int(time.time()):
        token = refresh_access_token(token)
    return token


def extract_code(raw: str) -> str:
    text = raw.strip().strip('"').strip("'")
    if not text:
        raise TikTokError("No hay código de autorización.")
    if "code=" in text:
        parsed = urlparse(text)
        values = parse_qs(parsed.query).get("code") or parse_qs(parsed.fragment).get("code")
        if values:
            return values[0]
    if re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", text):
        return text
    raise TikTokError(
        "No pude leer el code. Pega la URL completa de "
        "social.delfincheckin.com/oauth/tiktok?code=..."
    )


def authorize_url(state: str, scopes: str) -> str:
    key, _ = require_app_credentials()
    query = urlencode(
        {
            "client_key": key,
            "response_type": "code",
            "scope": scopes,
            "redirect_uri": redirect_uri(),
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _serve_local_code(state: str, result: dict[str, str], stop: threading.Event) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.rstrip("/") not in {"/oauth/tiktok", "/callback"}:
                self.send_response(404)
                self.end_headers()
                return
            qs = parse_qs(parsed.query)
            got_state = (qs.get("state") or [""])[0]
            code = (qs.get("code") or [""])[0]
            err = (qs.get("error") or [""])[0]
            if err:
                result["error"] = err
            elif code and (not got_state or got_state == state):
                result["code"] = code
            body = (
                "<html><body style='font-family:sans-serif;padding:40px'>"
                "<h1>Delfín Check-in</h1><p>Ya puedes volver a la terminal.</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    try:
        server = HTTPServer(("127.0.0.1", LOCAL_PORT), Handler)
    except OSError:
        return
    server.timeout = 0.5
    try:
        while not stop.is_set() and "code" not in result and "error" not in result:
            server.handle_request()
    finally:
        server.server_close()


def login(*, scopes: str | None = None, code: str | None = None) -> dict[str, Any]:
    require_app_credentials()
    if code:
        data = exchange_code(extract_code(code))
        print(f"  sesión TikTok: open_id={data.get('open_id')} scopes={data.get('scope')}")
        return data

    state = secrets.token_urlsafe(16)
    wanted = scopes or "user.info.basic,video.publish,video.upload"
    url = authorize_url(state, wanted)
    print("Abre TikTok e inicia sesión con la cuenta de Delfín:")
    print(f"  {url}")
    print(
        "\nSi al terminar ves un 404 en delfincheckin.com, está bien: "
        "copia la URL completa de la barra y pégala aquí. Enter vacío espera al Mac."
    )
    result: dict[str, str] = {}
    stop = threading.Event()
    thread = threading.Thread(
        target=_serve_local_code, args=(state, result, stop), daemon=True
    )
    thread.start()
    webbrowser.open(url)
    deadline = time.time() + 180
    pasted = ""
    while time.time() < deadline and "code" not in result and "error" not in result:
        ready, _, _ = select.select([sys.stdin], [], [], 0.5)
        if ready:
            pasted = sys.stdin.readline().strip()
            break
    stop.set()
    if result.get("error"):
        raise TikTokError(f"TikTok denegó el acceso: {result['error']}")
    raw = pasted or result.get("code") or ""
    if not raw:
        pasted = input("URL o code: ").strip()
        raw = pasted
    data = exchange_code(extract_code(raw))
    print(f"  sesión TikTok: open_id={data.get('open_id')} scopes={data.get('scope')}")
    return data


def _api_headers(token: dict[str, Any]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/json; charset=UTF-8",
    }


def query_creator(token: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=30) as client:
        res = client.post(CREATOR_INFO_URL, headers=_api_headers(token), json={})
        data = res.json()
    _raise_api(data)
    return data.get("data") or {}


def _chunk_plan(size: int) -> tuple[int, int]:
    if size < FIVE_MB:
        return size, 1
    if size <= SIXTY_FOUR_MB:
        return size, 1
    chunk = TEN_MB
    count = max(1, size // chunk)
    return chunk, count


def _trim_title(caption: str) -> str:
    text = caption.strip()
    if len(text) <= TITLE_MAX:
        return text
    return text[: TITLE_MAX - 1].rstrip() + "…"


def _init_direct(
    token: dict[str, Any],
    *,
    title: str,
    video_size: int,
    chunk_size: int,
    total_chunk_count: int,
    privacy_level: str,
    disable_comment: bool = False,
    disable_duet: bool = False,
    disable_stitch: bool = False,
    brand_content_toggle: bool = False,
    brand_organic_toggle: bool = False,
) -> dict[str, Any]:
    body = {
        "post_info": {
            "title": _trim_title(title),
            "privacy_level": privacy_level,
            "disable_duet": disable_duet,
            "disable_comment": disable_comment,
            "disable_stitch": disable_stitch,
            "brand_content_toggle": brand_content_toggle,
            "brand_organic_toggle": brand_organic_toggle,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    }
    with httpx.Client(timeout=30) as client:
        res = client.post(DIRECT_INIT_URL, headers=_api_headers(token), json=body)
        data = res.json()
    _raise_api(data)
    return data.get("data") or {}


def _init_inbox(
    token: dict[str, Any],
    *,
    video_size: int,
    chunk_size: int,
    total_chunk_count: int,
) -> dict[str, Any]:
    body = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        }
    }
    with httpx.Client(timeout=30) as client:
        res = client.post(INBOX_INIT_URL, headers=_api_headers(token), json=body)
        data = res.json()
    _raise_api(data)
    return data.get("data") or {}


def _put_video(upload_url: str, path: Path, chunk_size: int, total_size: int) -> None:
    mime = "video/mp4"
    if path.suffix.lower() in {".mov", ".m4v"}:
        mime = "video/quicktime"
    sent = 0
    with path.open("rb") as fh, httpx.Client(timeout=300) as client:
        while sent < total_size:
            remaining = total_size - sent
            take = remaining if remaining <= chunk_size else chunk_size
            if remaining - take > 0 and remaining - take < FIVE_MB:
                take = remaining
            blob = fh.read(take)
            if not blob:
                break
            last = sent + len(blob) - 1
            res = client.put(
                upload_url,
                headers={
                    "Content-Type": mime,
                    "Content-Length": str(len(blob)),
                    "Content-Range": f"bytes {sent}-{last}/{total_size}",
                },
                content=blob,
            )
            if res.status_code not in {200, 201, 206}:
                raise TikTokError(
                    f"Subida TikTok HTTP {res.status_code}: {res.text[:400]}"
                )
            sent += len(blob)


def fetch_status(token: dict[str, Any], publish_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=30) as client:
        res = client.post(
            STATUS_URL,
            headers=_api_headers(token),
            json={"publish_id": publish_id},
        )
        data = res.json()
    _raise_api(data)
    return data.get("data") or {}


def wait_status(token: dict[str, Any], publish_id: str, timeout_s: int = 180) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = fetch_status(token, publish_id)
        status = str(last.get("status") or "")
        print(f"  estado: {status or last}")
        if status in {"PUBLISH_COMPLETE", "FAILED"}:
            return last
        time.sleep(4)
    return last


def publish_video(
    path: Path,
    caption: str,
    *,
    confirm: bool = True,
    inbox: bool = False,
    privacy_level: str | None = None,
    disable_comment: bool = False,
    disable_duet: bool = False,
    disable_stitch: bool = False,
    brand_content_toggle: bool = False,
    brand_organic_toggle: bool = False,
) -> dict[str, Any]:
    video = path.expanduser().resolve()
    if not video.exists() or video.suffix.lower() not in {".mp4", ".mov", ".m4v"}:
        raise TikTokError(f"No hay vídeo en {video}")
    token = valid_token()
    scopes = {s.strip() for s in str(token.get("scope") or "").split(",") if s.strip()}
    size = video.stat().st_size
    chunk_size, chunks = _chunk_plan(size)
    creator = {}
    privacy = privacy_level or "SELF_ONLY"
    use_inbox = inbox or "video.publish" not in scopes
    if not use_inbox:
        creator = query_creator(token)
        options = creator.get("privacy_level_options") or []
        if privacy not in options:
            if "SELF_ONLY" in options:
                privacy = "SELF_ONLY"
            elif options:
                privacy = str(options[0])
        print(
            f"  cuenta: @{creator.get('creator_username') or '-'} "
            f"({creator.get('creator_nickname') or '-'})"
        )
        print(f"  privacidad: {privacy}  opciones={options}")
        print("  marca: contenido propio de Delfín Check-in (brand organic)")
        print('  al publicar aceptas TikTok Music Usage Confirmation')
        if confirm:
            ok = input("Escribe PUBLICAR para enviar este Reel a TikTok: ").strip()
            if ok != "PUBLICAR":
                raise TikTokError("Cancelado.")
        payload = _init_direct(
            token,
            title=caption,
            video_size=size,
            chunk_size=chunk_size,
            total_chunk_count=chunks,
            privacy_level=privacy,
            disable_comment=disable_comment,
            disable_duet=disable_duet,
            disable_stitch=disable_stitch,
            brand_content_toggle=brand_content_toggle,
            brand_organic_toggle=brand_organic_toggle,
        )
    else:
        print("  modo bandeja (video.upload): queda como borrador en TikTok")
        if confirm:
            ok = input("Escribe PUBLICAR para enviar el borrador a TikTok: ").strip()
            if ok != "PUBLICAR":
                raise TikTokError("Cancelado.")
        payload = _init_inbox(
            token,
            video_size=size,
            chunk_size=chunk_size,
            total_chunk_count=chunks,
        )
    upload_url = payload.get("upload_url")
    publish_id = payload.get("publish_id")
    if not upload_url or not publish_id:
        raise TikTokError(f"TikTok no devolvió upload_url: {payload}")
    print(f"  subiendo {video.name} ({size} bytes, {chunks} parte(s))")
    _put_video(str(upload_url), video, chunk_size, size)
    status = wait_status(token, str(publish_id))
    return {
        "publish_id": publish_id,
        "status": status,
        "inbox": use_inbox,
        "privacy": privacy if not use_inbox else "inbox",
        "creator": creator.get("creator_username"),
        "file": str(video),
    }


def latest_pack(cfg: Config) -> Path:
    ready = cfg.ready_dir
    packs = sorted(
        [p for p in ready.iterdir() if p.is_dir() and p.name.endswith("_pack")],
        key=lambda p: p.stat().st_mtime,
    )
    if not packs:
        raise TikTokError(f"No hay pack en {ready}. Primero: python -m delfin_media day")
    return packs[-1]


def pack_reels(pack: Path) -> list[tuple[Path, str, str]]:
    items: list[tuple[Path, str, str]] = []
    for folder, label in (
        ("01_reel_tiempo", "Reel tiempo (Lucía)"),
        ("02_reel_dinero", "Reel dinero (Pablo)"),
    ):
        video = pack / folder / "reel.mp4"
        caption_path = pack / folder / "CAPTION_REEL_TIKTOK.txt"
        caption = caption_path.read_text(encoding="utf-8") if caption_path.exists() else ""
        if video.exists():
            items.append((video, caption, label))
    if not items:
        raise TikTokError(f"El pack {pack.name} no tiene reel.mp4")
    return items


def publish_pack(
    cfg: Config,
    *,
    pack_dir: Path | None = None,
    confirm: bool = True,
    inbox: bool = False,
) -> list[dict[str, Any]]:
    pack = pack_dir or latest_pack(cfg)
    results = []
    print(f"Pack TikTok: {pack.name}")
    for video, caption, label in pack_reels(pack):
        print(f"\n→ {label}: {video}")
        results.append(
            publish_video(video, caption, confirm=confirm, inbox=inbox)
        )
    return results
