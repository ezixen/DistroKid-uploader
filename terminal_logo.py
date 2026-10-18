"""Console splash + title-bar icon from the uploader logo."""
from __future__ import annotations

import base64
import ctypes
import shutil
import sys
import zlib
from pathlib import Path

try:
    from terminal_logo_data import SIZE as _GRID, _B85
except ImportError:  # pragma: no cover
    _GRID = 0
    _B85 = ""

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040


def _rgb_grid() -> bytes | None:
    if not _B85 or not _GRID:
        return None
    try:
        raw = zlib.decompress(base64.b85decode(_B85))
    except Exception:
        return None
    if len(raw) != _GRID * _GRID * 3:
        return None
    return raw


def _sample(grid: bytes, src: int, x: int, y: int, w: int, h: int) -> tuple[int, int, int]:
    sx = min(src - 1, (x * src) // max(1, w))
    sy = min(src - 1, (y * src) // max(1, h))
    i = (sy * src + sx) * 3
    return grid[i], grid[i + 1], grid[i + 2]


def _console_cells() -> tuple[int, int]:
    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return max(20, size.columns), max(10, size.lines)
    except Exception:
        return 80, 24


def render_logo_ansi(max_width: int | None = None) -> str:
    """Truecolor half-block ANSI art, sized to the current console."""
    grid = _rgb_grid()
    if not grid:
        return ""
    cols, lines = _console_cells()
    # Leave room for banner text; keep roughly square using half-blocks.
    width = min(cols - 2, max_width or 72, 96)
    width = max(24, width)
    # Each char row shows 2 pixel rows → pixel height ~= width for square logo.
    pix_h = width
    if pix_h % 2:
        pix_h -= 1
    char_rows = pix_h // 2
    # Don't eat the whole terminal
    max_rows = max(6, min(char_rows, lines - 8))
    if max_rows < char_rows:
        char_rows = max_rows
        pix_h = char_rows * 2
        width = pix_h  # keep square-ish
        width = max(24, min(width, cols - 2))
        pix_h = width - (width % 2)
        char_rows = pix_h // 2

    out: list[str] = []
    for cy in range(char_rows):
        parts: list[str] = []
        y0 = cy * 2
        y1 = y0 + 1
        for x in range(width):
            r0, g0, b0 = _sample(grid, _GRID, x, y0, width, pix_h)
            r1, g1, b1 = _sample(grid, _GRID, x, y1, width, pix_h)
            parts.append(
                f"\x1b[38;2;{r0};{g0};{b0}m\x1b[48;2;{r1};{g1};{b1}m▀"
            )
        parts.append("\x1b[0m")
        out.append("".join(parts))
    return "\n".join(out)


def _enable_vt() -> None:
    """Allow truecolor ANSI in classic conhost / Windows Terminal."""
    try:
        handle = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def print_logo(*, enabled: bool = True) -> None:
    if not enabled:
        return
    _enable_vt()
    art = render_logo_ansi()
    if not art:
        return
    try:
        # Windows cp1252 consoles cannot print ▀ without UTF-8 mode.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(art, flush=True)
    except Exception:
        pass


def find_logo_file(*names: str, search_roots: list[Path] | None = None) -> Path | None:
    roots: list[Path] = list(search_roots or [])
    here = Path(__file__).resolve().parent
    roots.extend([here, here / "app", here.parent / "app"])
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots.insert(0, exe_dir)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.insert(0, Path(meipass))
    for root in roots:
        for name in names:
            p = Path(root) / name
            if p.is_file():
                return p
    return None


def set_console_icon(ico_path: Path | None = None) -> bool:
    """Best-effort: set the console window icon (conhost; WT may keep its tab icon)."""
    if ico_path is None:
        ico_path = find_logo_file("uploader.ico")
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return False
        hicon = 0
        if ico_path is not None and ico_path.is_file():
            hicon = ctypes.windll.user32.LoadImageW(
                None,
                str(ico_path),
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE,
            )
        if not hicon and getattr(sys, "frozen", False):
            hicon = ctypes.windll.shell32.ExtractIconW(
                ctypes.windll.kernel32.GetModuleHandleW(None),
                str(sys.executable),
                0,
            )
        if not hicon:
            return False
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
        return True
    except Exception:
        return False