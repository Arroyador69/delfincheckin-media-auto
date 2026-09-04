from __future__ import annotations

from pathlib import Path

import yaml

from delfin_media.paths import data_path
from delfin_media.script import Pain, load_pains


def _path() -> Path:
    return data_path("published.yaml")


def load_published() -> dict:
    path = _path()
    if not path.exists():
        return {"pains": [], "last_pack": 0, "hooks": []}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pains = list(raw.get("pains") or [])
    last_pack = int(raw.get("last_pack") or 0)
    hooks = list(raw.get("hooks") or [])
    return {"pains": pains, "last_pack": last_pack, "hooks": hooks}


def _write_published(data: dict) -> None:
    _path().write_text(
        yaml.safe_dump(
            {
                "last_pack": int(data.get("last_pack") or 0),
                "pains": list(data.get("pains") or []),
                "hooks": list(data.get("hooks") or []),
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
    _write_published({"last_pack": last, "pains": seen, "hooks": used_hooks})


def pick_unused_pain(*, money: bool) -> Pain:
    """Elige un dolor aún no publicado. Si están todos, recicla."""
    used = set(load_published()["pains"])
    pool = [p for p in load_pains() if bool(p.money_angle) is money]
    fresh = [p for p in pool if p.id not in used]
    chosen = fresh or pool
    if not chosen:
        raise RuntimeError("No hay dolores en data/pains.yaml")
    import random

    return random.choice(chosen)
