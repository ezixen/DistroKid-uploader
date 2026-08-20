"""
Load DistroKid upload-settings.txt (replaces prices.txt for this app).

Code defaults (no file / missing keys) are safe for new users:
  ai=off, mandatory_checkboxes=off, explicit=off, audiomack=on
Your checked-in upload-settings.txt can override for your own releases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


def _truthy(val: str) -> bool:
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}


def _parse_roles(val: str) -> list[str]:
    return [p.strip() for p in val.split(",") if p.strip()]


def parse_real_name(full: str) -> tuple[str, str, str]:
    """
    Split DistroKid songwriter real name into first / middle / last.
    Supports: George 'ezixen' Lawrence  →  George | ezixen | Lawrence
    """
    raw = (full or "").strip()
    if not raw:
        return "", "", ""
    quoted = re.match(r"^(.+?)\s+['\"]([^'\"]+)['\"]\s+(.+)$", raw)
    if quoted:
        return quoted.group(1).strip(), quoted.group(2).strip(), quoted.group(3).strip()
    parts = raw.split()
    if len(parts) >= 3:
        return parts[0], " ".join(parts[1:-1]), parts[-1]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return raw, "", ""


@dataclass
class UploadSettings:
    album_price: str = "9.99"
    track_price: str = "0.99"
    releaser: str = "(ezixen) records"
    real_name: str = "George 'ezixen' Lawrence"
    real_name_first: str = ""
    real_name_middle: str = ""
    real_name_last: str = ""
    artist: str = "ezixen"
    instrumental: bool = True
    explicit: bool = False  # Explicit lyrics — default No
    # ai: off | on | both  — default OFF for new users
    ai: str = "off"
    ai_lyrics: bool = False
    ai_music: bool = False
    ai_all_audio: bool = False
    ai_part_audio: bool = False
    ai_part_vocals: bool = False
    ai_part_instruments: bool = False
    ai_artist_persona: str = "human"  # human | ai
    credit_artist: str = "ezixen"
    credit_roles: list[str] = field(
        default_factory=lambda: ["Unknown", "Executive producer"]
    )
    stores_include_social: bool = True
    audiomack: bool = True  # free extra — on by default
    release_date: str = "today"
    # Bottom "Important checkboxes (mandatory)" — default OFF for users
    mandatory_checkboxes: bool = False

    @property
    def ai_enabled(self) -> bool:
        return self.ai.strip().lower() in {"on", "both", "yes", "true"}

    def songwriter_parts(self) -> tuple[str, str, str]:
        if self.real_name_first or self.real_name_middle or self.real_name_last:
            return (
                (self.real_name_first or "").strip(),
                (self.real_name_middle or "").strip(),
                (self.real_name_last or "").strip(),
            )
        return parse_real_name(self.real_name)

    def release_date_iso(self) -> str:
        from datetime import date

        raw = (self.release_date or "today").strip().lower()
        if raw in {"", "today", "now"}:
            return date.today().isoformat()
        return self.release_date.strip()


def settings_path(app_root: Path) -> Path:
    preferred = app_root / "upload-settings.txt"
    legacy = app_root / "prices.txt"
    if preferred.is_file():
        return preferred
    return legacy if legacy.is_file() else preferred


def load_upload_settings(app_root: Path) -> UploadSettings:
    path = settings_path(app_root)
    s = UploadSettings()
    if not path.is_file():
        return s
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip().lower(), val.strip()
        if key in {"album", "album_price"} and val:
            s.album_price = val
        elif key in {"track", "track_price"} and val:
            s.track_price = val
        elif key in {"releaser", "label", "record_label"} and val:
            s.releaser = val
        elif key in {"real_name", "legal_name", "fullname_name"} and val:
            s.real_name = val
        elif key in {"real_name_first", "first_name"} and val:
            s.real_name_first = val
        elif key in {"real_name_middle", "middle_name"} and val:
            s.real_name_middle = val
        elif key in {"real_name_last", "last_name"} and val:
            s.real_name_last = val
        elif key in {"artist", "artist_name", "band"} and val:
            s.artist = val
        elif key == "instrumental":
            s.instrumental = _truthy(val)
        elif key == "explicit":
            s.explicit = _truthy(val)
        elif key == "ai":
            s.ai = val.lower()
        elif key == "ai_lyrics":
            s.ai_lyrics = _truthy(val)
        elif key == "ai_music":
            s.ai_music = _truthy(val)
        elif key == "ai_all_audio":
            s.ai_all_audio = _truthy(val)
        elif key == "ai_part_audio":
            s.ai_part_audio = _truthy(val)
        elif key == "ai_part_vocals":
            s.ai_part_vocals = _truthy(val)
        elif key == "ai_part_instruments":
            s.ai_part_instruments = _truthy(val)
        elif key in {"ai_artist_persona", "ai_persona"}:
            s.ai_artist_persona = val.lower()
        elif key in {"credit_artist", "contributor", "contributing_artist"} and val:
            s.credit_artist = val
        elif key in {"credit_roles", "roles"} and val:
            s.credit_roles = _parse_roles(val)
        elif key in {"stores_include_social", "include_social"}:
            s.stores_include_social = _truthy(val)
        elif key == "audiomack":
            s.audiomack = _truthy(val)
        elif key in {"release_date", "releasedate", "go_live_date"}:
            s.release_date = val or "today"
        elif key in {"mandatory_checkboxes", "important_checkboxes", "mandatory"}:
            s.mandatory_checkboxes = _truthy(val)
    if s.ai.strip().lower() == "off":
        s.ai_lyrics = s.ai_music = s.ai_all_audio = s.ai_part_audio = False
        s.ai_part_vocals = s.ai_part_instruments = False
    return s
