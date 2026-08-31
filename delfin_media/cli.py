from __future__ import annotations

import argparse
import subprocess
import sys

from delfin_media.config import load_config
from delfin_media.doctor import run_doctor
from delfin_media.pipeline import clean_ready, generate_day, generate_one
from delfin_media.script import load_pains, load_personas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="delfin-media",
        description="Pack diario de Delfín Check-in: Reels, carruseles y stories.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    doc = sub.add_parser("doctor", help="Comprueba Python, ffmpeg y dependencias")
    doc.add_argument("--ci", action="store_true", help="modo GitHub Actions")

    gen = sub.add_parser("generate", help="Crea un Reel + su carrusel")
    gen.add_argument("--count", type=int, default=1)
    gen.add_argument("--pain", help="id del dolor (ver list)")
    gen.add_argument("--persona", help="lucia | carlos | marta | pablo")
    gen.add_argument("--money", action="store_true", help="solo ángulos de dinero")
    gen.add_argument(
        "--llm",
        action="store_true",
        help="intenta Ollama (no recomendado en 8 GB)",
    )

    day = sub.add_parser(
        "day",
        help="Pack del día: Lucía + Pablo + 2 carruseles + 2 stories",
    )
    day.add_argument("--lucia-pain", help="dolor de Lucía (tiempo/legal)")
    day.add_argument("--pablo-pain", help="dolor de Pablo (dinero)")
    day.add_argument("--llm", action="store_true")

    sub.add_parser("list", help="Lista dolores y personas")
    sub.add_parser("bank", help="Baja el banco de fotos y clips de hook")
    sub.add_parser("clean", help="Borra output/ready para liberar espacio")
    sub.add_parser("open", help="Abre la carpeta output/ready en Finder")

    args = parser.parse_args(argv)
    cfg = load_config()

    if args.cmd == "doctor":
        return run_doctor(cfg, ci=args.ci)

    if args.cmd == "list":
        print("Dolores")
        for pain in load_pains():
            tag = "dinero" if pain.money_angle else "tiempo/legal"
            print(f"  {pain.id:24} [{tag}] {pain.hook}")
        print("Personas")
        for persona in load_personas():
            print(f"  {persona.id:24} {persona.name}, {persona.city}")
        return 0

    if args.cmd == "bank":
        from delfin_media.bank import BANK_DIR, sync_bank

        paths = sync_bank()
        print(f"{len(paths)} archivos en {BANK_DIR}")
        app_dir = BANK_DIR / "app"
        n_app = sum(
            1
            for p in app_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".m4v"}
        )
        print(f"App: {n_app} vídeos en {app_dir}")
        for clip in sorted(app_dir.iterdir(), key=lambda p: p.name.lower()):
            if clip.is_file() and clip.suffix.lower() in {".mp4", ".mov", ".m4v"}:
                print(f"  · {clip.name}")
        return 0

    if args.cmd == "clean":
        clean_ready(cfg)
        return 0

    if args.cmd == "open":
        cfg.ready_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(cfg.ready_dir)], check=False)
        return 0

    if args.cmd == "day":
        generate_day(
            cfg,
            lucia_pain=args.lucia_pain,
            pablo_pain=args.pablo_pain,
            use_llm=args.llm,
        )
        print("Para abrirlos: python -m delfin_media open")
        return 0

    if args.cmd == "generate":
        n = max(1, args.count)
        for i in range(n):
            print(f"\n[{i + 1}/{n}]")
            generate_one(
                cfg,
                pain_id=args.pain,
                persona_id=args.persona,
                money_only=args.money,
                use_llm=args.llm,
            )
        print(f"\nVídeos en {cfg.ready_dir}")
        print("Pack de producción (Reels + carruseles + stories): python -m delfin_media day")
        print("Para abrirlos: python -m delfin_media open")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
