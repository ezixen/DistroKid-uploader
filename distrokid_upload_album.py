"""
DistroKid album uploader (form fill only — never final-publish without human OK).

Uses Chrome DevTools Protocol on port 9222.
Safeguard: if album title already exists → warning, no overwrite.
Settings: upload-settings.txt (releaser, real name, credits, instrumental, AI, prices).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import websocket

from album_media import (
    album_title_from_folder,
    app_dir,
    largest_jpg,
    numbered_wavs,
    title_from_filename,
)
from distrokid_form import (
    fill_by_selector,
    fill_track_song_title,
    set_checkbox_near_label,
    set_song_count,
    set_track_instrumental,
    snapshot_form,
)
from distrokid_finish import (
    apply_ai_disclosure_modal,
    enable_audiomack,
    fill_apple_music_credits,
    set_explicit_lyrics,
    set_mandatory_checkboxes,
)
from distrokid_stores import (
    configure_free_stores_only,
    handle_visible_popups,
    set_release_date_today,
)
from distrokid_tracks import (
    copy_songwriters_to_all_tracks,
    fill_songwriter_name_parts,
    set_cover_artwork,
    set_track_audio_file,
    wait_for_track_upload_slots,
)
from upload_settings import load_upload_settings

CDP = "http://127.0.0.1:9222"
DISTROKID_MYMUSIC = "https://distrokid.com/mymusic/"
DISTROKID_UPLOAD = "https://distrokid.com/new"


def cdp_alive() -> bool:
    try:
        urllib.request.urlopen(f"{CDP}/json/version", timeout=2)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _cdp_ws_url() -> str:
    tabs = json.loads(urllib.request.urlopen(f"{CDP}/json/list", timeout=5).read().decode())
    for t in tabs:
        url = t.get("url") or ""
        if t.get("type") == "page" and "distrokid.com" in url and t.get("webSocketDebuggerUrl"):
            return t["webSocketDebuggerUrl"]
    for t in tabs:
        if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
            return t["webSocketDebuggerUrl"]
    raise SystemExit("No Chrome page target on CDP 9222")


class Cdp:
    def __init__(self) -> None:
        self.ws = websocket.create_connection(_cdp_ws_url(), timeout=120)
        self._id = 0

    def call(self, method: str, params: dict | None = None, timeout: float = 120) -> dict:
        self._id += 1
        msg_id = self._id
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = json.loads(self.ws.recv())
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(data["error"])
                return data.get("result") or {}
        raise TimeoutError(method)

    def evaluate(self, expression: str, await_promise: bool = True) -> object:
        r = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": await_promise},
        )
        if r.get("exceptionDetails"):
            raise RuntimeError(r["exceptionDetails"])
        return (r.get("result") or {}).get("value")

    def navigate(self, url: str) -> None:
        self.call("Page.enable")
        self.call("Page.navigate", {"url": url})
        time.sleep(3)

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


def preview_folder(folder: Path) -> None:
    s = load_upload_settings(app_dir())
    wavs = numbered_wavs(folder)
    cover = largest_jpg(folder)
    print("Album title:", album_title_from_folder(folder), flush=True)
    print("Cover:", cover.name, flush=True)
    print(f"Prices: album={s.album_price}  track={s.track_price}", flush=True)
    print(f"Releaser: {s.releaser}", flush=True)
    print(f"Real name: {s.real_name} -> {s.songwriter_parts()}", flush=True)
    print(f"Artist: {s.artist}", flush=True)
    print(f"Instrumental: {'on' if s.instrumental else 'off'}", flush=True)
    print(f"AI: {s.ai} (lyrics={s.ai_lyrics} music={s.ai_music} all={s.ai_all_audio} part={s.ai_part_audio} instr={s.ai_part_instruments} vocals={s.ai_part_vocals})", flush=True)
    print(f"Explicit: {'on' if s.explicit else 'off'}  Audiomack: {'on' if s.audiomack else 'off'}  Mandatory boxes: {'on' if s.mandatory_checkboxes else 'off'}", flush=True)
    print(f"Credits: {s.credit_artist} -> {s.credit_roles}", flush=True)
    print("Tracks:", len(wavs), flush=True)
    for w in wavs:
        print(" ", w.name, "->", title_from_filename(w.name), flush=True)


def album_exists_on_distrokid(cdp: Cdp, album_title: str) -> dict:
    cdp.navigate(DISTROKID_MYMUSIC)
    time.sleep(1)
    cdp.evaluate(
        """
(() => {
  const links = [...document.querySelectorAll('a,button')];
  const hit = links.find(el => /show all releases/i.test(el.innerText||''));
  if (hit) hit.click();
  return !!hit;
})()
"""
    )
    time.sleep(1.5)
    js = f"""
(() => {{
  const want = {json.dumps(album_title)}.trim().toLowerCase().replace(/\\s+/g,' ');
  const text = document.body.innerText || '';
  const lines = text.split(/\\n+/).map(s => s.trim()).filter(Boolean);
  const albums = [];
  for (let i=0;i<lines.length;i++) {{
    if (/^\\d+\\s+tracks?$/i.test(lines[i+1]||'')) albums.push(lines[i]);
  }}
  const matches = albums.filter(a => a.toLowerCase().replace(/\\s+/g,' ') === want);
  return {{ exists: matches.length > 0, matches, albums: albums.slice(0,40), url: location.href }};
}})()
"""
    result = cdp.evaluate(js)
    return result if isinstance(result, dict) else {"exists": False, "matches": [], "url": ""}


def _assert_not_2fa(cdp: Cdp) -> None:
    body = (cdp.evaluate("(document.body&&document.body.innerText||'').slice(0,500)") or "").lower()
    if "2-step authentication" in body or "twofactor" in body.replace(" ", ""):
        raise SystemExit(
            "DistroKid is asking for 2-Step Authentication in the debug Chrome window.\n"
            "Paste the emailed code there, click Done, then re-run this upload."
        )


def fill_release_form(cdp: Cdp, folder: Path) -> int:
    s = load_upload_settings(app_dir())
    wavs = numbered_wavs(folder)
    cover = largest_jpg(folder)
    title = album_title_from_folder(folder)
    n_tracks = len(wavs)
    if n_tracks < 1:
        raise SystemExit("No numbered .wav tracks found")

    print("Opening DistroKid new-release flow (fresh)…", flush=True)
    cdp.navigate(DISTROKID_UPLOAD)
    time.sleep(3)
    _assert_not_2fa(cdp)

    # 1) Song count FIRST — DistroKid rebuilds the form if this changes later
    print(f"Set number of songs FIRST: {n_tracks}", flush=True)
    sc = set_song_count(cdp, n_tracks)
    print(" ", sc, flush=True)
    if not sc.get("ok"):
        raise SystemExit(f"Could not set howManySongs to {n_tracks}: {sc}")
    print("Waiting for DistroKid track upload slots…", flush=True)
    slots = wait_for_track_upload_slots(cdp, n_tracks, timeout_s=25.0)
    print(" ", slots, flush=True)
    if not slots.get("ok"):
        raise SystemExit(f"Track upload slots not ready for {n_tracks} songs: {slots}")
    _assert_not_2fa(cdp)

    # 2) All free stores + social destinations; never paid extras
    #    (Roblox / similar store popups: auto-check confirms + CONTINUE)
    include_social = getattr(s, "stores_include_social", True)
    print("Configure free stores + social destinations (no paid extras)…", flush=True)
    stores = configure_free_stores_only(cdp, include_social=include_social)
    print(
        " ",
        {
            k: stores.get(k)
            for k in ("ok", "enabledCount", "disabledCount", "disabled", "popups")
        },
        flush=True,
    )
    if s.audiomack:
        print("Enable Audiomack (free):", enable_audiomack(cdp), flush=True)

    snap = snapshot_form(cdp)
    print(f"DistroKid page: {snap.get('href')} inputs={snap.get('inputCount')}", flush=True)

    print("NOTE: genre and paid extras are left for you to set manually.", flush=True)

    print("Fill release identity…", flush=True)
    print(" album title:", fill_by_selector(cdp, "#albumTitleInput, input[name=albumtitle]", title), flush=True)
    print(" artist:", fill_by_selector(cdp, "#artistName, input[name=bandname]", s.artist), flush=True)
    print(" releaser:", fill_by_selector(cdp, "#recordLabel, input[name=recordLabel]", s.releaser), flush=True)

    first, middle, last = s.songwriter_parts()
    print(f" Songwriter real name parts: first={first!r} middle={middle!r} last={last!r}", flush=True)
    print(" ", fill_songwriter_name_parts(cdp, first, middle, last, track=1), flush=True)
    time.sleep(0.8)
    print(" Copy songwriters to all tracks (+ Do it confirm):", copy_songwriters_to_all_tracks(cdp), flush=True)
    time.sleep(1.0)

    release_day = s.release_date_iso()
    print(f"Release date -> {release_day}…", flush=True)
    print(" ", set_release_date_today(cdp, release_day), flush=True)

    print("Instrumental (album-level if present):", set_checkbox_near_label(cdp, ["instrumental", "contains no lyrics"], s.instrumental), flush=True)

    try:
        print("Upload cover…", flush=True)
        print(" ", set_cover_artwork(cdp, cover), flush=True)
        handle_visible_popups(cdp, rounds=1)
    except Exception as e:
        print(f"  cover file input: {e}", flush=True)

    # DistroKid uploads in parallel — attach every file quickly, do not wait for each finish
    print(f"Queue all {n_tracks} track audio files (parallel uploads OK)…", flush=True)
    for i, wav in enumerate(wavs, start=1):
        try:
            r = set_track_audio_file(cdp, i, wav)
            ok = r.get("ok") and (r.get("verify") or {}).get("ok", True)
            print(f"  [{i}/{n_tracks}] {wav.name} -> {ok} {r.get('verify') or r.get('upload')}", flush=True)
        except Exception as e:
            print(f"  [{i}/{n_tracks}] {wav.name} warn: {e}", flush=True)
    handle_visible_popups(cdp, rounds=1)

    print("Fill per-track titles / flags (uploads may still finish in background)…", flush=True)
    for i, wav in enumerate(wavs, start=1):
        t = title_from_filename(wav.name)
        print(f"Track {i}/{n_tracks}: title={t!r}", flush=True)
        print("  title:", fill_track_song_title(cdp, i, t), flush=True)
        if s.instrumental:
            print("  instrumental:", set_track_instrumental(cdp, i, True), flush=True)
        print("  explicit:", set_explicit_lyrics(cdp, explicit=s.explicit, track_1based=i), flush=True)
        if i == 1:
            print("AI disclosure modal (apply to all songs)…", flush=True)
            print(" ", apply_ai_disclosure_modal(cdp, s), flush=True)
            handle_visible_popups(cdp, rounds=2)

    # Re-assert Explicit=No on all tracks (guards against accidental Yes clicks)
    print(f"Explicit lyrics all tracks -> {'Yes' if s.explicit else 'No'}:", set_explicit_lyrics(cdp, explicit=s.explicit), flush=True)

    print("Apple Music credits (performer/producer + copy to all)…", flush=True)
    for r in fill_apple_music_credits(cdp, s):
        print(" ", r, flush=True)

    print(
        f"Mandatory important checkboxes -> {'ON' if s.mandatory_checkboxes else 'leave for human'}:",
        set_mandatory_checkboxes(cdp, enabled=s.mandatory_checkboxes),
        flush=True,
    )

    print("Re-apply release date…", flush=True)
    print(" ", set_release_date_today(cdp, release_day), flush=True)
    handle_visible_popups(cdp, rounds=2)

    print("", flush=True)
    print("DONE — DistroKid form filled as far as the UI allowed.", flush=True)
    print("Please VERIFY in Chrome (genre / any paid extras you want), then push/upload yourself if OK.", flush=True)
    print("This tool does NOT final-submit/publish.", flush=True)
    return 0


def run_upload(folder: Path, *, force: bool = False, dry_run: bool = False) -> int:
    folder = folder.resolve()
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")

    title = album_title_from_folder(folder)
    preview_folder(folder)

    if dry_run:
        print("Dry-run only — no DistroKid changes.", flush=True)
        return 0

    if not cdp_alive():
        raise SystemExit("Chrome CDP not on 9222. Run .\\2_start_chrome.ps1 and log into DistroKid first.")

    cdp = Cdp()
    try:
        print(f"Checking DistroKid for existing album titled: {title!r}", flush=True)
        check = album_exists_on_distrokid(cdp, title)
        if check.get("exists") and not force:
            print("WARNING: Album appears to ALREADY EXIST on DistroKid — will NOT overwrite.", flush=True)
            print(f"  Checked via: {check.get('url')}", flush=True)
            for m in check.get("matches") or []:
                print(f"  match: {m}", flush=True)
            print("  Re-run with --force only if you intentionally want to proceed anyway.", flush=True)
            return 3
        if check.get("exists") and force:
            print("WARNING: Album may already exist, but --force was set. Continuing…", flush=True)

        return fill_release_form(cdp, folder)
    finally:
        cdp.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="DistroKid album uploader (no overwrite if exists)")
    p.add_argument("folder", nargs="?", help="Album folder path")
    p.add_argument("--dry-run", action="store_true", help="Preview titles/settings only")
    p.add_argument("--force", action="store_true", help="Proceed even if album title seems to exist")
    args = p.parse_args(argv)
    if not args.folder:
        raise SystemExit("Usage: distrokid_upload_album.py <album-folder> [--dry-run] [--force]")
    return run_upload(Path(args.folder), force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
