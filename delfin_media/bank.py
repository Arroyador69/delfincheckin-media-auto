from __future__ import annotations

import random
from pathlib import Path

import httpx
import yaml
from PIL import Image

from delfin_media.config import Config
from delfin_media.paths import ROOT, data_path
from delfin_media.script import Persona

BANK_DIR = ROOT / "assets" / "bank"
PEXELS = "https://images.pexels.com/photos/{id}/pexels-photo-{id}.jpeg"


def load_bank() -> dict:
    return yaml.safe_load(data_path("bank.yaml").read_text(encoding="utf-8"))


def _download(item: dict) -> Path:
    dest = BANK_DIR / item["file"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 8_000:
        return dest
    url = PEXELS.format(id=item["id"]) + "?auto=compress&cs=tinysrgb&w=1280"
    print(f"  banco · {dest.name}")
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(
            url,
            headers={"User-Agent": "delfincheckin-media-auto/0.2 (commercial CC0 bank)"},
        )
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    img = Image.open(dest).convert("RGB")
    img.save(dest, "JPEG", quality=88)
    return dest


def sync_bank() -> list[Path]:
    bank = load_bank()
    paths: list[Path] = []
    for group in ("rooms", "people_female", "people_male"):
        for item in bank[group]:
            try:
                paths.append(_download(item))
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


def pick_people(persona: Persona, n: int = 2) -> list[Path]:
    bank = load_bank()
    key = "people_female" if persona.voice == "female" else "people_male"
    people = _existing(bank[key])
    if not people:
        sync_bank()
        people = _existing(bank[key])
    if not people:
        return []
    if len(people) <= n:
        return people
    return random.sample(people, n)


def pick_reel_stills(persona: Persona, _cfg: Config) -> list[Path]:
    people = pick_people(persona, 1)
    rooms = pick_rooms(2)
    stills = people + rooms
    if not stills:
        raise RuntimeError("Banco vacío. python -m delfin_media bank")
    return stills[:3]
