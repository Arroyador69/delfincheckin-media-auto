from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from delfin_media.config import Config
from delfin_media.script import Pain, Persona

_IBERIAN = (
    "HIGHEST PRIORITY ETHNICITY: native Spanish person from Spain, Iberian "
    "Southern European Mediterranean features, double eyelids, brown or hazel "
    "eyes, oval face, slightly aquiline nose, olive-tan skin of Andalusia or "
    "the Canary Islands, looks like a local from Málaga old town or Tenerife. "
    "FORBIDDEN: East Asian, Korean, Japanese, Chinese, Vietnamese, Thai, "
    "Filipino, Indonesian, monolid, epicanthic fold, K-pop face, anime, "
    "celebrity lookalike."
)


def _prompt(persona: Persona, pain: Pain, pose: str) -> str:
    return (
        f"{_IBERIAN} {pose}. {persona.image_prompt}. "
        f"Scene extra: {pain.image_extra}. "
        "Vertical 9:16 photoreal iPhone UGC, no text, no watermark, no logo."
    )


def _cache_path(cfg: Config, prompt: str, seed: int, idx: int) -> Path:
    digest = hashlib.sha256(f"{seed}:{idx}:{prompt}".encode()).hexdigest()[:16]
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    return cfg.cache_dir / f"shot_{persona_id_safe(seed)}_{idx}_{digest}.jpg"


def persona_id_safe(seed: int) -> str:
    return str(seed)


def _pollinations(prompt: str, dest: Path, cfg: Config, seed: int) -> bool:
    encoded = quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={cfg.width}&height={cfg.height}&nologo=true"
        f"&model={cfg.pollinations_model}&enhance=true&seed={seed}"
    )
    try:
        with httpx.Client(timeout=90.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "delfincheckin-media-auto/0.1"})
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            img = img.resize((cfg.width, cfg.height), Image.Resampling.LANCZOS)
            img.save(dest, "JPEG", quality=90)
            return True
    except Exception:
        return False


def _fallback_portrait(persona: Persona, dest: Path, cfg: Config) -> Path:
    img = Image.new("RGB", (cfg.width, cfg.height), (12, 42, 56))
    draw = ImageDraw.Draw(img)
    for y in range(cfg.height):
        t = y / cfg.height
        draw.line(
            [(0, y), (cfg.width, y)],
            fill=(int(12 + t * 18), int(42 + t * 30), int(56 + t * 40)),
        )
    font_lg = ImageFont.truetype(str(cfg.font_bold), 54)
    font_sm = ImageFont.truetype(str(cfg.font_regular), 32)
    draw.text((80, cfg.height * 0.62), persona.name, font=font_lg, fill=(255, 255, 255))
    draw.text(
        (80, cfg.height * 0.62 + 70),
        f"{persona.city} · {persona.role}",
        font=font_sm,
        fill=(210, 230, 235),
    )
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "JPEG", quality=90)
    return dest


def persona_shots(persona: Persona, pain: Pain, cfg: Config) -> list[Path]:
    shots: list[Path] = []
    poses = persona.poses or ("looking at camera",)
    for idx, pose in enumerate(poses):
        prompt = _prompt(persona, pain, pose)
        dest = _cache_path(cfg, prompt, persona.seed, idx)
        if dest.exists() and dest.stat().st_size > 8_000:
            shots.append(dest)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  imagen IA · {persona.name} · toma {idx + 1}/{len(poses)}")
        if cfg.image_provider == "pollinations" and _pollinations(
            prompt, dest, cfg, persona.seed
        ):
            shots.append(dest)
            continue
        print("  pollinations no respondió, uso still de marca")
        shots.append(_fallback_portrait(persona, dest, cfg))
    return shots
