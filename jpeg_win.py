"""Load a JPEG to RGB bytes via Windows GDI+ (no Pillow / numpy)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", ctypes.c_uint32),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", wintypes.BOOL),
        ("SuppressExternalCodecs", wintypes.BOOL),
    ]


class BitmapData(ctypes.Structure):
    _fields_ = [
        ("Width", wintypes.UINT),
        ("Height", wintypes.UINT),
        ("Stride", ctypes.c_int),
        ("PixelFormat", ctypes.c_int),
        ("Scan0", ctypes.c_void_p),
        ("Reserved", ctypes.c_void_p),
    ]


class Rect(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.c_int),
        ("Y", ctypes.c_int),
        ("Width", ctypes.c_int),
        ("Height", ctypes.c_int),
    ]


# PixelFormat24bppRGB
_PixelFormat24bppRGB = 0x00021808
_ImageLockModeRead = 0x0001


def load_jpeg_rgb(path: Path, max_edge: int = 512) -> tuple[int, int, bytes] | None:
    """
    Return ``(width, height, rgb_bytes)`` for *path*, scaled so the longest
    side is at most *max_edge*. Uses GDI+ only.
    """
    path = Path(path)
    if not path.is_file():
        return None
    gdiplus = ctypes.windll.gdiplus
    token = ctypes.c_ulong()
    startup = GdiplusStartupInput()
    startup.GdiplusVersion = 1
    if gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None) != 0:
        return None
    try:
        bitmap = ctypes.c_void_p()
        status = gdiplus.GdipCreateBitmapFromFile(str(path), ctypes.byref(bitmap))
        if status != 0 or not bitmap:
            return None
        try:
            src_w = ctypes.c_uint()
            src_h = ctypes.c_uint()
            gdiplus.GdipGetImageWidth(bitmap, ctypes.byref(src_w))
            gdiplus.GdipGetImageHeight(bitmap, ctypes.byref(src_h))
            w0, h0 = int(src_w.value), int(src_h.value)
            if w0 <= 0 or h0 <= 0:
                return None
            scale = min(1.0, float(max_edge) / float(max(w0, h0)))
            w = max(1, int(round(w0 * scale)))
            h = max(1, int(round(h0 * scale)))

            # Draw into a new 24bpp bitmap at target size (high-quality bilinear).
            dest = ctypes.c_void_p()
            if gdiplus.GdipCreateBitmapFromScan0(
                w, h, 0, _PixelFormat24bppRGB, None, ctypes.byref(dest)
            ) != 0:
                return None
            try:
                graphics = ctypes.c_void_p()
                if gdiplus.GdipGetImageGraphicsContext(dest, ctypes.byref(graphics)) != 0:
                    return None
                try:
                    # InterpolationModeHighQualityBicubic = 7
                    gdiplus.GdipSetInterpolationMode(graphics, 7)
                    gdiplus.GdipDrawImageRectI(graphics, bitmap, 0, 0, w, h)
                finally:
                    gdiplus.GdipDeleteGraphics(graphics)

                data = BitmapData()
                rect = Rect(0, 0, w, h)
                if gdiplus.GdipBitmapLockBits(
                    dest,
                    ctypes.byref(rect),
                    _ImageLockModeRead,
                    _PixelFormat24bppRGB,
                    ctypes.byref(data),
                ) != 0:
                    return None
                try:
                    # GDI+ 24bpp is BGR, stride may include padding
                    stride = int(data.Stride)
                    raw = ctypes.string_at(data.Scan0, stride * h)
                    rgb = bytearray(w * h * 3)
                    for y in range(h):
                        row = raw[y * stride : y * stride + w * 3]
                        for x in range(w):
                            b, g, r = row[x * 3], row[x * 3 + 1], row[x * 3 + 2]
                            i = (y * w + x) * 3
                            rgb[i] = r
                            rgb[i + 1] = g
                            rgb[i + 2] = b
                    return w, h, bytes(rgb)
                finally:
                    gdiplus.GdipBitmapUnlockBits(dest, ctypes.byref(data))
            finally:
                gdiplus.GdipDisposeImage(dest)
        finally:
            gdiplus.GdipDisposeImage(bitmap)
    except Exception:
        return None
    finally:
        gdiplus.GdiplusShutdown(token)
