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
        return {"pains": []}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    pains = list(raw.get("pains") or [])
    return {"pains": pains}


def mark_published(pain_ids: list[str]) -> None:
    data = load_published()
    seen = list(data["pains"])
    for pid in pain_ids:
        if pid not in seen:
            seen.append(pid)
    _path().write_text(
        yaml.safe_dump({"pains": seen}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


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
