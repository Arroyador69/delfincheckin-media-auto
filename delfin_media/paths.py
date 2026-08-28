from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def data_path(name: str) -> Path:
    return ROOT / "data" / name
