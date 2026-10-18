"""Attach a real console for windowed EXEs so Windows uses our icon (not cmd's)."""
from __future__ import annotations

import ctypes
import sys


def set_app_user_model_id(app_id: str) -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
    except Exception:
        pass


def ensure_attached_console() -> None:
    """
    PyInstaller ``--windowed`` EXEs have no console by default. Allocate one and
    rebind stdio so prints/input work, while the process identity (and tab/taskbar
    icon) stays our EXE — not the classic ``C:\\`` console host icon.
    """
    if not getattr(sys, "frozen", False):
        return
    try:
        kernel32 = ctypes.windll.kernel32
        if kernel32.GetConsoleWindow():
            return
        if not kernel32.AllocConsole():
            return
        # Re-open std handles against the new console
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")  # noqa: SIM115
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
    except Exception:
        pass
