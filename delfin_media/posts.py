from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from delfin_media.bank import pick_rooms
from delfin_media.config import Config, load_yaml
from delfin_media.paths import ROOT
from delfin_media.script import Pain, Persona, Script

SIZES = {
    "ig": (1080, 1350),
    "tt": (1080, 1920),
}


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


def _cover_crop(photo: Path, size: tuple[int, int]) -> Image.Image:
    w, h = size
    base = Image.open(photo).convert("RGB")
    bw, bh = base.size
    scale = max(w / bw, h / bh)
    base = base.resize((int(bw * scale), int(bh * scale)), Image.Resampling.LANCZOS)
    left = (base.width - w) // 2
    top = (base.height - h) // 2
    return base.crop((left, top, left + w, top + h))


def _rounded(im: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *im.size), radius=radius, fill=255)
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def solution_line(script: Script) -> str:
    text = script.text
    text = re.sub(r"(Empieza|Entra).*$", "", text, flags=re.I | re.S).strip()
    text = re.sub(r"delfincheckin\.com", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" .")
    words = text.split()
    if len(words) > 22:
        text = " ".join(words[:22]).rstrip(",;")
    if text and not text.endswith("."):
        text += "."
    return text or "El huésped rellena el parte. Delfín lo envía al Ministerio."


def make_carousel_card(
    cfg: Config,
    photo: Path,
    kicker: str,
    title: str,
    footer: str,
    size: tuple[int, int] = (1080, 1350),
) -> Image.Image:
    """Lienzo navy + foto inset + tarjeta de texto. Letras siempre legibles."""
    brand = _brand()
    navy = _hex(brand["navy"])
    teal = _hex(brand["teal"])
    yellow = _hex(brand["yellow"])
    white = _hex(brand["white"])
    card_bg = (16, 28, 48)
    w, h = size
    img = Image.new("RGB", (w, h), navy)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 16), fill=teal)

    logo_path = ROOT / brand["logo"]
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA").resize((88, 88), Image.Resampling.LANCZOS)
        img.paste(logo, (48, 40), logo)

    inset_h = 820 if h >= 1800 else 560
    inset_w = w - 96
    photo_im = _rounded(_cover_crop(photo, (inset_w, inset_h)), 28)
    canvas = img.convert("RGBA")
    canvas.paste(photo_im, (48, 148), photo_im)
    img = canvas.convert("RGB")
    draw = ImageDraw.Draw(img)

    card_top = 148 + inset_h + 28
    card_bot = h - 88
    draw.rounded_rectangle((48, card_top, w - 48, card_bot), radius=28, fill=card_bg)
    draw.rectangle((48, card_top, 64, card_bot), fill=teal)

    font_k = ImageFont.truetype(str(cfg.font_bold), 28)
    font_t = ImageFont.truetype(str(cfg.font_bold), 44 if h < 1800 else 48)
    font_f = ImageFont.truetype(str(cfg.font_regular), 26)
    font_url = ImageFont.truetype(str(cfg.font_bold), 26)
    x = 88
    y = card_top + 28
    draw.text((x, y), kicker.upper(), font=font_k, fill=yellow)
    y += 42
    max_lines = 4 if h >= 1800 else 3
    for line in _wrap(draw, title, font_t, w - 176)[:max_lines]:
        draw.text((x, y), line, font=font_t, fill=white)
        y += 52
    draw.text((x, card_bot - 48), footer, font=font_f, fill=teal)
    draw.text((48, h - 56), "delfincheckin.com", font=font_url, fill=yellow)
    return img


def carousel_slides(pain: Pain, persona: Persona, script: Script, cfg: Config) -> list[tuple[str, str, str]]:
    return [
        (f"{persona.name} · {persona.city}", pain.spoken_hook, "El dolor de este Reel"),
        ("En este vídeo", solution_line(script), "Delfín Check-in"),
        ("Empieza", "Una propiedad gratis. Sin tarjeta.", cfg.cta_url),
    ]


def write_instagram_pack(
    cfg: Config,
    dest_dir: Path,
    pain: Pain,
    persona: Persona,
    script: Script,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    rooms = pick_rooms(3)
    slides = carousel_slides(pain, persona, script, cfg)
    for i, ((kicker, title, footer), photo) in enumerate(zip(slides, rooms), start=1):
        ig = make_carousel_card(cfg, photo, kicker, title, footer, SIZES["ig"])
        ig.save(dest_dir / f"0{i}-carousel.jpg", "JPEG", quality=90)
        tt = make_carousel_card(cfg, photo, kicker, title, footer, SIZES["tt"])
        tt.save(dest_dir / f"0{i}-tiktok.jpg", "JPEG", quality=90)
    (dest_dir / "CAPTION_INSTAGRAM_FACEBOOK.txt").write_text(
        _caption(pain, persona, script, "ig"), encoding="utf-8"
    )
    (dest_dir / "CAPTION_TIKTOK.txt").write_text(
        _caption(pain, persona, script, "tiktok"), encoding="utf-8"
    )
    (dest_dir / "CAPTION_YOUTUBE.txt").write_text(
        _caption(pain, persona, script, "youtube"), encoding="utf-8"
    )
    return dest_dir


def _caption(pain: Pain, persona: Persona, script: Script, platform: str) -> str:
    body = (
        f"{pain.spoken_hook}\n\n"
        f"{script.text}\n\n"
        "Una propiedad gratis, sin tarjeta.\n"
        "delfincheckin.com\n"
    )
    if platform == "tiktok":
        tags = "#DelfinCheckin #AlquilerVacacional #CheckInDigital #ParteDeViajeros"
    elif platform == "youtube":
        tags = "Check-in digital y parte de viajeros. Empieza en delfincheckin.com"
    else:
        tags = (
            "#DelfinCheckin #ParteDeViajeros #AlquilerVacacional "
            "#RD933 #CheckInDigital #AlojamientoTuristico"
        )
    return f"{persona.name} · {persona.city}\n\n{body}\n{tags}\n"


def write_publish_guide(
    dest_dir: Path,
    lucia_slug: str,
    pablo_slug: str,
) -> Path:
    text = f"""PACK DEL DÍA · Delfín Check-in
Instagram · Facebook · TikTok · YouTube Shorts / Stories

1) REELS / SHORTS / TIKTOK (9:16)
   - {lucia_slug}.mp4  → Lucía
   - {pablo_slug}.mp4  → Pablo
   Misma pieza en Instagram Reels, Facebook Reels, TikTok y YouTube Shorts.

2) CARRUSEL (uno por vídeo, explica ESE Reel)
   - {lucia_slug}_ig/  01-03-carousel.jpg = Instagram y Facebook (1080×1350)
                         01-03-tiktok.jpg  = TikTok y YouTube (1080×1920)
   - {pablo_slug}_ig/  igual, de Pablo
   Sube las 3 fotos en orden. Caption en CAPTION_*.txt

3) STORIES (2, solo recuerdan + registro)
   - stories/01-*.jpg o .mp4
   - stories/02-*.jpg o .mp4
   Instagram, Facebook, TikTok y YouTube. Frase + delfincheckin.com
   No explican el vídeo. Mandan a registrarse (una propiedad gratis, sin tarjeta).

No publiques a ciegas: mira el MP4 y las fotos antes de subir.
"""
    path = dest_dir / "COMO_PUBLICAR.txt"
    path.write_text(text, encoding="utf-8")
    return path
