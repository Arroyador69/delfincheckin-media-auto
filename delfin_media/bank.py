from __future__ import annotations

import random
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
    """Clip o foto de persona preocupada. Preferir vídeo si hay MP4 en hooks/."""
    bank = load_bank()
    key = "hooks_female" if persona.voice == "female" else "hooks_male"
    tagged = []
    for p in (BANK_DIR / "hooks").glob("*"):
        if p.suffix.lower() not in VIDEO_EXT:
            continue
        tokens = _hook_tokens(p)
        if persona.voice == "female":
            if "mujer" in tokens:
                tagged.append(p)
        elif "hombre" in tokens:
            tagged.append(p)
    if tagged:
        return random.choice(tagged)
    stills = _existing(bank.get(key, []))
    if not stills:
        sync_bank()
        stills = _existing(bank.get(key, []))
    if not stills:
        people_key = "people_female" if persona.voice == "female" else "people_male"
        stills = _existing(bank.get(people_key, []))
    if not stills:
        raise RuntimeError("Sin hook. python -m delfin_media bank")
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


def pick_app_clip(pain_id: str) -> Path | None:
    """MP4/MOV de la app (cualquier nombre). Si no hay, None."""
    bank = load_bank()
    spec = bank.get("app") or {}
    folder = BANK_DIR / spec.get("folder", "app")
    folder.mkdir(parents=True, exist_ok=True)
    videos = _app_videos(folder)
    if not videos:
        return None
    wanted = [
        spec.get("by_pain", {}).get(pain_id),
        spec.get("default"),
    ]
    lower = {p.name.lower(): p for p in videos}
    for name in wanted:
        if not name:
            continue
        hit = lower.get(str(name).lower())
        if hit:
            return hit
    return videos[0]


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXT
