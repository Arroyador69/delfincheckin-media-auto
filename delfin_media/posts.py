from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from delfin_media.config import Config, load_yaml
from delfin_media.paths import ROOT
from delfin_media.script import Pain, Persona, Script


def _hex(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _brand() -> dict:
    return load_yaml("brand.yaml")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = (cur + " " + word).strip()
        box = draw.textbbox((0, 0), trial, font=font)
        if box[2] - box[0] <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _paste_logo(canvas: Image.Image, size: int = 92) -> None:
    path = ROOT / _brand()["logo"]
    if not path.exists():
        return
    logo = Image.open(path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    canvas.paste(logo, (48, 48), logo)


def _slide(
    cfg: Config, kicker: str, title: str, footer: str, size: tuple[int, int]
) -> Image.Image:
    brand = _brand()
    navy = _hex(brand["navy"])
    teal = _hex(brand["teal"])
    yellow = _hex(brand["yellow"])
    white = _hex(brand["white"])
    img = Image.new("RGB", size, navy)
    draw = ImageDraw.Draw(img)
    w, h = size
    draw.rectangle((0, 0, w, 18), fill=teal)
    draw.rectangle((0, h - 18, w, h), fill=teal)
    _paste_logo(img)
    font_k = ImageFont.truetype(str(cfg.font_bold), 28)
    font_t = ImageFont.truetype(str(cfg.font_bold), 72 if size[1] > 1400 else 64)
    font_f = ImageFont.truetype(str(cfg.font_regular), 32)
    draw.text((56, 180), kicker.upper(), font=font_k, fill=yellow)
    y = 240
    for line in _wrap(draw, title, font_t, w - 112):
        draw.text((56, y), line, font=font_t, fill=white)
        y += 78
    draw.text((56, h - 120), footer, font=font_f, fill=teal)
    return img


def _caption(pain: Pain, script: Script) -> str:
    return (
        f"{pain.hook}.\n\n"
        f"{script.text}\n\n"
        "Una propiedad gratis, sin tarjeta.\n"
        "delfincheckin.com\n\n"
        "Publicar en Instagram y Facebook. No en TikTok ni YouTube.\n\n"
        "#DelfinCheckin #ParteDeViajeros #AlquilerVacacional "
        "#RD933 #CheckInDigital #AlojamientoTuristico"
    )


def write_instagram_pack(
    cfg: Config,
    dest_dir: Path,
    pain: Pain,
    persona: Persona,
    script: Script,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    product = load_yaml("product.yaml")
    answer = (
        "El huésped rellena el parte antes. Delfín Check-in lo envía al Ministerio."
        if not pain.money_angle
        else "Microsite, pago directo y reseñas Google. Más margen, menos comisión."
    )
    slides = [
        ("Dolor", pain.hook, persona.name),
        ("Qué hace", answer, product["plans"]["checkin"]["price"]),
        ("Empieza", "Una propiedad gratis. Sin tarjeta. delfincheckin.com", cfg.cta_url),
    ]
    for i, (kicker, title, footer) in enumerate(slides, start=1):
        img = _slide(cfg, kicker, title, footer, (1080, 1350))
        img.save(dest_dir / f"0{i}-carousel.jpg", "JPEG", quality=88)
    (dest_dir / "CAPTION_INSTAGRAM_FACEBOOK.txt").write_text(
        _caption(pain, script), encoding="utf-8"
    )
    return dest_dir


def make_reel_slides(
    cfg: Config, dest_dir: Path, pain: Pain, persona: Persona
) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    product = load_yaml("product.yaml")
    answer = (
        "El huésped rellena el parte antes. Se envía solo al Ministerio."
        if not pain.money_angle
        else "Microsite y pago directo. Más margen, menos comisión de Airbnb."
    )
    slides = [
        ("Dolor", pain.hook, persona.name),
        ("Delfín Check-in", answer, product["plans"]["checkin"]["price"]),
        ("Empieza gratis", "Una propiedad. Sin tarjeta. delfincheckin.com", cfg.cta_url),
    ]
    paths: list[Path] = []
    for i, (kicker, title, footer) in enumerate(slides, start=1):
        img = _slide(cfg, kicker, title, footer, (cfg.width, cfg.height))
        path = dest_dir / f"reel_{i}.jpg"
        img.save(path, "JPEG", quality=90)
        paths.append(path)
    return paths
