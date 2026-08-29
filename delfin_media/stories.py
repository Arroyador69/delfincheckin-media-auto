from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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


def make_story_card(cfg: Config, story: dict) -> Image.Image:
    brand = load_yaml("brand.yaml")
    navy = _hex(brand["navy"])
    teal = _hex(brand["teal"])
    yellow = _hex(brand["yellow"])
    white = _hex(brand["white"])
    w, h = cfg.width, cfg.height
    img = Image.new("RGB", (w, h), navy)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 24), fill=teal)
    draw.rectangle((0, h - 24, w, h), fill=teal)

    logo_path = ROOT / brand["logo"]
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA").resize((160, 160), Image.Resampling.LANCZOS)
        img.paste(logo, ((w - 160) // 2, 220), logo)

    font_k = ImageFont.truetype(str(cfg.font_bold), 36)
    font_p = ImageFont.truetype(str(cfg.font_bold), 72)
    font_c = ImageFont.truetype(str(cfg.font_regular), 38)
    font_u = ImageFont.truetype(str(cfg.font_bold), 44)
    cx = w // 2

    def center(text: str, y: int, font, fill) -> int:
        box = draw.textbbox((0, 0), text, font=font)
        tw = box[2] - box[0]
        draw.text((cx - tw / 2, y), text, font=font, fill=fill)
        return box[3] - box[1]

    kicker = str(story.get("kicker") or "Recuerda")
    center(kicker.upper(), 430, font_k, yellow)
    y = 520
    for line in _wrap(draw, str(story["phrase"]), font_p, w - 140)[:4]:
        center(line, y, font_p, white)
        y += 92
    y += 36
    center(str(story.get("cta") or "Empieza gratis · sin tarjeta"), y, font_c, teal)
    center(cfg.cta_url, y + 80, font_u, yellow)
    return img


def write_stories_pack(cfg: Config, dest_dir: Path, n: int = 2) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    picked = pick_daily_stories(n)
    lines = [
        "STORIES · Instagram, Facebook, TikTok, YouTube",
        "Misma pieza 9:16 en las cuatro. Una frase + registro en la web.",
        "No explican el Reel. Mandan y recuerdan. CTA: delfincheckin.com",
        "",
    ]
    for i, story in enumerate(picked, start=1):
        img = make_story_card(cfg, story)
        jpg = dest_dir / f"0{i}-{story['id']}.jpg"
        mp4 = dest_dir / f"0{i}-{story['id']}.mp4"
        img.save(jpg, "JPEG", quality=92)
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
