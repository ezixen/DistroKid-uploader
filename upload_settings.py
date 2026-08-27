"""
Load DistroKid upload-settings.txt (replaces prices.txt for this app).

Code defaults match shipped upload-settings.txt (ezixen releases).
If upload-settings.txt is missing, copy upload-settings.example.txt first.
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
    Split ONE person's legal name into DistroKid First / Middle / Last fields.
    Still one person — never one word = one songwriter.

    Supports: George 'ezixen' Lawrence  →  George | ezixen | Lawrence
    Spanish-style: Maria del Carmen Garcia Lopez → Maria | del Carmen Garcia | Lopez
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


def person_name_to_parts(full: str, *, mode: str = "auto") -> tuple[str, str, str]:
    """Map one person's full name line onto DistroKid First/Middle/Last."""
    m = (mode or "auto").strip().lower()
    raw = (full or "").strip()
    if not raw:
        return "", "", ""
    if m in {"full_first", "first", "whole", "nosplit", "no_split"}:
        return raw, "", ""
    return parse_real_name(raw)


_SONGWRITER_N_RE = re.compile(r"^songwriter[_\s-]*(\d+)$", re.I)
_PRODUCER_N_RE = re.compile(r"^producer[_\s-]*(\d+)$", re.I)
_PLAYER_N_RE = re.compile(
    r"^(?:player|performer|instrument_player|instrumentplayer)[_\s-]*(\d+)$",
    re.I,
)


@dataclass
class UploadSettings:
    album_price: str = "9.99"
    track_price: str = "0.99"
    releaser: str = "(ezixen) records"
    real_name: str = "George ezixen Lawrence"
    real_name_first: str = ""
    real_name_middle: str = ""
    real_name_last: str = ""
    # Numbered persons: songwriter_1=…, songwriter_2=… (one full name per line)
    songwriters: list[str] = field(default_factory=lambda: ["George ezixen Lawrence"])
    # auto = First/Middle/Last from that one line; full_first = entire line in First only
    songwriter_name_mode: str = "auto"
    artist: str = "ezixen"
    instrumental: bool = True
    explicit: bool = False  # Explicit lyrics — default No
    # ai: off | on | both  — default OFF for new users
    ai: str = "off"
    ai_lyrics: bool = False
    ai_music: bool = False
    ai_all_audio: bool = False
    ai_part_audio: bool = True
    ai_part_vocals: bool = False
    ai_part_instruments: bool = True
    ai_artist_persona: str = "human"  # human | ai
    credit_artist: str = "ezixen"
    credit_roles: list[str] = field(
        default_factory=lambda: ["Unknown", "Executive producer"]
    )
    # Numbered Apple credits (one person per line — full name, any word count)
    producers: list[str] = field(default_factory=lambda: ["ezixen"])
    players: list[str] = field(default_factory=lambda: ["ezixen"])  # instrument / performer
    producer_role: str = ""  # default resolved from credit_roles / Executive producer
    player_role: str = ""  # default resolved from credit_roles / Unknown
    stores_include_social: bool = True
    audiomack: bool = True  # free extra — on by default
    release_date: str = "today"
    mandatory_checkboxes: bool = True

    @property
    def ai_enabled(self) -> bool:
        if self.ai.strip().lower() in {"on", "both", "yes", "true"}:
            return True
        return any(
            (
                self.ai_lyrics,
                self.ai_music,
                self.ai_all_audio,
                self.ai_part_audio,
                self.ai_part_vocals,
                self.ai_part_instruments,
            )
        )

    def songwriter_people(self) -> list[tuple[str, str, str]]:
        """
        One DistroKid songwriter person per entry (First, Middle, Last).

        Prefer numbered lines songwriter_1= / songwriter_2= …
        (entire value = that person's name, any word count).
        Else legacy real_name / real_name_first|middle|last (single person).
        """
        mode = self.songwriter_name_mode
        if self.songwriters:
            return [person_name_to_parts(n, mode=mode) for n in self.songwriters if (n or "").strip()]
        if self.real_name_first or self.real_name_middle or self.real_name_last:
            return [
                (
                    (self.real_name_first or "").strip(),
                    (self.real_name_middle or "").strip(),
                    (self.real_name_last or "").strip(),
                )
            ]
        parts = person_name_to_parts(self.real_name, mode=mode)
        return [parts] if any(parts) else []

    def songwriter_parts(self) -> tuple[str, str, str]:
        """First songwriter only (compat). Prefer songwriter_people()."""
        people = self.songwriter_people()
        return people[0] if people else ("", "", "")

    def _legacy_credit_name(self) -> str:
        return (self.credit_artist or self.artist or "").strip()

    def producer_names(self) -> list[str]:
        """Apple Music producer display names (one person per entry)."""
        if self.producers:
            return [n.strip() for n in self.producers if (n or "").strip()]
        name = self._legacy_credit_name()
        return [name] if name else []

    def player_names(self) -> list[str]:
        """Apple Music performer / instrument-player display names."""
        if self.players:
            return [n.strip() for n in self.players if (n or "").strip()]
        name = self._legacy_credit_name()
        return [name] if name else []

    def resolved_producer_role(self) -> str:
        if (self.producer_role or "").strip():
            return self.producer_role.strip()
        roles = list(self.credit_roles or [])
        hit = next((r for r in roles if r.lower().strip() == "executive producer"), None)
        if hit:
            return hit
        hit = next((r for r in roles if "executive" in r.lower() or "producer" in r.lower()), None)
        return hit or "Executive producer"

    def resolved_player_role(self) -> str:
        if (self.player_role or "").strip():
            return self.player_role.strip()
        roles = list(self.credit_roles or [])
        hit = next((r for r in roles if "unknown" in r.lower()), None)
        return hit or "Unknown"

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
    numbered_sw: dict[int, str] = {}
    numbered_prod: dict[int, str] = {}
    numbered_play: dict[int, str] = {}
    explicit_ai: set[str] = set()
    saw_real_name = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip().lower(), val.strip()
        m_sw = _SONGWRITER_N_RE.match(key)
        if m_sw and val:
            numbered_sw[int(m_sw.group(1))] = val
            continue
        m_pr = _PRODUCER_N_RE.match(key)
        if m_pr and val:
            numbered_prod[int(m_pr.group(1))] = val
            continue
        m_pl = _PLAYER_N_RE.match(key)
        if m_pl and val:
            numbered_play[int(m_pl.group(1))] = val
            continue
        if key in {"songwriter_name_mode", "songwriter_split", "real_name_mode"} and val:
            s.songwriter_name_mode = val.lower()
            continue
        if key in {"album", "album_price"} and val:
            s.album_price = val
        elif key in {"track", "track_price"} and val:
            s.track_price = val
        elif key in {"releaser", "label", "record_label"} and val:
            s.releaser = val
        elif key in {"real_name", "legal_name", "fullname_name"} and val:
            s.real_name = val
            saw_real_name = True
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
            explicit_ai.add("ai")
        elif key == "ai_lyrics":
            s.ai_lyrics = _truthy(val)
            explicit_ai.add("ai_lyrics")
        elif key == "ai_music":
            s.ai_music = _truthy(val)
            explicit_ai.add("ai_music")
        elif key == "ai_all_audio":
            s.ai_all_audio = _truthy(val)
            explicit_ai.add("ai_all_audio")
        elif key == "ai_part_audio":
            s.ai_part_audio = _truthy(val)
            explicit_ai.add("ai_part_audio")
        elif key == "ai_part_vocals":
            s.ai_part_vocals = _truthy(val)
            explicit_ai.add("ai_part_vocals")
        elif key == "ai_part_instruments":
            s.ai_part_instruments = _truthy(val)
            explicit_ai.add("ai_part_instruments")
        elif key in {"ai_artist_persona", "ai_persona"}:
            s.ai_artist_persona = val.lower()
        elif key in {"credit_artist", "contributor", "contributing_artist"} and val:
            s.credit_artist = val
        elif key in {"credit_roles", "roles"} and val:
            s.credit_roles = _parse_roles(val)
        elif key in {"producer_role", "credit_producer_role"} and val:
            s.producer_role = val
        elif key in {"player_role", "performer_role", "credit_performer_role"} and val:
            s.player_role = val
        elif key in {"stores_include_social", "include_social"}:
            s.stores_include_social = _truthy(val)
        elif key == "audiomack":
            s.audiomack = _truthy(val)
        elif key in {"release_date", "releasedate", "go_live_date"}:
            s.release_date = val or "today"
        elif key in {"mandatory_checkboxes", "important_checkboxes", "mandatory"}:
            s.mandatory_checkboxes = _truthy(val)
    if numbered_sw:
        s.songwriters = [numbered_sw[i] for i in sorted(numbered_sw)]
    elif saw_real_name and s.real_name.strip():
        s.songwriters = [s.real_name.strip()]
    if numbered_prod:
        s.producers = [numbered_prod[i] for i in sorted(numbered_prod)]
    if numbered_play:
        s.players = [numbered_play[i] for i in sorted(numbered_play)]
    if s.ai.strip().lower() == "off":
        explicit_part = bool(
            explicit_ai
            & {
                "ai_lyrics",
                "ai_music",
                "ai_all_audio",
                "ai_part_audio",
                "ai_part_vocals",
                "ai_part_instruments",
            }
        )
        if explicit_part:
            # ai=off but explicit ai_* flags in file → still disclose Yes + selected parts
            s.ai = "both"
        else:
            s.ai_lyrics = s.ai_music = s.ai_all_audio = s.ai_part_audio = False
            s.ai_part_vocals = s.ai_part_instruments = False
    return s
