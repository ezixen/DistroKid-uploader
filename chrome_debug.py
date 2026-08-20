"""
Shared Chrome debug-profile helpers (EXE + scripts).

Profile lives under %%LOCALAPPDATA%%\\DistroKid-Uploader so the unpacked
app folder can always be deleted without fighting Chrome lock files.

After each use we stop debug Chrome, drop locks/caches/temp, and remove any
legacy local-secrets next to the app â€” but we KEEP DistroKid login cookies.
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import time
from pathlib import Path

PROFILE_ROOT_NAME = "DistroKid-Uploader"
PROFILE_DIR_NAME = "chrome-debug-profile"
DEFAULT_DEBUG_PORT = 9222

# PIDs / ports of debug Chrome we started this process (CommandLine is often blank on Windows).
_started_chrome_pids: set[int] = set()
_started_debug_ports: set[int] = set()

# Names/paths to delete after a session (ephemeral). Login/session data is kept.
_EPHEMERAL_DIR_NAMES = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "ShaderCache",
    "DawnCache",
    "DawnWebGPUCache",
    "Media Cache",
    "VideoDecodeStats",
    "Crashpad",
    "CrashpadMetrics-active.pma",
    "BrowserMetrics",
    "optimization_guide_hint_cache_store",
    "Download Service",
    "Safe Browsing",
    "File System",
    "blob_storage",
    "Service Worker",
}
# Never delete these (DistroKid login / prefs)
_KEEP_NAME_HINTS = (
    "Cookies",
    "Login Data",
    "Preferences",
    "Secure Preferences",
    "Web Data",
    "Network",
    "Local Storage",
    "Session Storage",
    "IndexedDB",
)


def chrome_data_root() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / PROFILE_ROOT_NAME


def chrome_profile_dir() -> Path:
    return chrome_data_root() / PROFILE_DIR_NAME


def ensure_user_writable(path: Path) -> Path:
    """Create path and grant the current user full control (recursive)."""
    path.mkdir(parents=True, exist_ok=True)
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if user:
        subprocess.run(
            ["icacls", str(path), "/grant", f"{user}:(OI)(CI)F", "/T", "/C", "/Q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def remember_started_chrome(pid: int | None, port: int = DEFAULT_DEBUG_PORT) -> None:
    """Record a Chrome process we launched so cleanup can stop it without CommandLine."""
    if pid and pid > 0:
        _started_chrome_pids.add(int(pid))
    if port and port > 0:
        _started_debug_ports.add(int(port))


def remember_debug_port_listeners(port: int = DEFAULT_DEBUG_PORT) -> None:
    """After CDP is up, record the real browser PID(s) listening on the debug port."""
    remember_started_chrome(None, port=port)
    for pid in _pids_listening_on_port(port):
        remember_started_chrome(pid, port=port)


def _powershell() -> str:
    return (
        os.environ.get("SystemRoot", r"C:\Windows")
        + r"\System32\WindowsPowerShell\v1.0\powershell.exe"
    )


def _pids_listening_on_port(port: int) -> list[int]:
    """Return PIDs with a TCP LISTENING socket on 127.0.0.1:port (netstat)."""
    try:
        r = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    needle = f"127.0.0.1:{port}"
    found: set[int] = set()
    for line in (r.stdout or "").splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[1] != needle and not parts[1].endswith(f":{port}"):
            # Prefer localhost; still allow 0.0.0.0:port / [::1]:port
            if f":{port}" not in parts[1]:
                continue
            if not (
                parts[1].startswith("127.0.0.1:")
                or parts[1].startswith("0.0.0.0:")
                or parts[1].startswith("[::1]:")
                or parts[1].startswith("[::]:")
            ):
                continue
        try:
            found.add(int(parts[-1]))
        except ValueError:
            continue
    return sorted(found)


def _debug_ports_for_profile(profile: Path) -> set[int]:
    ports: set[int] = set()
    port_file = profile / "DevToolsActivePort"
    if port_file.is_file():
        try:
            first = port_file.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
            if first.isdigit():
                ports.add(int(first))
        except OSError:
            pass
    return ports


def _taskkill_tree(pid: int) -> bool:
    try:
        r = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        err = (r.stderr or "") + (r.stdout or "")
        return r.returncode == 0 or "not found" in err.lower()
    except (OSError, subprocess.TimeoutExpired):
        return False


def stop_chrome_using_profile(profile: Path | None = None) -> int:
    """
    Stop debug Chrome for our DistroKid profile.

    Windows often returns empty Win32 CommandLine for chrome.exe, so we also:
    - kill process trees we started this session (remember_started_chrome)
    - kill listeners on debug ports we started or that DevToolsActivePort lists
    """
    global _started_chrome_pids, _started_debug_ports
    profile = profile or chrome_profile_dir()
    stopped = 0
    ports_to_clear = set(_started_debug_ports) | _debug_ports_for_profile(profile)

    # 1) Processes we launched (reliable even when CommandLine is blank)
    for pid in list(_started_chrome_pids):
        if _taskkill_tree(pid):
            stopped += 1
    _started_chrome_pids.clear()

    # 2) CommandLine match when the OS exposes it
    markers = [
        str(profile).replace("/", "\\"),
        f"{PROFILE_ROOT_NAME}\\{PROFILE_DIR_NAME}",
        "local-secrets\\chrome-debug-profile",
    ]
    likes = " -or ".join(
        f"($_.CommandLine -like '*{m.replace(chr(39), '')}*')" for m in markers
    )
    ps = f"""
$ErrorActionPreference = 'SilentlyContinue'
$n = 0
Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | ForEach-Object {{
  if ($_.CommandLine -and ({likes})) {{
    taskkill /PID $_.ProcessId /T /F 2>$null | Out-Null
    $n++
  }}
}}
Write-Output $n
"""
    try:
        r = subprocess.run(
            [
                _powershell(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        try:
            stopped += int((r.stdout or "0").strip().splitlines()[-1])
        except (ValueError, IndexError):
            pass
    except (OSError, subprocess.TimeoutExpired):
        pass

    # 3) Port-based kill only for ports we started or our profile advertises
    for port in ports_to_clear:
        for pid in _pids_listening_on_port(port):
            if _taskkill_tree(pid):
                stopped += 1
    _started_debug_ports.clear()

    time.sleep(0.8)
    return stopped


def clear_chrome_lock_files(profile: Path | None = None) -> None:
    profile = profile or chrome_profile_dir()
    if not profile.is_dir():
        return
    for pattern in ("**/LOCK", "**/SingletonLock", "**/SingletonCookie", "**/SingletonSocket"):
        for p in profile.glob(pattern):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


def _is_keep(path: Path) -> bool:
    name = path.name
    for hint in _KEEP_NAME_HINTS:
        if name == hint or name.startswith(hint):
            return True
    return False


def prune_ephemeral_chrome_cache(profile: Path | None = None) -> None:
    """Delete caches/temp under the profile; keep cookies / login / prefs."""
    profile = profile or chrome_profile_dir()
    if not profile.is_dir():
        return
    for child in list(profile.iterdir()):
        if _is_keep(child):
            continue
        if child.is_dir() and child.name in _EPHEMERAL_DIR_NAMES:
            shutil.rmtree(child, ignore_errors=True)
        elif child.is_file() and child.suffix.lower() in {".tmp", ".log", ".old", ".pma"}:
            try:
                child.unlink(missing_ok=True)
            except OSError:
                pass
    # Default/ profile subfolder (Chrome often nests here)
    default = profile / "Default"
    if default.is_dir():
        for child in list(default.iterdir()):
            if _is_keep(child):
                continue
            if child.is_dir() and child.name in _EPHEMERAL_DIR_NAMES:
                shutil.rmtree(child, ignore_errors=True)
            elif child.is_file() and child.name in {"LOCK", "TransportSecurity"}:
                try:
                    child.unlink(missing_ok=True)
                except OSError:
                    pass


def force_remove_tree(path: Path) -> bool:
    """Best-effort delete of a directory tree on any drive (takeown + robocopy empty mirror)."""
    if not path.exists():
        return True
    path = path.resolve()
    stop_chrome_using_profile(path if path.name == PROFILE_DIR_NAME else path / PROFILE_DIR_NAME)
    # Also stop chrome if command line mentions this exact path
    marker = str(path).replace("/", "\\")
    try:
        subprocess.run(
            [
                os.environ.get("SystemRoot", r"C:\Windows")
                + r"\System32\WindowsPowerShell\v1.0\powershell.exe",
                "-NoProfile",
                "-Command",
                f"""
$ErrorActionPreference='SilentlyContinue'
Get-CimInstance Win32_Process | Where-Object {{
  $_.CommandLine -and $_.CommandLine -like '*{marker.replace(chr(39),'')}*'
}} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}
""",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    time.sleep(0.8)
    ensure_user_writable(path)
    shutil.rmtree(path, ignore_errors=True)
    if not path.exists():
        return True
    # robocopy empty-dir mirror (works when rd/Remove-Item fail)
    empty = Path(os.environ.get("TEMP", ".")) / f"empty_del_{os.getpid()}_{int(time.time())}"
    try:
        empty.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["robocopy", str(empty), str(path), "/MIR", "/R:2", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"],
            capture_output=True,
            check=False,
        )
        subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(path)], capture_output=True, check=False)
    finally:
        shutil.rmtree(empty, ignore_errors=True)
    if not path.exists():
        return True
    # Rename aside so parent can be deleted; schedule delete on reboot as last resort
    renamed = path.with_name(path.name + ".__delete_me__")
    try:
        if renamed.exists():
            shutil.rmtree(renamed, ignore_errors=True)
        path.rename(renamed)
        path = renamed
    except OSError:
        pass
    try:
        import ctypes

        MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
        # Schedule each top-level file if still present
        for p in [path] + (list(path.rglob("*")) if path.exists() else []):
            if p.exists() and p.is_file():
                ctypes.windll.kernel32.MoveFileExW(str(p), None, MOVEFILE_DELAY_UNTIL_REBOOT)
        if path.exists():
            ctypes.windll.kernel32.MoveFileExW(str(path), None, MOVEFILE_DELAY_UNTIL_REBOOT)
    except Exception:
        pass
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def remove_legacy_app_local_secrets(*roots: Path) -> None:
    """Old profile lived next to the EXE/scripts â€” remove so the app folder deletes cleanly on any drive."""
    names = ("local-secrets", "local-secrets.to_delete", "local-secrets.__delete_me__")
    for root in roots:
        if not root:
            continue
        for name in names:
            legacy = Path(root) / name
            if legacy.exists():
                force_remove_tree(legacy)


def scrub_app_folder_side_effects(app_root: Path) -> None:
    """On start and exit: wipe any junk Chrome left beside the EXE (any drive)."""
    remove_legacy_app_local_secrets(app_root)
    # Chrome sometimes drops crashpad next to cwd if misconfigured â€” remove known junk names
    for name in ("Crashpad", "chrome_debug.log", "debug.log"):
        p = Path(app_root) / name
        if p.is_dir():
            force_remove_tree(p)
        elif p.is_file():
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


def prepare_chrome_profile() -> Path:
    d = ensure_user_writable(chrome_profile_dir())
    clear_chrome_lock_files(d)
    return d


def cleanup_after_use(*app_roots: Path, keep_login: bool = True) -> int:
    """
    End-of-session cleanup:
    - stop debug Chrome for our profile
    - clear locks + ephemeral caches
    - remove legacy local-secrets under app folders (any drive)
    - keep DistroKid login when keep_login=True
    """
    n = stop_chrome_using_profile()
    time.sleep(0.8)
    clear_chrome_lock_files()
    if keep_login:
        prune_ephemeral_chrome_cache()
        ensure_user_writable(chrome_profile_dir())
    else:
        root = chrome_data_root()
        if root.is_dir():
            force_remove_tree(root)
    for r in app_roots:
        scrub_app_folder_side_effects(Path(r))
    return n


def register_chrome_cleanup_on_exit(*app_roots: Path) -> None:
    roots = tuple(app_roots)

    def _cleanup() -> None:
        cleanup_after_use(*roots, keep_login=True)

    atexit.register(_cleanup)
