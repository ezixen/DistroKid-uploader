"""Console splash (from uploader.jpg) + title-bar / window icon."""
from __future__ import annotations

import base64
import ctypes
import shutil
import sys
import zlib
from pathlib import Path

try:
    from terminal_logo_data import SIZE as _PACKED_SIZE, _B85
except ImportError:  # pragma: no cover
    _PACKED_SIZE = 0
    _B85 = ""

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040


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


def _packed_rgb() -> tuple[int, bytes] | None:
    if not _B85 or not _PACKED_SIZE:
        return None
    try:
        raw = zlib.decompress(base64.b85decode(_B85))
    except Exception:
        return None
    if len(raw) != _PACKED_SIZE * _PACKED_SIZE * 3:
        return None
    return _PACKED_SIZE, raw


def _jpeg_rgb(max_edge: int) -> tuple[int, int, bytes] | None:
    """Load uploader.jpg via Windows GDI+ (no Pillow/numpy in the EXE)."""
    jpg = find_logo_file("uploader.jpg")
    if jpg is None:
        return None
    try:
        from jpeg_win import load_jpeg_rgb
    except ImportError:
        return None
    return load_jpeg_rgb(jpg, max_edge=max_edge)


def _load_rgb_for_render(pix_w: int, pix_h: int) -> tuple[int, int, bytes] | None:
    # Prefer full JPEG scaled just above target for sharp half-block sampling
    edge = max(pix_w, pix_h) * 2
    edge = max(128, min(edge, 512))
    loaded = _jpeg_rgb(edge)
    if loaded:
        return loaded
    packed = _packed_rgb()
    if not packed:
        return None
    size, raw = packed
    return size, size, raw


def _sample(rgb: bytes, src_w: int, src_h: int, x: int, y: int, w: int, h: int) -> tuple[int, int, int]:
    sx = min(src_w - 1, (x * src_w) // max(1, w))
    sy = min(src_h - 1, (y * src_h) // max(1, h))
    i = (sy * src_w + sx) * 3
    return rgb[i], rgb[i + 1], rgb[i + 2]


def _console_cells() -> tuple[int, int]:
    try:
        size = shutil.get_terminal_size(fallback=(100, 40))
        return max(20, size.columns), max(10, size.lines)
    except Exception:
        return 100, 40


def render_logo_ansi(max_width: int | None = None) -> str:
    """Truecolor half-block ANSI art from JPEG (fallback: packed RGB)."""
    cols, lines = _console_cells()
    # Use most of the window; leave room for banner text below
    width = min(cols - 2, max_width or 120)
    width = max(32, width)
    pix_h = width - (width % 2)
    char_rows = pix_h // 2
    max_rows = max(8, min(char_rows, lines - 10))
    if max_rows < char_rows:
        char_rows = max_rows
        pix_h = char_rows * 2
        width = max(32, min(pix_h, cols - 2))
        pix_h = width - (width % 2)
        char_rows = pix_h // 2

    loaded = _load_rgb_for_render(width, pix_h)
    if not loaded:
        return ""
    src_w, src_h, rgb = loaded

    out: list[str] = []
    for cy in range(char_rows):
        parts: list[str] = []
        y0 = cy * 2
        y1 = y0 + 1
        for x in range(width):
            r0, g0, b0 = _sample(rgb, src_w, src_h, x, y0, width, pix_h)
            r1, g1, b1 = _sample(rgb, src_w, src_h, x, y1, width, pix_h)
            parts.append(
                f"\x1b[38;2;{r0};{g0};{b0}m\x1b[48;2;{r1};{g1};{b1}m▀"
            )
        parts.append("\x1b[0m")
        out.append("".join(parts))
    return "\n".join(out)


def _enable_vt() -> None:
    try:
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
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
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(art, flush=True)
    except Exception:
        pass


def _load_icon_handle(path: Path, cx: int, cy: int) -> int:
    return int(
        ctypes.windll.user32.LoadImageW(
            None,
            str(path),
            IMAGE_ICON,
            cx,
            cy,
            LR_LOADFROMFILE,
        )
        or 0
    )


def set_console_icon(ico_path: Path | None = None) -> bool:
    """Set the console window icon from uploader.ico / embedded EXE icon."""
    if ico_path is None:
        ico_path = find_logo_file("uploader.ico")
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return False
        h_small = h_big = 0
        if ico_path is not None and ico_path.is_file():
            h_small = _load_icon_handle(ico_path, 16, 16)
            h_big = _load_icon_handle(ico_path, 32, 32)
            if not h_big:
                h_big = _load_icon_handle(ico_path, 0, 0)  # default size
            if not h_small:
                h_small = h_big
        if (not h_small or not h_big) and getattr(sys, "frozen", False):
            large = ctypes.c_void_p()
            small = ctypes.c_void_p()
            ctypes.windll.shell32.ExtractIconExW(
                str(sys.executable), 0, ctypes.byref(large), ctypes.byref(small), 1
            )
            h_big = h_big or int(large.value or 0)
            h_small = h_small or int(small.value or 0) or h_big
        if not h_small and not h_big:
            return False
        if h_small:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
        if h_big:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
        # Also set class icons (helps some hosts)
        GCLP_HICON = -14
        GCLP_HICONSM = -34
        if h_big:
            ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICON, h_big)
        if h_small:
            ctypes.windll.user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, h_small)
        return True
    except Exception:
        return False
