from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from delfin_media.bank import is_video, pick_app_clip, pick_hook, pick_music, pick_rooms, sync_bank
from delfin_media.captions import write_ass
from delfin_media.config import Config
from delfin_media.endcard import make_endcard
from delfin_media.history import mark_published, pick_unused_pain
from delfin_media.posts import write_instagram_pack, write_publish_guide, write_reel_captions
from delfin_media.render import render_reel
from delfin_media.script import Pain, Persona, build_script
from delfin_media.stories import write_stories_pack
from delfin_media.tts import concat_voiceovers, speak


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
    dest_dir: Path | None = None,
    carousel_dir: Path | None = None,
    reel_name: str | None = None,
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
    out_dir = dest_dir or cfg.ready_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg.logs_dir.mkdir(parents=True, exist_ok=True)

    print(f"→ {slug}")
    print(f"  dolor: {pain.hook}")
    print(f"  hook 3s: {script.spoken_hook}")
    print(f"  persona: {persona.name} ({persona.city})")
    print(f"  cuerpo ({script.source}): {script.text}")
    print(f"  motor voz: {cfg.voice_engine}")

    hook_vo = speak(script.spoken_hook, persona, work / "hook.mp3", cfg)
    body_vo = speak(script.text, persona, work / "body.mp3", cfg)
    voice = concat_voiceovers([hook_vo, body_vo], work / "voice.mp3")
    print(
        f"  voz: hook {hook_vo.duration:.1f}s + cuerpo {body_vo.duration:.1f}s "
        f"= {voice.duration:.1f}s"
    )

    sync_bank()
    hook_src = pick_hook(persona)
    app_src = pick_app_clip(pain.id)
    if app_src is None:
        rooms = pick_rooms(1)
        app_src = rooms[0] if rooms else hook_src
        print("  aviso: no hay MP4 de la app en assets/bank/app/. Cuerpo con habitación.")
    else:
        print(f"  app: {app_src.name} ({app_src})")
    print(f"  hook visual: {hook_src.name}")
    music = pick_music()
    if music:
        print(f"  música: {music.name} (entra tras el hook, baja antes del cierre)")
    else:
        print("  aviso: sin música de fondo en assets/bank/music/")

    ass = write_ass(voice.words, work / "subs.ass", cfg, hook_until=hook_vo.duration)
    endcard = make_endcard(cfg, work / "endcard.png")
    dest = out_dir / (reel_name or f"{slug}.mp4")
    render_reel(
        hook_src,
        app_src,
        voice.path,
        ass,
        endcard,
        dest,
        work,
        hook_vo.duration,
        body_vo.duration,
        cfg,
        music=music,
    )

    meta = {
        "file": dest.name,
        "pain_id": pain.id,
        "persona_id": persona.id,
        "hook": pain.hook,
        "spoken_hook": script.spoken_hook,
        "script": script.text,
        "source": script.source,
        "duration_s": round(voice.duration + cfg.endcard_seconds, 2),
        "structure": "hook-app-cierre",
        "music": music.name if music else None,
        "app": app_src.name if app_src else None,
        "cta": cfg.cta_url,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_reel_captions(out_dir, pain, script)
    print(f"  listo: {dest}")
    ig_dir = carousel_dir or (out_dir / "carrusel")
    clip = app_src if is_video(app_src) else None
    write_instagram_pack(cfg, ig_dir, pain, persona, script, app_clip=clip)
    print(f"  carrusel: {ig_dir}")
    return dest


def generate_day(
    cfg: Config,
    *,
    lucia_pain: str | None = None,
    pablo_pain: str | None = None,
    use_llm: bool = False,
) -> Path:
    """Pack de producción: Reel tiempo + Reel dinero + 2 carruseles + 2 stories."""
    lucia_id = lucia_pain or pick_unused_pain(money=False).id
    pablo_id = pablo_pain or pick_unused_pain(money=True).id

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest_root = cfg.ready_dir / f"{stamp}_pack"
    reel_t = dest_root / "01_reel_tiempo"
    reel_d = dest_root / "02_reel_dinero"
    car_t = dest_root / "03_carrusel_tiempo"
    car_d = dest_root / "04_carrusel_dinero"
    stories = dest_root / "05_stories"
    for folder in (reel_t, reel_d, car_t, car_d, stories):
        folder.mkdir(parents=True, exist_ok=True)

    print(f"\nPack de producción → {dest_root.name}")
    print("  01 Reel tiempo · 02 Reel dinero · 03-04 carruseles · 05 stories\n")

    generate_one(
        cfg,
        pain_id=lucia_id,
        persona_id="lucia",
        dest_dir=reel_t,
        carousel_dir=car_t,
        reel_name="reel.mp4",
        use_llm=use_llm,
    )
    generate_one(
        cfg,
        pain_id=pablo_id,
        persona_id="pablo",
        dest_dir=reel_d,
        carousel_dir=car_d,
        reel_name="reel.mp4",
        use_llm=use_llm,
    )
    write_stories_pack(cfg, stories, n=2)
    print(f"  stories: {stories}")
    write_publish_guide(dest_root, "01_reel_tiempo", "02_reel_dinero")
    mark_published([lucia_id, pablo_id])
    print(f"  guía: {dest_root / 'COMO_PUBLICAR.txt'}")
    print(f"\nTodo en {dest_root}")
    return dest_root


def clean_ready(cfg: Config) -> int:
    n = 0
    cfg.ready_dir.mkdir(parents=True, exist_ok=True)
    for path in list(cfg.ready_dir.iterdir()):
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        n += 1
    print(f"Limpio: {n} archivos/carpetas en {cfg.ready_dir}")
    return n
