"""
Shared album-folder helpers (titles, wavs, cover, prices).
Duplicated into each app folder on purpose (BandCamp / DistroKid / BC-DK).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_prices(prices_file: Path | None = None) -> tuple[str, str]:
    album, track = "9.99", "0.99"
    path = prices_file or (app_dir() / "prices.txt")
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip().lower(), val.strip()
            if key == "album" and val:
                album = val
            elif key == "track" and val:
                track = val
    return album, track


def title_from_filename(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"^\d+[.,\s-]*", "", stem).strip()
    if " - " in stem:
        title = stem.split(" - ", 1)[1]
    else:
        title = re.sub(r"(?i)\bezixen\b", "", stem)
    title = title.replace("_", "?")
    # Keep trailing "..." / punctuation that belongs to the title (do NOT strip ".")
    return title.strip(" -")


def album_title_from_folder(folder: Path) -> str:
    stem = folder.name
    if " - " in stem:
        left, right = stem.split(" - ", 1)
        if re.search(r"(?i)ezixen", left) or len(left) < 40:
            stem = right
    else:
        stem = re.sub(r"(?i)\bezixen\b", "", stem)
    # Keep "..." in album names; only trim spaces / dashes / underscores
    return re.sub(r"\s{2,}", " ", stem).strip(" -_")


def numbered_wavs(folder: Path) -> list[Path]:
    wavs = [p for p in folder.iterdir() if p.suffix.lower() == ".wav" and re.match(r"^\d", p.name)]
    wavs.sort(key=lambda p: int(re.match(r"^(\d+)", p.name).group(1)))
    return wavs


def largest_jpg(folder: Path) -> Path:
    jpgs = [p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg"}]
    if not jpgs:
        raise SystemExit("No jpg/jpeg cover found in folder")
    return max(jpgs, key=lambda p: p.stat().st_size)
