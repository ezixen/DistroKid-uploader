"""
DistroKid per-track uploads + songwriter real-name helpers.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def set_file_input_selector(cdp, selector: str, path: Path, *, settle_s: float = 0.05) -> dict:
    """Set a specific file input by CSS selector (never guess by global index)."""
    doc = cdp.call("DOM.getDocument", {"depth": -1})
    root = doc["root"]["nodeId"]
    found = cdp.evaluate(
        f"""
(() => {{
  const el = document.querySelector({json.dumps(selector)});
  if (!el) return {{ok:false, selector: {json.dumps(selector)}}};
  el.setAttribute('data-dk-file-target', '1');
  el.scrollIntoView({{block:'center', inline:'nearest'}});
  return {{ok:true, id: el.id||'', name: el.name||''}};
}})()
"""
    ) or {"ok": False}
    if not found.get("ok"):
        return found
    if settle_s > 0:
        time.sleep(settle_s)
    node = cdp.call(
        "DOM.querySelector",
        {"nodeId": root, "selector": 'input[type=file][data-dk-file-target="1"]'},
    )
    node_id = node.get("nodeId")
    cdp.evaluate(
        """(() => {
  document.querySelectorAll('input[type=file][data-dk-file-target]').forEach(el => el.removeAttribute('data-dk-file-target'));
})()"""
    )
    if not node_id:
        return {"ok": False, "reason": "nodeId missing", "selector": selector}
    cdp.call("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(path.resolve())]})
    return {"ok": True, "selector": selector, "file": path.name, **{k: found.get(k) for k in ("id", "name")}}


def set_cover_artwork(cdp, path: Path) -> dict:
    return set_file_input_selector(cdp, "#artwork, input[type=file][name=artwork]", path, settle_s=0.15)


def wait_for_track_upload_slots(cdp, n_tracks: int, *, timeout_s: float = 25.0) -> dict:
    """Poll until DistroKid has created #js-track-upload-1..N after song-count change."""
    n = int(n_tracks)
    deadline = time.time() + timeout_s
    last: dict = {"ok": False}
    while time.time() < deadline:
        last = cdp.evaluate(
            f"""
(() => {{
  const n = {n};
  const ids = [...document.querySelectorAll('input[type=file][id^="js-track-upload-"]')]
    .map(e => e.id);
  const missing = [];
  for (let i = 1; i <= n; i++) {{
    if (!document.getElementById('js-track-upload-' + i)) missing.push(i);
  }}
  return {{ok: missing.length === 0, found: ids.length, missing, ids: ids.slice(0, 20)}};
}})()
"""
        ) or {"ok": False}
        if last.get("ok"):
            return last
        time.sleep(0.35)
    return {**last, "ok": False, "timeout": True, "timeout_s": timeout_s}


def set_track_audio_file(cdp, track_1based: int, path: Path) -> dict:
    """
    Attach audio to DistroKid's numbered track slot (#js-track-upload-N).
    Does NOT wait for DistroKid to finish uploading — the site uploads in parallel.
    """
    n = int(track_1based)
    selector = f"#js-track-upload-{n}"
    meta = cdp.evaluate(
        f"""
(() => {{
  const n = {n};
  const el = document.querySelector('#js-track-upload-' + n);
  if (!el) {{
    const ids = [...document.querySelectorAll('input[type=file][id^="js-track-upload-"]')].map(e => e.id);
    return {{ok:false, reason:'missing', want: 'js-track-upload-' + n, foundIds: ids}};
  }}
  el.scrollIntoView({{block:'nearest', inline:'nearest'}});
  return {{ok:true, id: el.id}};
}})()
"""
    ) or {"ok": False}
    if not meta.get("ok"):
        return meta
    put = set_file_input_selector(cdp, selector, path, settle_s=0.05)
    # Instant check that the input accepted a file (not DistroKid upload progress)
    verify = cdp.evaluate(
        f"""
(() => {{
  const el = document.querySelector('#js-track-upload-' + {n});
  if (!el) return {{ok:false}};
  const name = (el.files && el.files[0] && el.files[0].name) || '';
  return {{ok: !!name, fileName: name}};
}})()
"""
    ) or {}
    return {"ok": bool(put.get("ok")), "track": n, "upload": put, "verify": verify, "meta": meta}


def fill_songwriter_name_parts(cdp, first: str, middle: str, last: str, *, track: int = 1) -> dict:
    """Fill DistroKid first/middle/last songwriter fields for one track (default track 1)."""
    js = f"""
(() => {{
  const track = {int(track)};
  const first = {json.dumps(first)};
  const middle = {json.dumps(middle)};
  const last = {json.dumps(last)};
  const set = (sel, value) => {{
    const el = document.querySelector(sel);
    if (!el) return {{ok:false, sel}};
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event('input', {{bubbles:true}}));
    el.dispatchEvent(new Event('change', {{bubbles:true}}));
    el.blur();
    return {{ok:true, sel, value: el.value}};
  }};
  // Prefer numbered fields: songwriter_real_name_first1 / middle1 / last1
  let f = set('input[name="songwriter_real_name_first' + track + '"]', first);
  let m = set('input[name="songwriter_real_name_middle' + track + '"]', middle);
  let l = set('input[name="songwriter_real_name_last' + track + '"]', last);
  if (!f.ok) f = set('input[name^=songwriter_real_name_first]', first);
  if (!m.ok) m = set('input[name^=songwriter_real_name_middle]', middle);
  if (!l.ok) l = set('input[name^=songwriter_real_name_last]', last);
  return {{ok: !!(f.ok && l.ok), first: f, middle: m, last: l}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def copy_songwriters_to_all_tracks(cdp) -> dict:
    """Click DistroKid copy-songwriters link and confirm the 'Do it' popup."""
    from distrokid_dialogs import click_and_confirm

    steps = click_and_confirm(
        cdp,
        lambda: cdp.evaluate(
            r"""
(() => {
  // Prefer exact short link text on span.linklike (avoid parent divs that also contain "Add another…")
  const els = [...document.querySelectorAll('span.linklike, a, button, span')];
  const hit = els.find(el => {
    const t = (el.innerText || '').replace(/\s+/g, ' ').trim().toLowerCase();
    if (!t) return false;
    if (t.includes('add another')) return false;
    return t === 'copy these songwriters to all tracks on this album'
      || (t.startsWith('copy these songwriters') && t.length < 70);
  });
  if (!hit) return {ok:false, reason:'copy-link-not-found'};
  hit.scrollIntoView({block:'center'});
  hit.click();
  return {ok:true, tag: hit.tagName, text:(hit.innerText||'').replace(/\s+/g,' ').trim().slice(0,80)};
})()
"""
        )
        or {"ok": False},
        wait_s=1.0,
        rounds=4,
    )
    clicked = (steps[0] or {}).get("click") or {}
    confirmed = any(s.get("confirm", {}).get("ok") for s in steps[1:])
    return {"ok": bool(clicked.get("ok")), "clicked": clicked, "confirmed": confirmed, "steps": steps}


def set_track_ai_part_instruments(cdp, track_1based: int, *, vocals: bool = False, instruments: bool = True) -> dict:
    """Per-track: Yes → Part of the audio → Instruments (and/or Vocals)."""
    js = f"""
(() => {{
  const n = {int(track_1based)};
  const wantVocals = {json.dumps(vocals)};
  const wantInstr = {json.dumps(instruments)};
  // Find a root near "Track N"
  const nodes = [...document.querySelectorAll('div,section,fieldset,li,article')];
  let root = null;
  for (const el of nodes) {{
    const kids = el.children ? [...el.children] : [];
    const head = kids.find(c => {{
      const t = (c.innerText || '').trim();
      return new RegExp('^Track\\\\s*' + n + '\\\\b', 'i').test(t) && t.length < 24;
    }});
    if (head) {{ root = el; break; }}
  }}
  if (!root) {{
    // fallback: Nth title_ field's ancestor
    const titles = [...document.querySelectorAll('input[name^="title_"]')];
    const title = titles[n-1];
    root = title?.closest('div,section,fieldset,li') || document.body;
  }}
  const clickMatching = (re) => {{
    const cand = [...root.querySelectorAll('input[type=radio],input[type=checkbox],label,button,div,span')];
    const hit = cand.find(el => {{
      const t = (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g,' ').trim();
      return re.test(t) && t.length < 140;
    }});
    if (!hit) return false;
    hit.click();
    return true;
  }};
  // AI Yes inside this track block
  clickMatching(/does this song include ai|^yes$/i);
  const yesRadios = [...root.querySelectorAll('input[type=radio]')].filter(r => {{
    const t = (r.closest('label')?.innerText || r.parentElement?.innerText || '').toLowerCase();
    return /ai-generated|include ai|^\\s*yes\\s*$/.test(t);
  }});
  for (const r of yesRadios) {{
    const t = (r.closest('label')?.innerText || '').trim().toLowerCase();
    if (t === 'yes' || /^yes\\b/.test(t)) {{ if (!r.checked) r.click(); break; }}
  }}
  // Part of the audio
  clickMatching(/part of the audio/i);
  // Instruments / Vocals sub-options
  let instr = false, voc = false;
  if (wantInstr) instr = clickMatching(/^instruments$|part of the audio \\(instruments\\)|^instruments\\b/i);
  if (wantVocals) voc = clickMatching(/^vocals$/i);
  return {{ok:true, track:n, instruments:instr, vocals:voc}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}
