from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from delfin_media.bank import pick_rooms
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


def overlay_photo(
    cfg: Config,
    photo: Path,
    kicker: str,
    title: str,
    footer: str,
    size: tuple[int, int],
) -> Image.Image:
    """Foto fija (habitación) + texto, logo y colores. No se convierte en vídeo."""
    brand = _brand()
    navy = _hex(brand["navy"])
    teal = _hex(brand["teal"])
    yellow = _hex(brand["yellow"])
    white = _hex(brand["white"])
    w, h = size
    base = Image.open(photo).convert("RGB")
    bw, bh = base.size
    scale = max(w / bw, h / bh)
    base = base.resize((int(bw * scale), int(bh * scale)), Image.Resampling.LANCZOS)
    left = (base.width - w) // 2
    top = (base.height - h) // 2
    img = base.crop((left, top, left + w, top + h))
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_s = ImageDraw.Draw(shade)
    for y in range(int(h * 0.42), h):
        a = int(210 * ((y - h * 0.42) / (h * 0.58)))
        draw_s.rectangle((0, y, w, y + 1), fill=(*navy, min(a, 220)))
    img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 14), fill=teal)
    _paste_logo(img, 80)
    font_k = ImageFont.truetype(str(cfg.font_bold), 26)
    font_t = ImageFont.truetype(str(cfg.font_bold), 52)
    font_f = ImageFont.truetype(str(cfg.font_regular), 28)
    y = int(h * 0.56)
    draw.text((48, y), kicker.upper(), font=font_k, fill=yellow)
    y += 42
    for line in _wrap(draw, title, font_t, w - 96)[:5]:
        draw.text((48, y), line, font=font_t, fill=white)
        y += 62
    draw.text((48, h - 88), footer, font=font_f, fill=teal)
    return img


def write_instagram_pack(
    cfg: Config,
    dest_dir: Path,
    pain: Pain,
    persona: Persona,
    script: Script,
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    product = load_yaml("product.yaml")
    rooms = pick_rooms(3)
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
    for i, ((kicker, title, footer), photo) in enumerate(zip(slides, rooms), start=1):
        img = overlay_photo(cfg, photo, kicker, title, footer, (1080, 1350))
        img.save(dest_dir / f"0{i}-carousel.jpg", "JPEG", quality=88)
    (dest_dir / "CAPTION_INSTAGRAM_FACEBOOK.txt").write_text(
        _caption(pain, script), encoding="utf-8"
    )
    return dest_dir


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
