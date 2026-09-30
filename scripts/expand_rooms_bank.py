#!/usr/bin/env python3
"""Banco de habitaciones limpio: solo vivienda / apartamento / villa / paisaje.

Borra el dump pexels-* / ov-* contaminado, mantiene los 18 originales curados,
y descarga ~540 fotos vía Wikimedia Commons (CC) filtrando título/categorías.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ROOMS = ROOT / "assets" / "bank" / "rooms"
UA = "delfincheckin-media-auto/0.4 (stock bank; https://delfincheckin.com)"
API = "https://commons.wikimedia.org/w/api.php"

# Búsquedas: interiores vacíos, villas, paisajes costeros.
QUERIES = [
    "hotel bedroom interior",
    "hotel room empty bed",
    "apartment bedroom interior",
    "apartment living room interior",
    "modern apartment interior",
    "villa bedroom interior",
    "villa living room",
    "villa swimming pool",
    "luxury hotel bedroom",
    "cozy bedroom interior",
    "minimalist bedroom interior",
    "living room sofa apartment",
    "kitchen apartment interior",
    "bathroom hotel modern",
    "terrace apartment view",
    "balcony ocean apartment",
    "mediterranean villa exterior",
    "beach house exterior",
    "coastal landscape sea",
    "ocean sunset landscape",
    "tropical resort pool",
    "holiday home interior",
    "furnished apartment empty",
    "boutique hotel room",
    "scandinavian bedroom",
    "penthouse living room",
    "guest room hotel bed",
    "suite hotel bedroom",
    "resort hotel room interior",
    "cottage interior bedroom",
]

ALLOW = re.compile(
    r"\b(hotel|bedroom|bed\b|apartment|flat|condo|villa|resort|suite|"
    r"living\s*room|salon|lounge|kitchen|bathroom|bath\b|pool|piscina|"
    r"terrace|balcony|interior|room\b|house|home|cabin|cottage|chalet|"
    r"landscape|beach|ocean|sea\b|coast|mountain|sunset|architecture|"
    r"real\s*estate|property|rental|vacation|holiday|dormitorio|habitaci|"
    r"apartamento|vivienda|mobiliario|furniture|sofa|sofá)\b",
    re.I,
)

DENY = re.compile(
    r"\b(people|person|man\b|woman|girl|boy|child|baby|portrait|selfie|"
    r"face|couple|family|crowd|wedding|business\s*man|model|"
    r"food|restaurant|meal|coffee|laptop|office\s*desk|"
    r"car\b|vehicle|street\s*food|dog\b|cat\b|animal|pet\b|"
    r"smartphone|holding\s*phone|working\s*on|typing|"
    r"yoga|fitness|gym|sport|running|fashion|makeup|"
    r"statue|sculpture|painting\b|museum|map\b|logo|"
    r"personas?|mujer|hombre|niñ[oa]|retrato|comida|"
    r"coche|perro|gato|selfie)\b",
    re.I,
)

ORIGINAL_KEEP = {
    "apto-mesa.jpg",
    "apto-moderno.jpg",
    "cama-blanca.jpg",
    "dormitorio-claro.jpg",
    "dormitorio.jpg",
    "habitacion-madera.jpg",
    "hotel-blanco.jpg",
    "hotel-cama.jpg",
    "hotel-lujo-2.jpg",
    "hotel-lujo.jpg",
    "hotel-ventana.jpg",
    "piscina-atardecer.jpg",
    "resort-piscina.jpg",
    "salon-grande.jpg",
    "salon-luz.jpg",
    "salon-sofa.jpg",
    "suite-cama.jpg",
    "terraza-vistas.jpg",
}


def _get_json(params: dict) -> dict:
    q = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(
        f"{API}?{q}",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _safe_name(pageid: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40].strip("-")
    return f"wm-{pageid}-{slug}.jpg"


def harvest(target: int = 600) -> list[dict]:
    seen: set[str] = set()
    items: list[dict] = []
    for qi, q in enumerate(QUERIES, 1):
        offset = 0
        for _ in range(6):
            try:
                data = _get_json(
                    {
                        "action": "query",
                        "generator": "search",
                        "gsrnamespace": 6,
                        "gsrlimit": 50,
                        "gsroffset": offset,
                        "gsrsearch": q,
                        "prop": "imageinfo",
                        "iiprop": "url|size|mime|extmetadata",
                        "iiurlwidth": 1280,
                    }
                )
            except Exception as exc:
                print(f"  aviso {q!r} offset={offset}: {exc}")
                time.sleep(1.2)
                break
            pages = (data.get("query") or {}).get("pages") or {}
            if not pages:
                break
            for page in pages.values():
                title = page.get("title") or ""
                info = (page.get("imageinfo") or [{}])[0]
                mime = (info.get("mime") or "").lower()
                if "image/jpeg" not in mime and "image/png" not in mime and "image/webp" not in mime:
                    continue
                meta = info.get("extmetadata") or {}
                desc = " ".join(
                    str((meta.get(k) or {}).get("value") or "")
                    for k in ("ImageDescription", "ObjectName", "Categories", "Artist")
                )
                blob = f"{title} {desc}"
                blob_plain = re.sub(r"<[^>]+>", " ", blob)
                if DENY.search(blob_plain):
                    continue
                if not ALLOW.search(blob_plain):
                    continue
                img_url = info.get("thumburl") or info.get("url") or ""
                if not img_url or img_url in seen:
                    continue
                w = int(info.get("thumbwidth") or info.get("width") or 0)
                h = int(info.get("thumbheight") or info.get("height") or 0)
                if min(w, h) < 400 and min(int(info.get("width") or 0), int(info.get("height") or 0)) < 400:
                    continue
                pageid = str(page.get("pageid") or len(items))
                seen.add(img_url)
                items.append(
                    {
                        "id": pageid,
                        "url": img_url,
                        "title": title.replace("File:", "")[:80],
                    }
                )
                if len(items) >= target + 100:
                    print(f"  suficientes candidatas: {len(items)}")
                    return items
            cont = data.get("continue") or {}
            if "gsroffset" not in cont:
                break
            offset = int(cont["gsroffset"])
            time.sleep(0.25)
        print(f"  [{qi}/{len(QUERIES)}] candidatas={len(items)} · {q}")
        if len(items) >= target + 100:
            break
    return items


def download_one(item: dict) -> Path | None:
    dest = ROOMS / _safe_name(item["id"], item["title"])
    if dest.exists() and dest.stat().st_size > 8_000:
        return dest
    req = urllib.request.Request(item["url"], headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if len(data) < 8_000:
            return None
        img = Image.open(BytesIO(data)).convert("RGB")
        if min(img.size) < 400:
            return None
        img.save(dest, "JPEG", quality=88)
        return dest
    except Exception as exc:
        print(f"  fallo {item['id']}: {exc}")
        return None


def wipe_contaminated() -> int:
    n = 0
    for p in list(ROOMS.glob("*")):
        if not p.is_file():
            continue
        if p.name in ORIGINAL_KEEP:
            continue
        if p.name.startswith(("pexels-", "ov-", "wm-")):
            p.unlink()
            n += 1
    return n


def main() -> int:
    ROOMS.mkdir(parents=True, exist_ok=True)
    removed = wipe_contaminated()
    kept = len([p for p in ROOMS.glob("*.jpg") if p.name in ORIGINAL_KEEP])
    print(f"Eliminadas {removed} fotos fuera de tema. Originales curados: {kept}")

    target = 540
    print("Buscando interiores / villas / paisajes (Wikimedia Commons)…")
    items = harvest(target=target)
    print(f"Candidatas: {len(items)}. Descargando…")

    ok = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(download_one, it) for it in items]
        for fut in as_completed(futs):
            path = fut.result()
            if path:
                ok += 1
                if ok % 40 == 0:
                    total = len(list(ROOMS.glob("*.jpg")))
                    print(f"  … {ok} ok / {total} en disco")
            if len(list(ROOMS.glob("*.jpg"))) >= target + kept:
                break

    total = len(list(ROOMS.glob("*.jpg")))
    print(f"Listo. Total rooms: {total} (~{total // 6} días a 6 fotos/día)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
