from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from delfin_media.paths import ROOT


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Config:
    brand: str
    cta_url: str
    cta_spoken: str
    width: int
    height: int
    fps: int
    subtitle_fontsize: int
    subtitle_margin_v: int
    voice_engine: str
    voice_language: str
    voice_pocket_female: str
    voice_pocket_male: str
    voice_azure_female: str
    voice_azure_male: str
    azure_speech_key: str
    azure_speech_region: str
    voice_female: str
    voice_female_rate: str
    voice_female_pitch: str
    voice_male: str
    voice_male_rate: str
    voice_male_pitch: str
    voice_volume: str
    story_seconds: float
    image_provider: str
    pollinations_model: str
    visual_mode: str
    min_words: int
    max_words: int
    endcard_seconds: float
    music_volume: float
    output_dir: Path
    cache_dir: Path
    font_bold: Path
    font_regular: Path
    ready_dir: Path
    work_dir: Path
    logs_dir: Path


def load_config(path: Path | None = None) -> Config:
    load_dotenv()
    cfg_path = path or (ROOT / "config.yaml")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    output = ROOT / raw["output_dir"]
    cache = ROOT / raw["cache_dir"]
    return Config(
        brand=raw["brand"],
        cta_url=raw["cta_url"],
        cta_spoken=raw["cta_spoken"],
        width=int(raw["width"]),
        height=int(raw["height"]),
        fps=int(raw["fps"]),
        subtitle_fontsize=int(raw["subtitle_fontsize"]),
        subtitle_margin_v=int(raw["subtitle_margin_v"]),
        voice_engine=str(raw.get("voice_engine", "edge")),
        voice_language=str(raw.get("voice_language", "spanish")),
        voice_pocket_female=str(raw.get("voice_pocket_female", "lola")),
        voice_pocket_male=str(raw.get("voice_pocket_male", "jean")),
        voice_azure_female=str(
            raw.get("voice_azure_female", "es-ES-Ximena:DragonHDLatestNeural")
        ),
        voice_azure_male=str(
            raw.get("voice_azure_male", "es-ES-Tristan:DragonHDLatestNeural")
        ),
        azure_speech_key=os.environ.get("AZURE_SPEECH_KEY", "").strip(),
        azure_speech_region=os.environ.get("AZURE_SPEECH_REGION", "westeurope").strip(),
        voice_female=raw["voice_female"],
        voice_female_rate=str(raw.get("voice_female_rate", "-3%")),
        voice_female_pitch=str(raw.get("voice_female_pitch", "+0Hz")),
        voice_male=raw["voice_male"],
        voice_male_rate=str(raw.get("voice_male_rate", "-2%")),
        voice_male_pitch=str(raw.get("voice_male_pitch", "+0Hz")),
        voice_volume=str(raw.get("voice_volume", "+0%")),
        story_seconds=float(raw.get("story_seconds", 5.5)),
        image_provider=raw["image_provider"],
        pollinations_model=raw["pollinations_model"],
        visual_mode=str(raw.get("visual_mode", "brand")),
        min_words=int(raw["min_words"]),
        max_words=int(raw["max_words"]),
        endcard_seconds=float(raw["endcard_seconds"]),
        music_volume=float(raw.get("music_volume", 0.06)),
        output_dir=output,
        cache_dir=cache,
        font_bold=Path(raw["font_bold"]),
        font_regular=Path(raw["font_regular"]),
        ready_dir=output / "ready",
        work_dir=output / "work",
        logs_dir=output / "logs",
    )


def load_yaml(rel: str) -> dict:
    from delfin_media.paths import data_path

    return yaml.safe_load(data_path(rel).read_text(encoding="utf-8"))
