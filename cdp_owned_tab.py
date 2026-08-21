"""Process-owned Chrome CDP tabs.

Each app *process* opens its own new tab(s) on first use and sticks to those
target ids for the rest of its life, so several BandCamp / DistroKid / DK-BC
instances can share one debug Chrome on port 9222 without stealing tabs.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

CDP_DEFAULT = "http://127.0.0.1:9222"

_lock = threading.Lock()
# key -> Chrome target id (from /json/list / /json/new)
_owned_ids: dict[str, str] = {}


def reset_owned_tabs() -> None:
    """Test helper — clear process ownership."""
    with _lock:
        _owned_ids.clear()


def owned_tab_ids() -> dict[str, str]:
    with _lock:
        return dict(_owned_ids)


def list_pages(cdp: str = CDP_DEFAULT) -> list[dict[str, Any]]:
    raw = urllib.request.urlopen(f"{cdp}/json/list", timeout=5).read().decode()
    data = json.loads(raw)
    if not isinstance(data, list):
        raise SystemExit("Unexpected CDP /json/list response")
    return data


def page_by_id(target_id: str, cdp: str = CDP_DEFAULT) -> dict[str, Any]:
    for page in list_pages(cdp=cdp):
        if page.get("id") == target_id and page.get("type") == "page":
            if page.get("webSocketDebuggerUrl"):
                return page
    raise SystemExit(
        f"Owned Chrome tab id={target_id!r} is gone. "
        "Leave each uploader's tab open, or restart that uploader instance."
    )


def open_new_tab(url: str, cdp: str = CDP_DEFAULT) -> dict[str, Any]:
    """Always create a new tab via CDP; return the page dict (id + ws url)."""
    q = urllib.parse.quote(url, safe=":/?&=#%")
    endpoint = f"{cdp}/json/new?{q}"
    try:
        raw = urllib.request.urlopen(endpoint, timeout=8).read().decode()
    except Exception:
        req = urllib.request.Request(endpoint, method="PUT")
        raw = urllib.request.urlopen(req, timeout=8).read().decode()
    page = json.loads(raw)
    if not isinstance(page, dict):
        raise SystemExit("CDP /json/new did not return a page object")
    tid = page.get("id")
    if not tid:
        raise SystemExit("CDP /json/new did not return a tab id")
    if not page.get("webSocketDebuggerUrl"):
        for _ in range(10):
            time.sleep(0.15)
            try:
                return page_by_id(str(tid), cdp=cdp)
            except SystemExit:
                continue
        raise SystemExit(f"CDP tab {tid!r} has no webSocketDebuggerUrl yet")
    return page


def claim_tab(key: str, url: str, cdp: str = CDP_DEFAULT) -> dict[str, Any]:
    """
    First call for *key* opens a new tab and remembers its id.
    Later calls reuse that same tab (re-resolve WS by id, never by URL).
    If the owned tab was closed, opens a replacement and remembers the new id.
    """
    with _lock:
        owned = _owned_ids.get(key)

    if owned:
        try:
            return page_by_id(owned, cdp=cdp)
        except SystemExit:
            with _lock:
                if _owned_ids.get(key) == owned:
                    _owned_ids.pop(key, None)

    page = open_new_tab(url, cdp=cdp)
    tid = str(page["id"])
    with _lock:
        existing = _owned_ids.get(key)
        if existing and existing != tid:
            try:
                return page_by_id(existing, cdp=cdp)
            except SystemExit:
                _owned_ids[key] = tid
                return page
        _owned_ids[key] = tid
        return page
