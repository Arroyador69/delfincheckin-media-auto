from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from delfin_media.bank import is_video
from delfin_media.config import Config
from delfin_media.paths import ROOT


class RenderError(RuntimeError):
    pass


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(proc.stderr[-2000:] or proc.stdout[-2000:])


def _common_v(cfg: Config) -> list[str]:
    return [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(cfg.fps),
        "-crf",
        "19",
        "-preset",
        "veryfast",
    ]


def _common_a() -> list[str]:
    return ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]


def cover_9x16(cfg: Config) -> str:
    """Llena 9:16 recortando, sin estirar."""
    w, h = cfg.width, cfg.height
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={w}:{h},"
        f"eq=saturation=1.05:contrast=1.04,fps={cfg.fps},setsar=1,format=yuv420p"
    )


def kenburns_9x16(cfg: Config, duration: float) -> str:
    """Foto en movimiento: paneo lento a 9:16, sin estirar."""
    w, h = cfg.width, cfg.height
    dur = max(duration, 0.5)
    src_w, src_h = int(w * 1.22), int(h * 1.22)
    return (
        f"scale={src_w}:{src_h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={src_w}:{src_h},"
        f"crop={w}:{h}:(in_w-{w})*t/{dur:.3f}:(in_h-{h})*t/{dur:.3f}*0.45,"
        f"eq=saturation=1.05:contrast=1.04,fps={cfg.fps},setsar=1,format=yuv420p"
    )


def letterbox_9x16(cfg: Config) -> str:
    """Cabe entero en 9:16 con bandas navy. No deforma la app."""
    w, h = cfg.width, cfg.height
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x0B1220,"
        f"fps={cfg.fps},setsar=1,format=yuv420p"
    )


def grab_video_frame(src: Path, dest: Path, at: float = 2.0) -> Path:
    """Fotograma de la app para el carrusel (misma UI que el Reel)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{max(at, 0.2):.2f}",
            "-i",
            str(src),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(dest),
        ]
    )
    return dest


def _to_clip(src: Path, dest: Path, duration: float, vf: str, cfg: Config) -> Path:
    duration = max(duration, 0.5)
    cmd = ["ffmpeg", "-y"]
    if is_video(src):
        cmd += ["-stream_loop", "-1", "-i", str(src), "-t", f"{duration:.3f}"]
        use_vf = vf
    else:
        cmd += ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(src)]
        use_vf = kenburns_9x16(cfg, duration)
    cmd += ["-vf", use_vf, "-an", *_common_v(cfg), str(dest)]
    _run(cmd)
    return dest


def render_still_video(image: Path, dest: Path, duration: float, cfg: Config) -> Path:
    """Story o cierre en movimiento a partir de un JPG 9:16."""
    duration = max(duration, 0.5)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(image),
            "-f",
            "lavfi",
            "-t",
            f"{duration:.3f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf",
            f"scale={cfg.width}:{cfg.height},fps={cfg.fps},setsar=1,format=yuv420p",
            *_common_v(cfg),
            *_common_a(),
            "-shortest",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    return dest


def render_reel(
    hook_src: Path,
    body_src: Path,
    audio: Path,
    ass: Path,
    endcard: Path,
    dest: Path,
    work: Path,
    hook_seconds: float,
    body_seconds: float,
    cfg: Config,
    music: Path | None = None,
) -> Path:
    if not shutil.which("ffmpeg"):
        raise RenderError("ffmpeg no está en PATH. brew install ffmpeg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    hook_clip = _to_clip(hook_src, work / "hook.mp4", hook_seconds, cover_9x16(cfg), cfg)
    # App: cover 9:16 (grabaciones de móvil ya recortadas). No se estira la UI.
    body_clip = _to_clip(body_src, work / "body_v.mp4", body_seconds, cover_9x16(cfg), cfg)

    joined_v = work / "acts.mp4"
    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(hook_clip),
            "-i",
            str(body_clip),
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            *_common_v(cfg),
            str(joined_v),
        ]
    )

    body = work / "voiced.mp4"
    ass_esc = str(ass.resolve()).replace("\\", "/").replace(":", "\\:")
    logo = ROOT / "assets" / "brand" / "logo-512.png"
    voiced = hook_seconds + body_seconds
    fade_out = max(hook_seconds + 0.8, voiced - 0.75)
    mux = ["ffmpeg", "-y", "-i", str(joined_v), "-i", str(audio)]
    next_idx = 2
    music_idx = None
    if music is not None and music.exists() and music.stat().st_size > 20_000:
        mux += ["-stream_loop", "-1", "-i", str(music)]
        music_idx = next_idx
        next_idx += 1
    logo_idx = None
    if logo.exists():
        mux += ["-i", str(logo)]
        logo_idx = next_idx

    parts: list[str] = []
    if logo_idx is not None:
        parts.append(f"[0:v]ass='{ass_esc}'[sub]")
        parts.append(f"[{logo_idx}:v]scale=110:110[logo]")
        parts.append("[sub][logo]overlay=40:40,setsar=1,format=yuv420p[v]")
    else:
        parts.append(f"[0:v]ass='{ass_esc}',setsar=1,format=yuv420p[v]")
    parts.append("[1:a]aformat=sample_rates=44100:channel_layouts=stereo[vo]")
    if music_idx is not None:
        vol = max(0.04, min(float(cfg.music_volume), 0.22))
        parts.append(
            f"[{music_idx}:a]atrim=0:{voiced:.3f},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates=44100:channel_layouts=stereo,"
            f"volume={vol:.3f},afade=t=in:st={hook_seconds:.3f}:d=0.45,"
            f"afade=t=out:st={fade_out:.3f}:d=0.65[bg]"
        )
        parts.append("[vo][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
    else:
        parts.append("[vo]volume=1[a]")

    vf = ";".join(parts)
    mux += [
        "-filter_complex",
        vf,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-shortest",
        *_common_v(cfg),
        *_common_a(),
        "-movflags",
        "+faststart",
        str(body),
    ]
    _run(mux)

    card = work / "card.mp4"
    _run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-t",
            f"{cfg.endcard_seconds}",
            "-i",
            str(endcard),
            "-f",
            "lavfi",
            "-t",
            f"{cfg.endcard_seconds}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf",
            f"scale={cfg.width}:{cfg.height},fps={cfg.fps},setsar=1,format=yuv420p",
            *_common_v(cfg),
            *_common_a(),
            "-shortest",
            str(card),
        ]
    )

    _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(body),
            "-i",
            str(card),
            "-filter_complex",
            "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            *_common_v(cfg),
            *_common_a(),
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    return dest
