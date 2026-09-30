from __future__ import annotations

from pathlib import Path

import yaml

from delfin_media.paths import data_path
from delfin_media.script import Pain, load_pains

# Reels únicos que quedan por ángulo (tiempo o dinero) antes de avisar.
LOW_INVENTORY = 8


def _path() -> Path:
    return data_path("published.yaml")


def load_published() -> dict:
    path = _path()
    if not path.exists():
        return {"pains": [], "last_pack": 0, "hooks": [], "scripts": [], "rooms": []}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pains = list(raw.get("pains") or [])
    last_pack = int(raw.get("last_pack") or 0)
    hooks = list(raw.get("hooks") or [])
    scripts = list(raw.get("scripts") or [])
    rooms = list(raw.get("rooms") or [])
    return {
        "pains": pains,
        "last_pack": last_pack,
        "hooks": hooks,
        "scripts": scripts,
        "rooms": rooms,
    }


def _write_published(data: dict) -> None:
    _path().write_text(
        yaml.safe_dump(
            {
                "last_pack": int(data.get("last_pack") or 0),
                "pains": list(data.get("pains") or []),
                "hooks": list(data.get("hooks") or []),
                "scripts": list(data.get("scripts") or []),
                "rooms": list(data.get("rooms") or []),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def mark_published(
    pain_ids: list[str],
    pack: int | None = None,
    hooks: list[str] | None = None,
    scripts: list[str] | None = None,
    rooms: list[str] | None = None,
) -> None:
    data = load_published()
    seen = list(data["pains"])
    for pid in pain_ids:
        if pid not in seen:
            seen.append(pid)
    last = data.get("last_pack") or 0
    if pack is not None:
        last = pack
    used_hooks = list(data.get("hooks") or [])
    for name in hooks or []:
        if name and name not in used_hooks:
            used_hooks.append(name)
    used_scripts = list(data.get("scripts") or [])
    for key in scripts or []:
        if key and key not in used_scripts:
            used_scripts.append(key)
    used_rooms = list(data.get("rooms") or [])
    for name in rooms or []:
        if name and name not in used_rooms:
            used_rooms.append(name)
    # Si el banco se ha reciclado entero, vaciar el historial de habitaciones.
    rooms_dir = Path(__file__).resolve().parents[1] / "assets" / "bank" / "rooms"
    on_disk = {
        p.name
        for p in rooms_dir.glob("*")
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    }
    if on_disk and used_rooms and set(used_rooms) >= on_disk:
        used_rooms = list(rooms or [])
    _write_published(
        {
            "last_pack": last,
            "pains": seen,
            "hooks": used_hooks,
            "scripts": used_scripts,
            "rooms": used_rooms,
        }
    )


def remaining_pains(*, money: bool) -> list[Pain]:
    used = set(load_published()["pains"])
    return [p for p in load_pains() if bool(p.money_angle) is money and p.id not in used]


def inventory() -> dict[str, int]:
    return {
        "tiempo": len(remaining_pains(money=False)),
        "dinero": len(remaining_pains(money=True)),
        "total": len(load_pains()),
    }


def pick_unused_script_index(pain: Pain) -> int:
    used = set(load_published().get("scripts") or [])
    for i, _text in enumerate(pain.scripts):
        if f"{pain.id}:{i}" not in used:
            return i
    return 0


def warn_inventory(*, lucia_id: str, pablo_id: str) -> None:
    """Avisa en consola si este pack recicla un guion o si quedan pocos únicos."""
    used = set(load_published()["pains"])
    stats = inventory()
    t_after = stats["tiempo"] - (0 if lucia_id in used else 1)
    d_after = stats["dinero"] - (0 if pablo_id in used else 1)
    recycled = []
    if lucia_id in used:
        recycled.append(f"Lucía ({lucia_id})")
    if pablo_id in used:
        recycled.append(f"Pablo ({pablo_id})")
    print(
        f"  Inventario: {stats['tiempo']} tiempo/legal + {stats['dinero']} dinero "
        f"sin usar de {stats['total']} Reels únicos."
    )
    if recycled:
        print(
            "  AVISO: este pack VA A REPETIR guion ya publicado: "
            + ", ".join(recycled)
            + "."
        )
        print(
            "  Para no reciclar: añade dolores nuevos en data/pains_more.yaml "
            "(hook oral, locutado y carrusel distintos) y, si hace falta, "
            "clips nuevos en assets/bank/hooks/."
        )
    print(
        f"  Tras este pack quedarán {max(t_after, 0)} tiempo/legal y "
        f"{max(d_after, 0)} dinero (~{max(min(t_after, d_after), 0)} packs únicos)."
    )
    if t_after < LOW_INVENTORY or d_after < LOW_INVENTORY:
        print(
            "  AVISO: quedan pocos guiones únicos. Sube vídeos nuevos al banco "
            "y escribe dolores nuevos antes de que se empiecen a repetir."
        )


def pick_unused_pain(*, money: bool) -> Pain:
    """Elige un dolor aún no publicado. Si están todos, recicla (con aviso)."""
    pool = [p for p in load_pains() if bool(p.money_angle) is money]
    if not pool:
        raise RuntimeError("No hay dolores en data/pains.yaml ni data/pains_more.yaml")
    fresh = remaining_pains(money=money)
    import random

    return random.choice(fresh or pool)
