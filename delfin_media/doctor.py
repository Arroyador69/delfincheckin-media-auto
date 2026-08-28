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
            errors = validate_script(script, cfg)
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
                print("  aviso: 8 GB. Movimiento con 3 tomas IA + cámara, no LTX local.")

    script_errors = check_scripts(cfg)
    print(f"  guiones: {'ok' if script_errors == 0 else script_errors}")
    if script_errors:
        ok = False

    cfg.ready_dir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"  salida: {cfg.ready_dir}")
    print("  listo" if ok else "  hay errores")
    return 0 if ok else 1
