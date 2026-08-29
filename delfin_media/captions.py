from __future__ import annotations

from pathlib import Path

from delfin_media.config import Config
from delfin_media.tts import Word


def _ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _chunk_words(words: list[Word], size: int = 3) -> list[list[Word]]:
    chunks: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        if current:
            prev = current[-1].text
            starts_sentence = word.text[:1].isupper() and prev[-1:].islower()
            if starts_sentence and len(current) >= 1:
                chunks.append(current)
                current = []
        current.append(word)
        punct = word.text.endswith((".", ",", "?", "!", ";", ":"))
        if len(current) >= size or punct:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def write_ass(
    words: list[Word], dest: Path, cfg: Config, hook_until: float = 0.0
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    hook_size = max(cfg.subtitle_fontsize + 16, 84)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {cfg.width}
PlayResY: {cfg.height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{cfg.subtitle_fontsize},&H0000D4FF,&H000000FF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,6,0,2,70,70,{cfg.subtitle_margin_v},1
Style: Hook,Arial,{hook_size},&H0000D4FF,&H000000FF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,7,0,2,50,50,{cfg.subtitle_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for chunk in _chunk_words(words):
        start = chunk[0].start
        end = max(chunk[-1].end, start + 0.35)
        text = " ".join(w.text.replace("\n", " ") for w in chunk)
        text = text.replace("{", "").replace("}", "")
        style = "Hook" if start < hook_until else "Default"
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,"
            f"{{\\fad(60,60)}}{text}\n"
        )
    dest.write_text("".join(lines), encoding="utf-8")
    return dest
