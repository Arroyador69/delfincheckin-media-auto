from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from delfin_media.bank import pick_reel_stills, sync_bank
from delfin_media.captions import write_ass
from delfin_media.config import Config
from delfin_media.endcard import make_endcard
from delfin_media.images import persona_shots
from delfin_media.posts import write_instagram_pack
from delfin_media.render import render_reel
from delfin_media.script import Pain, Persona, Script, build_script
from delfin_media.tts import speak


def _slug(pain: Pain, persona: Persona) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}_{pain.id}_{persona.id}"


def generate_one(
    cfg: Config,
    *,
    pain_id: str | None = None,
    persona_id: str | None = None,
    money_only: bool = False,
    use_llm: bool = False,
) -> Path:
    pain, persona, script = build_script(
        cfg,
        pain_id=pain_id,
        persona_id=persona_id,
        money_only=money_only,
        use_llm=use_llm,
    )
    slug = _slug(pain, persona)
    work = Path("/tmp/delfin-media") / slug
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    cfg.ready_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"→ {slug}")
    print(f"  dolor: {pain.hook}")
    print(f"  persona: {persona.name} ({persona.city})")
    print(f"  guion ({script.source}): {script.text}")

    audio_path = work / "voice.mp3"
    voice = speak(script.text, persona, audio_path, cfg)
    print(f"  voz: {voice.duration:.1f}s · {len(voice.words)} palabras")

    if cfg.visual_mode == "faces":
        print("  visual: Flux (no usar: caras que no son españolas)")
        photos = persona_shots(persona, pain, cfg)
    else:
        print("  visual: banco (persona europea + habitaciones, Ken Burns)")
        sync_bank()
        photos = pick_reel_stills(persona, cfg)
    ass = write_ass(voice.words, work / "subs.ass", cfg)
    endcard = make_endcard(cfg, work / "endcard.png", pain.hook)
    dest = cfg.ready_dir / f"{slug}.mp4"
    render_reel(
        photos, voice.path, ass, endcard, dest, work, voice.duration, cfg
    )

    meta = {
        "file": dest.name,
        "pain_id": pain.id,
        "persona_id": persona.id,
        "hook": pain.hook,
        "script": script.text,
        "source": script.source,
        "duration_s": round(voice.duration + cfg.endcard_seconds, 2),
        "cta": cfg.cta_url,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (cfg.ready_dir / f"{slug}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  listo: {dest}")
    ig_dir = cfg.ready_dir / f"{slug}_ig"
    write_instagram_pack(cfg, ig_dir, pain, persona, script)
    print(f"  posts IG/FB: {ig_dir}")
    return dest
