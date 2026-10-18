"""Visible app version (console title + startup) and quit confirmation."""
from __future__ import annotations

import ctypes
import re
import sys
from pathlib import Path

from terminal_logo import print_logo, set_console_icon

_FILEVERS_RE = re.compile(r"filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)")

# Official download homes (also printed every run).
OFFICIAL_RELEASES = {
    "BandCamp Uploader": "https://github.com/ezixen/BandCamp-uploader/releases/latest",
    "DistroKid Uploader": "https://github.com/ezixen/DistroKid-uploader/releases/latest",
    "DK-BC Uploader": "https://github.com/ezixen/DK-BC-Uploader/releases/latest",
}


def _from_version_info_text(text: str) -> str | None:
    m = _FILEVERS_RE.search(text)
    if not m:
        return None
    major, minor, patch, _build = (int(m.group(i)) for i in range(1, 5))
    return f"{major}.{minor}.{patch}"


def _from_exe_file_version(exe: Path) -> str | None:
    """Read PE FileVersion (Windows) — used when frozen so version_info.txt need not ship."""
    try:
        path = str(exe)
        size = ctypes.windll.version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(path, 0, size, buf):
            return None
        u = ctypes.c_void_p()
        length = ctypes.c_uint()
        if not ctypes.windll.version.VerQueryValueW(
            buf, "\\", ctypes.byref(u), ctypes.byref(length)
        ):
            return None

        class VS_FIXEDFILEINFO(ctypes.Structure):
            _fields_ = [
                ("dwSignature", ctypes.c_uint32),
                ("dwStrucVersion", ctypes.c_uint32),
                ("dwFileVersionMS", ctypes.c_uint32),
                ("dwFileVersionLS", ctypes.c_uint32),
                ("dwProductVersionMS", ctypes.c_uint32),
                ("dwProductVersionLS", ctypes.c_uint32),
                ("dwFileFlagsMask", ctypes.c_uint32),
                ("dwFileFlags", ctypes.c_uint32),
                ("dwFileOS", ctypes.c_uint32),
                ("dwFileType", ctypes.c_uint32),
                ("dwFileSubtype", ctypes.c_uint32),
                ("dwFileDateMS", ctypes.c_uint32),
                ("dwFileDateLS", ctypes.c_uint32),
            ]

        info = ctypes.cast(u, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
        major = (info.dwFileVersionMS >> 16) & 0xFFFF
        minor = info.dwFileVersionMS & 0xFFFF
        patch = (info.dwFileVersionLS >> 16) & 0xFFFF
        return f"{major}.{minor}.{patch}"
    except Exception:
        return None


def read_display_version(*search_roots: Path | str) -> str:
    """Return semver like ``2.0.0`` from version_info.txt or the frozen EXE."""
    roots: list[Path] = [Path(r) for r in search_roots]
    here = Path(__file__).resolve().parent
    roots.extend([here, here / "app", here.parent / "app"])
    if getattr(sys, "frozen", False):
        exe_ver = _from_exe_file_version(Path(sys.executable))
        if exe_ver:
            return exe_ver
        roots.insert(0, Path(sys.executable).resolve().parent)
    for root in roots:
        for candidate in (
            root / "version_info.txt",
            root / "app" / "version_info.txt",
        ):
            if candidate.is_file():
                try:
                    parsed = _from_version_info_text(
                        candidate.read_text(encoding="utf-8")
                    )
                except OSError:
                    parsed = None
                if parsed:
                    return parsed
    return "unknown"


def set_console_title(title: str) -> None:
    try:
        ctypes.windll.kernel32.SetConsoleTitleW(str(title))
    except Exception:
        pass


def official_source_lines(product_name: str) -> list[str]:
    url = OFFICIAL_RELEASES.get(product_name, "https://github.com/ezixen")
    return [
        "Please download this uploader only from the official GitHub release page —",
        "that way you get the real build, not an old or altered copy. Thank you!",
        f"  {url}",
    ]


def print_startup_banner(product_name: str, version: str, *extra_lines: str) -> None:
    """Logo (sized to the window), title-bar icon, version header, source note."""
    title = f"{product_name} v{version}"
    set_console_title(title)
    set_console_icon()
    print_logo()
    print(f"=== {title} ===", flush=True)
    for line in official_source_lines(product_name):
        print(line, flush=True)
    print(flush=True)
    for line in extra_lines:
        print(line, flush=True)


def confirm_quit(*, input_fn=input) -> bool:
    """Warn that quitting closes debug Chrome; require explicit yes."""
    print(flush=True)
    print("Quit will CLOSE the debug Chrome browser as well.", flush=True)
    print(
        "Make sure all uploads are done and setup / review is finished first.",
        flush=True,
    )
    ans = input_fn("Really quit and close the browser? [y/N]: ").strip().lower()
    return ans in {"y", "yes"}
