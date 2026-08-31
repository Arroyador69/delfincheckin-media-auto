from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from delfin_media.bank import pick_rooms
from delfin_media.config import Config, load_yaml
from delfin_media.paths import ROOT
from delfin_media.render import render_still_video


def _hex(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


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


def load_stories() -> list[dict]:
    return list(load_yaml("stories.yaml")["stories"])


def pick_daily_stories(n: int = 2) -> list[dict]:
    items = load_stories()
    recuerda = [s for s in items if s.get("kind") == "recuerda"]
    registro = [s for s in items if s.get("kind") == "registro"]
    chosen: list[dict] = []
    if recuerda:
        chosen.append(random.choice(recuerda))
    if registro and len(chosen) < n:
        chosen.append(random.choice(registro))
    while len(chosen) < n and items:
        extra = random.choice(items)
        if extra not in chosen:
            chosen.append(extra)
        else:
            break
    return chosen[:n]


def make_story_card(cfg: Config, story: dict, photo: Path | None = None) -> Image.Image:
    brand = load_yaml("brand.yaml")
    navy = _hex(brand["navy"])
    teal = _hex(brand["teal"])
    yellow = _hex(brand["yellow"])
    white = _hex(brand["white"])
    w, h = cfg.width, cfg.height

    if photo and photo.exists():
        bg = _cover_crop(photo, (w, h)).convert("RGBA")
        veil = Image.new("RGBA", (w, h), (*navy, 214))
        img = Image.alpha_composite(bg, veil).convert("RGB")
    else:
        img = Image.new("RGB", (w, h), navy)

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 18), fill=teal)
    draw.rectangle((0, 18, w, 30), fill=yellow)
    draw.rectangle((0, h - 18, w, h), fill=teal)

    logo_path = ROOT / brand["logo"]
    logo_s = 176
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA").resize((logo_s, logo_s), Image.Resampling.LANCZOS)
        img.paste(logo, ((w - logo_s) // 2, 64), logo)

    font_k = ImageFont.truetype(str(cfg.font_bold), 32)
    font_p = ImageFont.truetype(str(cfg.font_bold), 70)
    font_c = ImageFont.truetype(str(cfg.font_bold), 34)
    font_u = ImageFont.truetype(str(cfg.font_bold), 42)
    cx = w // 2

    def center(text: str, y: int, font, fill) -> int:
        box = draw.textbbox((0, 0), text, font=font)
        tw = box[2] - box[0]
        th = box[3] - box[1]
        draw.text((cx - tw / 2, y), text, font=font, fill=fill)
        return th

    kicker = str(story.get("kicker") or "Recuerda").upper()
    k_box = draw.textbbox((0, 0), kicker, font=font_k)
    kw, kh = k_box[2] - k_box[0], k_box[3] - k_box[1]
    pill_w, pill_h = kw + 56, kh + 28
    px, py = (w - pill_w) // 2, 268
    draw.rounded_rectangle((px, py, px + pill_w, py + pill_h), radius=22, fill=yellow)
    draw.text((px + 28, py + 10), kicker, font=font_k, fill=navy)

    y = 390
    for line in _wrap(draw, str(story["phrase"]), font_p, w - 120)[:4]:
        center(line, y, font_p, white)
        y += 88

    plate_top = h - 280
    draw.rounded_rectangle((56, plate_top, w - 56, h - 72), radius=32, fill=yellow)
    draw.rectangle((56, plate_top, 72, h - 72), fill=teal)
    cta = str(story.get("cta") or "Empieza gratis · sin tarjeta")
    center(cta, plate_top + 44, font_c, navy)
    if cfg.cta_url.lower() in cta.lower():
        center("Una propiedad · sin tarjeta", plate_top + 112, font_u, navy)
    else:
        center(cfg.cta_url, plate_top + 112, font_u, navy)
    return img


def write_stories_pack(cfg: Config, dest_dir: Path, n: int = 2) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for old in dest_dir.iterdir():
        if old.is_file():
            old.unlink()
    picked = pick_daily_stories(n)
    rooms = pick_rooms(max(n, 2))
    lines = [
        "STORIES · Instagram, Facebook, TikTok, YouTube",
        "Misma pieza 9:16 en las cuatro. Una frase + registro en la web.",
        "No explican el Reel. Mandan y recuerdan. CTA: delfincheckin.com",
        "",
    ]
    for i, story in enumerate(picked, start=1):
        photo = rooms[(i - 1) % len(rooms)] if rooms else None
        img = make_story_card(cfg, story, photo)
        jpg = dest_dir / f"0{i}-{story['id']}.jpg"
        mp4 = dest_dir / f"0{i}-{story['id']}.mp4"
        img.save(jpg, "JPEG", quality=93)
        render_still_video(jpg, mp4, cfg.story_seconds, cfg)
        cta = str(story.get("cta") or "Empieza gratis · sin tarjeta")
        extra = cta if cfg.cta_url.lower() in cta.lower() else f"{cta} · {cfg.cta_url}"
        lines.append(f"{jpg.name} / {mp4.name}")
        lines.append(f"  {story['phrase']}")
        lines.append(f"  {extra}")
        lines.append("")
    lines.append("Texto para pegar:")
    lines.append(f"{picked[0]['phrase']} {cfg.cta_url}")
    (dest_dir / "CAPTION_STORIES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest_dir
