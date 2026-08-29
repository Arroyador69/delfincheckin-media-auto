from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import edge_tts

from delfin_media.config import Config
from delfin_media.script import Persona

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_SWEETEN = (
    "highpass=f=80,lowpass=f=13000,"
    "acompressor=threshold=-20dB:ratio=2.2:attack=15:release=200:makeup=2,"
    "volume=1.06"
)


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


def _fallbacks(persona: Persona, cfg: Config) -> list[tuple[str, str, str]]:
    primary = _voice_settings(persona, cfg)
    extras = (
        [
            ("es-ES-XimenaNeural", "-3%", "+0Hz"),
            ("es-ES-ElviraNeural", "-4%", "+0Hz"),
        ]
        if persona.voice == "female"
        else [
            ("es-ES-AlvaroNeural", "-2%", "+0Hz"),
        ]
    )
    seen = {primary[0]}
    out = [primary]
    for item in extras:
        if item[0] not in seen:
            out.append(item)
            seen.add(item[0])
    return out


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


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE.split(text.strip()) if p.strip()]
    return parts or [text.strip()]


async def _synthesize(
    text: str, voice: str, dest: Path, rate: str, pitch: str, volume: str
) -> list[Word]:
    communicate = edge_tts.Communicate(
        text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
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
    if not audio:
        raise RuntimeError(f"sin audio ({voice})")
    dest.write_bytes(bytes(audio))
    return words


async def _synthesize_fallback(
    text: str,
    dest: Path,
    persona: Persona,
    cfg: Config,
    pitch_override: str | None = None,
) -> list[Word]:
    last_err: Exception | None = None
    for voice, rate, pitch in _fallbacks(persona, cfg):
        use_pitch = pitch_override if pitch_override is not None else pitch
        try:
            return await _synthesize(
                text, voice, dest, rate, use_pitch, cfg.voice_volume
            )
        except Exception as exc:
            last_err = exc
            if dest.exists():
                dest.unlink()
    raise RuntimeError(f"TTS falló: {last_err}")


def _concat_audio(parts: list[Voiceover], dest: Path, pause: float) -> Voiceover:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if len(parts) == 1 and pause <= 0:
        dest.write_bytes(parts[0].path.read_bytes())
        return Voiceover(
            path=dest, duration=parts[0].duration, words=list(parts[0].words)
        )
    inputs: list[str] = []
    for part in parts:
        inputs += ["-i", str(part.path)]
    n = len(parts)
    filters: list[str] = []
    labels: list[str] = []
    for i in range(n):
        if i < n - 1 and pause > 0:
            filters.append(f"[{i}:a]apad=pad_dur={pause:.3f}[a{i}]")
            labels.append(f"[a{i}]")
        else:
            labels.append(f"[{i}:a]")
    filters.append(f"{''.join(labels)}concat=n={n}:v=0:a=1[a]")
    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[a]",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1500:] or proc.stdout[-1500:])
    words: list[Word] = []
    offset = 0.0
    for i, part in enumerate(parts):
        for w in part.words:
            words.append(Word(text=w.text, start=w.start + offset, end=w.end + offset))
        offset += part.duration
        if i < n - 1:
            offset += pause
    duration = _probe_duration(dest)
    return Voiceover(path=dest, duration=duration, words=words)


def concat_voiceovers(parts: list[Voiceover], dest: Path) -> Voiceover:
    return _concat_audio(parts, dest, pause=0.08)


def _sweeten(src: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-af",
        _SWEETEN,
        "-c:a",
        "libmp3lame",
        "-q:a",
        "4",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        dest.write_bytes(src.read_bytes())


def speak(text: str, persona: Persona, dest: Path, cfg: Config) -> Voiceover:
    dest.parent.mkdir(parents=True, exist_ok=True)
    sentences = split_sentences(text)

    async def _all() -> list[Voiceover]:
        out: list[Voiceover] = []
        for i, sent in enumerate(sentences):
            piece = dest.parent / f"{dest.stem}_s{i}.mp3"
            pitch = "+2Hz" if sent.endswith("?") else None
            words = await _synthesize_fallback(
                sent, piece, persona, cfg, pitch_override=pitch
            )
            duration = _probe_duration(piece)
            if not words:
                words = _fallback_words(sent, duration)
            out.append(Voiceover(path=piece, duration=duration, words=words))
        return out

    pieces = asyncio.run(_all())
    raw = dest.with_name(dest.stem + "_raw.mp3")
    combined = _concat_audio(pieces, raw, pause=0.18 if len(pieces) > 1 else 0.0)
    _sweeten(combined.path, dest)
    duration = _probe_duration(dest)
    return Voiceover(path=dest, duration=duration + 0.12, words=combined.words)
