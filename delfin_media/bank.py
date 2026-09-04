from __future__ import annotations

import random
import re
import unicodedata
from pathlib import Path

import httpx
import yaml
from PIL import Image

from delfin_media.paths import ROOT, data_path
from delfin_media.script import Persona

BANK_DIR = ROOT / "assets" / "bank"
PEXELS = "https://images.pexels.com/photos/{id}/pexels-photo-{id}.jpeg"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}


def load_bank() -> dict:
    return yaml.safe_load(data_path("bank.yaml").read_text(encoding="utf-8"))


def _download_photo(item: dict) -> Path:
    dest = BANK_DIR / item["file"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 8_000:
        return dest
    url = PEXELS.format(id=item["id"]) + "?auto=compress&cs=tinysrgb&w=1280"
    print(f"  banco · {dest.name}")
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(
            url,
            headers={"User-Agent": "delfincheckin-media-auto/0.3 (commercial CC0 bank)"},
        )
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    img = Image.open(dest).convert("RGB")
    img.save(dest, "JPEG", quality=88)
    return dest


def _download_video(item: dict) -> Path:
    dest = BANK_DIR / item["file"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 50_000:
        return dest
    print(f"  banco vídeo · {dest.name}")
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        resp = client.get(
            item["url"],
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        )
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


def sync_bank() -> list[Path]:
    bank = load_bank()
    paths: list[Path] = []
    for group in ("rooms", "people_female", "people_male", "hooks_female", "hooks_male"):
        for item in bank.get(group, []):
            try:
                paths.append(_download_photo(item))
            except Exception as exc:
                print(f"  aviso: no se pudo bajar {item['file']}: {exc}")
    for item in bank.get("hook_videos", []):
        try:
            paths.append(_download_video(item))
        except Exception as exc:
            print(f"  aviso: no se pudo bajar {item['file']}: {exc}")
    (BANK_DIR / "app").mkdir(parents=True, exist_ok=True)
    (BANK_DIR / "hooks").mkdir(parents=True, exist_ok=True)
    (BANK_DIR / "music").mkdir(parents=True, exist_ok=True)
    for item in bank.get("music", []):
        try:
            paths.append(_download_video(item))
        except Exception as exc:
            print(f"  aviso: no se pudo bajar {item['file']}: {exc}")
    return paths


def _existing(items: list[dict]) -> list[Path]:
    out = []
    for item in items:
        path = BANK_DIR / item["file"]
        if path.exists() and path.stat().st_size > 8_000:
            out.append(path)
    return out


def _fill(paths: list[Path], n: int) -> list[Path]:
    if not paths:
        return []
    chosen = random.sample(paths, min(n, len(paths)))
    i = 0
    while len(chosen) < n:
        chosen.append(paths[i % len(paths)])
        i += 1
    return chosen


def pick_rooms(n: int = 3) -> list[Path]:
    rooms = _existing(load_bank()["rooms"])
    if not rooms:
        sync_bank()
        rooms = _existing(load_bank()["rooms"])
    return _fill(rooms, n)


def _hook_tokens(path: Path) -> set[str]:
    return set(path.stem.lower().replace("_", "-").split("-"))


def pick_hook(persona: Persona) -> Path:
    """Vídeo de persona preocupada: mujer para Lucía, hombre para Pablo.

    Prioriza clips que aún no han salido en un pack (data/published.yaml → hooks).
    """
    from delfin_media.history import load_published

    bank = load_bank()
    key = "hooks_female" if persona.voice == "female" else "hooks_male"
    want = "mujer" if persona.voice == "female" else "hombre"
    tagged = []
    for p in (BANK_DIR / "hooks").glob("*"):
        if p.suffix.lower() not in VIDEO_EXT:
            continue
        tokens = _hook_tokens(p)
        if want not in tokens:
            continue
        if "estres" not in tokens:
            continue
        tagged.append(p)
    used = set(load_published().get("hooks") or [])
    fresh = [p for p in tagged if p.name not in used]
    pool = fresh or tagged
    if pool:
        return random.choice(pool)
    stills = _existing(bank.get(key, []))
    if not stills:
        sync_bank()
        stills = _existing(bank.get(key, []))
    if not stills:
        raise RuntimeError(
            "Sin hook de persona preocupada. Revisa assets/bank/hooks/ "
            "(mujer-estres-*.mp4 / hombre-estres-*.mp4)."
        )
    return random.choice(stills)


def _app_videos(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    out: list[Path] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXT:
            continue
        if path.stat().st_size > 20_000:
            out.append(path)
    return out


_FILENAME_TYPOS = (
    ("resrvas", "reservas"),
    ("resrva", "reserva"),
)


def _norm_name(value: str) -> str:
    """Quita acentos, espacios raros y erratas típicas del título del clip."""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    for bad, good in _FILENAME_TYPOS:
        text = text.replace(bad, good)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _wanted_key(wanted: str) -> str:
    raw = str(wanted).strip()
    stem = Path(raw).stem if Path(raw).suffix.lower() in VIDEO_EXT else raw
    return _norm_name(stem)


def match_app_clip(videos: list[Path], wanted: str) -> Path | None:
    """Elige el clip cuyo título encaja con las palabras pedidas (formulario, microsite…)."""
    needle = _wanted_key(wanted)
    if not needle:
        return None
    ranked: list[tuple[int, Path]] = []
    for path in videos:
        hay = _norm_name(path.stem)
        score = 0
        if hay == needle:
            score = 100
        elif needle in hay:
            score = 80 + min(len(needle), 15)
        else:
            tokens = needle.split()
            hay_tokens = set(hay.split())
            if tokens and all(t in hay_tokens for t in tokens):
                score = 50 + len(tokens)
            elif tokens and all(t in hay for t in tokens):
                score = 40 + len(tokens)
        if score:
            ranked.append((score, path))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1].name.lower()))
    return ranked[0][1]


def pick_app_clip(pain_id: str) -> Path | None:
    """MP4/MOV de la app. Empareja por palabras del título, no hace falta un nombre fijo."""
    bank = load_bank()
    spec = bank.get("app") or {}
    folder = BANK_DIR / spec.get("folder", "app")
    folder.mkdir(parents=True, exist_ok=True)
    videos = _app_videos(folder)
    if not videos:
        return None
    for wanted in (spec.get("by_pain", {}).get(pain_id), spec.get("default")):
        if not wanted:
            continue
        hit = match_app_clip(videos, str(wanted))
        if hit:
            return hit
    return videos[0]


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXT


def pick_music() -> Path | None:
    """MP3 de fondo. Rota entre varias pistas del banco."""
    items = load_bank().get("music") or []
    paths = _existing(items)
    if len(paths) < 1:
        sync_bank()
        paths = _existing(load_bank().get("music") or [])
    if not paths:
        return None
    return random.choice(paths)
