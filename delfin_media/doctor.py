from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from delfin_media.config import Config
from delfin_media.paths import ROOT
from delfin_media.script import load_pains, load_personas, validate_script


def _ram_gb() -> float | None:
    try:
        raw = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        return int(raw) / (1024**3)
    except Exception:
        return None


def check_scripts(cfg: Config) -> int:
    bad = 0
    for pain in load_pains():
        for script in pain.scripts:
            errors = validate_script(script, cfg, spoken_hook=pain.spoken_hook)
            if errors:
                bad += 1
                print(f"  ERROR guion {pain.id}: {errors}")
    personas = load_personas()
    if len(personas) < 2:
        print("  ERROR: hacen falta al menos 2 personas")
        bad += 1
    for persona in personas:
        if len(persona.poses) < 3:
            print(f"  ERROR {persona.id}: mínimo 3 poses para movimiento")
            bad += 1
    from delfin_media.stories import load_stories

    if len(load_stories()) < 2:
        print("  ERROR: hacen falta al menos 2 stories en data/stories.yaml")
        bad += 1
    return bad


def run_doctor(cfg: Config, ci: bool = False) -> int:
    print("Delfín Check-in · doctor")
    print(f"  proyecto: {ROOT}")
    ok = True

    py = sys.version.split()[0]
    print(f"  python: {py}")
    if sys.version_info < (3, 11):
        print("  ERROR: hace falta Python 3.11+")
        ok = False

    ffmpeg = shutil.which("ffmpeg")
    print(f"  ffmpeg: {ffmpeg or 'NO'}")
    if not ffmpeg and not ci:
        print("  ERROR: brew install ffmpeg")
        ok = False

    for name in ("edge_tts", "httpx", "PIL", "yaml"):
        try:
            __import__("PIL" if name == "PIL" else name)
            print(f"  {name}: ok")
        except ImportError:
            print(f"  ERROR: falta {name}. pip install -r requirements.txt")
            ok = False

    if not ci:
        for font in (cfg.font_bold, cfg.font_regular):
            exists = Path(font).exists()
            print(f"  fuente {font.name}: {'ok' if exists else 'NO'}")
            if not exists:
                ok = False
        ram = _ram_gb()
        if ram is not None:
            print(f"  RAM: {ram:.1f} GB")
            if ram < 12:
                print("  aviso: 8 GB. Hook 3s + app + cierre. No Flux ni vídeo IA local.")

    bank_yaml = ROOT / "data" / "bank.yaml"
    stories_yaml = ROOT / "data" / "stories.yaml"
    print(f"  banco yaml: {'ok' if bank_yaml.exists() else 'NO'}")
    print(f"  stories yaml: {'ok' if stories_yaml.exists() else 'NO'}")
    if not bank_yaml.exists() or not stories_yaml.exists():
        ok = False
    if not ci:
        rooms = list((ROOT / "assets" / "bank" / "rooms").glob("*.jpg"))
        people = list((ROOT / "assets" / "bank" / "people").glob("*.jpg"))
        hooks = list((ROOT / "assets" / "bank" / "hooks").glob("*.jpg"))
        hook_vids = list((ROOT / "assets" / "bank" / "hooks").glob("*.mp4"))
        apps = [
            p
            for p in (ROOT / "assets" / "bank" / "app").iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".m4v"}
        ]
        print(f"  banco fotos: {len(rooms)} habitaciones, {len(people)} personas, {len(hooks)} hooks")
        print(f"  hook vídeos: {len(hook_vids)}")
        print(f"  app MP4: {len(apps)} (pega clips en assets/bank/app/)")
        if len(rooms) < 3 or len(hooks) < 2:
            print("  aviso: python -m delfin_media bank")

    script_errors = check_scripts(cfg)
    print(f"  guiones: {'ok' if script_errors == 0 else script_errors}")
    if script_errors:
        ok = False

    cfg.ready_dir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"  salida: {cfg.ready_dir}")
    print("  listo" if ok else "  hay errores")
    return 0 if ok else 1
