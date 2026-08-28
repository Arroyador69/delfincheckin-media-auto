from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path

import edge_tts

from delfin_media.config import Config
from delfin_media.script import Persona


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Voiceover:
    path: Path
    duration: float
    words: list[Word]


def _voice_settings(persona: Persona, cfg: Config) -> tuple[str, str, str]:
    if persona.voice == "female":
        return cfg.voice_female, cfg.voice_female_rate, cfg.voice_female_pitch
    return cfg.voice_male, cfg.voice_male_rate, cfg.voice_male_pitch


def _probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    )
    return float(out.strip())


def _fallback_words(text: str, duration: float) -> list[Word]:
    tokens = [t for t in text.replace("\n", " ").split(" ") if t]
    if not tokens:
        return []
    slot = duration / len(tokens)
    words: list[Word] = []
    t = 0.12
    for token in tokens:
        words.append(Word(text=token, start=t, end=t + slot * 0.9))
        t += slot
    return words


async def _synthesize(
    text: str, voice: str, dest: Path, rate: str, pitch: str
) -> list[Word]:
    communicate = edge_tts.Communicate(
        text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        boundary="WordBoundary",
    )
    audio = bytearray()
    words: list[Word] = []
    async for chunk in communicate.stream():
        kind = chunk.get("type")
        if kind == "audio":
            audio.extend(chunk["data"])
        elif kind == "WordBoundary":
            start = chunk["offset"] / 10_000_000
            dur = chunk["duration"] / 10_000_000
            words.append(Word(text=chunk["text"], start=start, end=start + dur))
    dest.write_bytes(bytes(audio))
    return words


def speak(text: str, persona: Persona, dest: Path, cfg: Config) -> Voiceover:
    dest.parent.mkdir(parents=True, exist_ok=True)
    voice, rate, pitch = _voice_settings(persona, cfg)
    words = asyncio.run(_synthesize(text, voice, dest, rate, pitch))
    duration = _probe_duration(dest)
    if not words:
        words = _fallback_words(text, duration)
    return Voiceover(path=dest, duration=duration + 0.25, words=words)
