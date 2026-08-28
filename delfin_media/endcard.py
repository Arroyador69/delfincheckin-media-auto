from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from delfin_media.config import Config, load_yaml
from delfin_media.paths import ROOT


def _hex(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def make_endcard(cfg: Config, dest: Path, line: str) -> Path:
    brand = load_yaml("brand.yaml")
    teal = _hex(brand["teal"])
    navy = _hex(brand["navy"])
    white = _hex(brand["white"])
    yellow = _hex(brand["yellow"])
    img = Image.new("RGB", (cfg.width, cfg.height), teal)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, cfg.width, 24), fill=navy)
    draw.rectangle((0, cfg.height - 24, cfg.width, cfg.height), fill=navy)
    logo_path = ROOT / brand["logo"]
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA").resize((280, 280), Image.Resampling.LANCZOS)
        img.paste(logo, ((cfg.width - 280) // 2, 620), logo)
    title = ImageFont.truetype(str(cfg.font_bold), 64)
    url_font = ImageFont.truetype(str(cfg.font_bold), 48)
    small = ImageFont.truetype(str(cfg.font_regular), 34)
    cx = cfg.width // 2

    def center(text: str, y: int, font, fill):
        box = draw.textbbox((0, 0), text, font=font)
        w = box[2] - box[0]
        draw.text((cx - w / 2, y), text, font=font, fill=fill)

    center("Delfín Check-in", 940, title, white)
    center(cfg.cta_url, 1020, url_font, yellow)
    center(line[:48], 1120, small, white)
    center("Empieza gratis · sin tarjeta", 1188, small, white)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "PNG")
    return dest
