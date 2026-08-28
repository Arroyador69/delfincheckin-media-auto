from __future__ import annotations

import argparse
import subprocess
import sys

from delfin_media.config import load_config
from delfin_media.doctor import run_doctor
from delfin_media.pipeline import generate_one
from delfin_media.script import load_pains, load_personas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="delfin-media",
        description="Reels de Delfín Check-in: dolores de propietarios, en local.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    doc = sub.add_parser("doctor", help="Comprueba Python, ffmpeg y dependencias")
    doc.add_argument("--ci", action="store_true", help="modo GitHub Actions")

    gen = sub.add_parser("generate", help="Crea uno o varios vídeos en output/ready")
    gen.add_argument("--count", type=int, default=1)
    gen.add_argument("--pain", help="id del dolor (ver list)")
    gen.add_argument("--persona", help="lucia | carlos | marta | pablo")
    gen.add_argument("--money", action="store_true", help="solo ángulos de dinero")
    gen.add_argument(
        "--llm",
        action="store_true",
        help="intenta Ollama (no recomendado en 8 GB)",
    )

    sub.add_parser("list", help="Lista dolores y personas")
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

    if args.cmd == "open":
        cfg.ready_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(cfg.ready_dir)], check=False)
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
        subprocess.run(["open", str(cfg.ready_dir)], check=False)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
