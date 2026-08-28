from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from delfin_media.config import Config
from delfin_media.paths import ROOT


class RenderError(RuntimeError):
    pass


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(proc.stderr[-2000:] or proc.stdout[-2000:])


def _ken_burns(cfg: Config, duration: float, shot_idx: int) -> str:
    d = max(duration, 0.5)
    w, h = cfg.width, cfg.height
    sw, sh = w + 280, h + 496
    if shot_idx % 3 == 0:
        crop = f"crop={w}:{h}:(in_w-{w})/2:(in_h-{h})*t/{d:.3f}"
    elif shot_idx % 3 == 1:
        crop = f"crop={w}:{h}:(in_w-{w})*t/{d:.3f}:(in_h-{h})*0.4"
    else:
        crop = f"crop={w}:{h}:(in_w-{w})*(1-t/{d:.3f}):(in_h-{h})*0.22"
    return (
        f"scale={sw}:{sh}:flags=lanczos,{crop},"
        f"eq=saturation=1.07:contrast=1.06,fps={cfg.fps},setsar=1,format=yuv420p"
    )


def render_reel(
    photos: list[Path],
    audio: Path,
    ass: Path,
    endcard: Path,
    dest: Path,
    work: Path,
    voice_seconds: float,
    cfg: Config,
) -> Path:
    if not shutil.which("ffmpeg"):
        raise RenderError("ffmpeg no está en PATH. brew install ffmpeg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    photos = [p for p in photos if p.exists()] or photos
    n = max(len(photos), 1)
    piece = max(voice_seconds, 8.0) / n
    common_v = [
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
    common_a = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]
    shots: list[Path] = []
    for i, photo in enumerate(photos):
        shot = work / f"shot_{i}.mp4"
        _run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-t",
                f"{piece:.3f}",
                "-i",
                str(photo),
                "-vf",
                _ken_burns(cfg, piece, i),
                "-an",
                *common_v,
                str(shot),
            ]
        )
        shots.append(shot)

    body_v = work / "body_v.mp4"
    if len(shots) == 1:
        body_v = shots[0]
    else:
        fc = "".join(f"[{i}:v]" for i in range(len(shots)))
        fc += f"concat=n={len(shots)}:v=1:a=0[v]"
        cmd = ["ffmpeg", "-y"]
        for shot in shots:
            cmd += ["-i", str(shot)]
        cmd += ["-filter_complex", fc, "-map", "[v]", *common_v, str(body_v)]
        _run(cmd)

    body = work / "body.mp4"
    ass_esc = str(ass.resolve()).replace("\\", "/").replace(":", "\\:")
    logo = ROOT / "assets" / "brand" / "logo-512.png"
    mux = [
        "ffmpeg",
        "-y",
        "-i",
        str(body_v),
        "-i",
        str(audio),
    ]
    if logo.exists():
        mux += ["-i", str(logo)]
        vf = (
            f"[0:v]ass='{ass_esc}'[sub];"
            f"[2:v]scale=110:110[logo];"
            f"[sub][logo]overlay=40:40,setsar=1,format=yuv420p[v];"
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a]"
        )
    else:
        vf = (
            f"[0:v]ass='{ass_esc}',setsar=1,format=yuv420p[v];"
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a]"
        )
    mux += [
        "-filter_complex",
        vf,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-shortest",
        *common_v,
        *common_a,
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
            *common_v,
            *common_a,
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
            *common_v,
            *common_a,
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )
    return dest
