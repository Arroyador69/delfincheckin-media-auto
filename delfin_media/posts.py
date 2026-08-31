from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from delfin_media.bank import is_video, pick_rooms
from delfin_media.config import Config, load_yaml
from delfin_media.paths import ROOT
from delfin_media.render import grab_video_frame
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


def _fit_pad(photo: Path, size: tuple[int, int], bg: tuple[int, int, int]) -> Image.Image:
    """La UI de la app cabe entera, sin recortar el móvil."""
    w, h = size
    base = Image.open(photo).convert("RGB")
    bw, bh = base.size
    scale = min(w / bw, h / bh)
    nw, nh = max(1, int(bw * scale)), max(1, int(bh * scale))
    base = base.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (w, h), bg)
    canvas.paste(base, ((w - nw) // 2, (h - nh) // 2))
    return canvas


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
    if len(words) > 28:
        text = " ".join(words[:28]).rstrip(",;")
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
    fit: str = "cover",
) -> Image.Image:
    """Carrusel de marca: navy, teal, amarillo, logo y foto (habitación o app)."""
    brand = _brand()
    navy = _hex(brand["navy"])
    teal = _hex(brand["teal"])
    yellow = _hex(brand["yellow"])
    white = _hex(brand["white"])
    cyan = _hex(brand.get("cyan", "#44C0FF"))
    card_bg = (14, 26, 46)
    w, h = size
    img = Image.new("RGB", (w, h), navy)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 16), fill=teal)
    draw.rectangle((0, 16, w, 26), fill=yellow)

    logo_path = ROOT / brand["logo"]
    logo_s = 108
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA").resize((logo_s, logo_s), Image.Resampling.LANCZOS)
        img.paste(logo, (40, 40), logo)

    inset_h = 900 if h >= 1800 else 560
    inset_w = w - 96
    photo_y = 168
    draw.rounded_rectangle(
        (44, photo_y - 6, 44 + inset_w + 8, photo_y + inset_h + 6),
        radius=34,
        fill=teal,
    )
    if fit == "contain":
        photo_im = _rounded(_fit_pad(photo, (inset_w, inset_h), navy), 28)
    else:
        photo_im = _rounded(_cover_crop(photo, (inset_w, inset_h)), 28)
    canvas = img.convert("RGBA")
    canvas.paste(photo_im, (48, photo_y), photo_im)
    img = canvas.convert("RGB")
    draw = ImageDraw.Draw(img)

    footer_h = 78
    card_top = photo_y + inset_h + 28
    card_bot = h - footer_h - 20
    draw.rounded_rectangle((48, card_top, w - 48, card_bot), radius=28, fill=card_bg)
    draw.rectangle((48, card_top, 62, card_bot), fill=yellow)
    draw.rectangle((62, card_top, 70, card_bot), fill=teal)

    font_k = ImageFont.truetype(str(cfg.font_bold), 28)
    font_t = ImageFont.truetype(str(cfg.font_bold), 44 if h < 1800 else 50)
    font_f = ImageFont.truetype(str(cfg.font_regular), 26)
    font_url = ImageFont.truetype(str(cfg.font_bold), 32)
    x = 92
    y = card_top + 28
    draw.text((x, y), kicker.upper(), font=font_k, fill=yellow)
    y += 44
    max_lines = 4 if h >= 1800 else 3
    for line in _wrap(draw, title, font_t, w - 188)[:max_lines]:
        draw.text((x, y), line, font=font_t, fill=white)
        y += 54
    draw.text((x, card_bot - 48), footer, font=font_f, fill=cyan)

    draw.rectangle((0, h - footer_h, w, h), fill=yellow)
    url_box = draw.textbbox((0, 0), "delfincheckin.com", font=font_url)
    url_w = url_box[2] - url_box[0]
    draw.text(((w - url_w) / 2, h - 54), "delfincheckin.com", font=font_url, fill=navy)
    return img


def carousel_slides(pain: Pain, persona: Persona, script: Script, cfg: Config) -> list[tuple[str, str, str]]:
    return [
        ("Delfín Check-in", pain.spoken_hook, "El dolor de este Reel"),
        ("En este vídeo", solution_line(script), "Así se ve Delfín Check-in"),
        ("Empieza", "Una propiedad gratis. Sin tarjeta.", cfg.cta_url),
    ]


def _carousel_photos(dest_dir: Path, app_clip: Path | None) -> tuple[list[Path], bool]:
    rooms = pick_rooms(3)
    photos = list(rooms)
    used_app = False
    if app_clip is None or not is_video(app_clip):
        return photos, used_app
    frame = dest_dir.parent / f".{dest_dir.name}_app.jpg"
    try:
        grab_video_frame(app_clip, frame, at=2.0)
        photos[1] = frame
        used_app = True
    except Exception as exc:
        print(f"  aviso: no se pudo sacar fotograma de la app: {exc}")
    return photos, used_app


def write_instagram_pack(
    cfg: Config,
    dest_dir: Path,
    pain: Pain,
    persona: Persona,
    script: Script,
    app_clip: Path | None = None,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    photos, used_app = _carousel_photos(dest_dir, app_clip)
    slides = carousel_slides(pain, persona, script, cfg)
    for i, ((kicker, title, footer), photo) in enumerate(zip(slides, photos), start=1):
        fit = "contain" if i == 2 and used_app else "cover"
        ig = make_carousel_card(cfg, photo, kicker, title, footer, SIZES["ig"], fit=fit)
        ig.save(dest_dir / f"0{i}-carousel.jpg", "JPEG", quality=92)
        tt = make_carousel_card(cfg, photo, kicker, title, footer, SIZES["tt"], fit=fit)
        tt.save(dest_dir / f"0{i}-tiktok.jpg", "JPEG", quality=92)
    preview = dest_dir.parent / f".{dest_dir.name}_app.jpg"
    if preview.exists():
        preview.unlink()
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
    return f"{body}\n{tags}\n"


def write_publish_guide(
    dest_dir: Path,
    lucia_slug: str,
    pablo_slug: str,
) -> Path:
    text = f"""PACK DEL DÍA · Delfín Check-in
Instagram · Facebook · TikTok · YouTube Shorts / Stories

1) REELS / SHORTS / TIKTOK (9:16)
   - {lucia_slug}.mp4  → Reel 1 (tiempo / legal)
   - {pablo_slug}.mp4  → Reel 2 (dinero)
   Misma pieza en Instagram Reels, Facebook Reels, TikTok y YouTube Shorts.

2) CARRUSEL (uno por vídeo, explica ESE Reel)
   - {lucia_slug}_ig/  01-03-carousel.jpg = Instagram y Facebook (1080×1350)
                         01-03-tiktok.jpg  = TikTok y YouTube (1080×1920)
   - {pablo_slug}_ig/  igual, del Reel 2
   Sube las 3 fotos en orden. Caption en CAPTION_*.txt
   La foto 02 es un fotograma de la app de ese Reel.

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
