"""
DistroKid per-track uploads + songwriter real-name helpers.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def set_file_input_selector(cdp, selector: str, path: Path, *, settle_s: float = 0.0) -> dict:
    """
    Set a specific file input by CSS selector (never guess by global index).

    Uses a shallow DOM snapshot — do NOT walk depth=-1 (that made each track
    attach feel like a full upload wait on large DistroKid pages).
    """
    found = cdp.evaluate(
        f"""
(() => {{
  const el = document.querySelector({json.dumps(selector)});
  if (!el) return {{ok:false, selector: {json.dumps(selector)}}};
  el.scrollIntoView({{block:'nearest', inline:'nearest'}});
  return {{ok:true, id: el.id||'', name: el.name||''}};
}})()
"""
    ) or {"ok": False}
    if not found.get("ok"):
        return found
    if settle_s > 0:
        time.sleep(settle_s)
    # depth 0 is enough: querySelector searches the whole document from root
    doc = cdp.call("DOM.getDocument", {"depth": 0})
    root = doc["root"]["nodeId"]
    node = cdp.call("DOM.querySelector", {"nodeId": root, "selector": selector})
    node_id = node.get("nodeId")
    if not node_id:
        return {"ok": False, "reason": "nodeId missing", "selector": selector}
    cdp.call("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(path.resolve())]})
    return {"ok": True, "selector": selector, "file": path.name, **{k: found.get(k) for k in ("id", "name")}}


def set_cover_artwork(cdp, path: Path) -> dict:
    return set_file_input_selector(cdp, "#artwork, input[type=file][name=artwork]", path, settle_s=0.1)


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

    Fire-and-forget: only checks that the <input> accepted a File.
    Does NOT wait for DistroKid HTTP upload / progress bars.
    """
    n = int(track_1based)
    selector = f"#js-track-upload-{n}"
    put = set_file_input_selector(cdp, selector, path, settle_s=0.0)
    if not put.get("ok"):
        # one retry after DistroKid may have rebuilt the input
        time.sleep(0.15)
        put = set_file_input_selector(cdp, selector, path, settle_s=0.0)
    verify = cdp.evaluate(
        f"""
(() => {{
  const el = document.querySelector('#js-track-upload-' + {n});
  if (!el) return {{ok:false, reason:'missing'}};
  const name = (el.files && el.files[0] && el.files[0].name) || '';
  return {{ok: !!name, fileName: name}};
}})()
"""
    ) or {}
    return {"ok": bool(put.get("ok") and verify.get("ok")), "track": n, "upload": put, "verify": verify}


def queue_all_track_audio(cdp, wavs: list[Path]) -> list[dict]:
    """
    Attach every wav into #js-track-upload-1..N as fast as possible so DistroKid
    can upload them in parallel. Never waits on progress.
    """
    out: list[dict] = []
    for i, wav in enumerate(wavs, start=1):
        try:
            out.append(set_track_audio_file(cdp, i, wav))
        except Exception as e:
            out.append({"ok": False, "track": i, "error": str(e), "file": wav.name})
    return out



def fill_songwriter_name_parts(cdp, first: str, middle: str, last: str, *, track: int = 1) -> dict:
    """Fill DistroKid first/middle/last for the first songwriter row on a track."""
    return fill_songwriters(cdp, [(first, middle, last)], track=track)


def fill_songwriters(
    cdp,
    people: list[tuple[str, str, str]],
    *,
    track: int = 1,
) -> dict:
    """
    Fill one or more songwriter PERSONS on DistroKid track ``track``.

    Each tuple is ONE person (First, Middle, Last). Extra people: click
    DistroKid "Add another songwriter" until enough rows exist, then fill.
    """
    cleaned = [(f or "", m or "", l or "") for f, m, l in (people or []) if (f or m or l)]
    if not cleaned:
        return {"ok": False, "reason": "no-songwriters"}

    steps: list[dict] = []
    # Ensure enough rows (DOM updates after each Add click)
    for _ in range(max(0, len(cleaned) - 1) + 3):
        info = cdp.evaluate(
            f"""
(() => {{
  const track = {int(track)};
  const need = {len(cleaned)};
  const listRows = () => {{
    const firsts = [...document.querySelectorAll('input[name^="songwriter_real_name_first"]')];
    return firsts.map(f => {{
      const suffix = f.name.slice('songwriter_real_name_first'.length);
      return {{
        suffix,
        first: f.name,
        middle: document.querySelector('input[name="songwriter_real_name_middle' + suffix + '"]') ? true : false,
        last: document.querySelector('input[name="songwriter_real_name_last' + suffix + '"]') ? true : false,
      }};
    }}).filter(r => r.middle || r.last);
  }};
  let rows = listRows().filter(r => r.suffix === String(track) || r.suffix.startsWith(String(track) + '_') || r.suffix.startsWith(String(track)));
  if (!rows.length) rows = listRows();
  if (rows.length >= need) return {{ok:true, ready:true, count: rows.length, rows}};
  const els = [...document.querySelectorAll('span.linklike, a, button, span')];
  const hit = els.find(el => {{
    const t = (el.innerText || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    if (!t || t.length > 80) return false;
    if (t.includes('copy these')) return false;
    return (t.includes('add another') && (t.includes('songwriter') || t.includes('writer')))
      || t === 'add another songwriter'
      || t === 'add another';
  }});
  if (!hit) return {{ok:false, ready:false, count: rows.length, reason:'add-link-not-found', rows}};
  hit.scrollIntoView({{block:'center'}});
  hit.click();
  return {{ok:true, ready:false, clicked:true, count: rows.length, text:(hit.innerText||'').trim().slice(0,60)}};
}})()
"""
        ) or {"ok": False}
        steps.append({"ensure": info})
        if info.get("ready"):
            break
        time.sleep(0.45)

    filled = cdp.evaluate(
        f"""
(() => {{
  const track = {int(track)};
  const people = {json.dumps([{"first": a, "middle": b, "last": c} for a, b, c in cleaned])};
  const setEl = (el, value) => {{
    if (!el) return {{ok:false}};
    el.focus();
    el.value = value;
    el.dispatchEvent(new Event('input', {{bubbles:true}}));
    el.dispatchEvent(new Event('change', {{bubbles:true}}));
    el.blur();
    return {{ok:true, value: el.value}};
  }};
  const listRows = () => {{
    const firsts = [...document.querySelectorAll('input[name^="songwriter_real_name_first"]')];
    return firsts.map(f => {{
      const suffix = f.name.slice('songwriter_real_name_first'.length);
      return {{
        suffix,
        first: f,
        middle: document.querySelector('input[name="songwriter_real_name_middle' + suffix + '"]'),
        last: document.querySelector('input[name="songwriter_real_name_last' + suffix + '"]'),
      }};
    }}).filter(r => r.first && r.last);
  }};
  let rows = listRows().filter(r => r.suffix === String(track) || r.suffix.startsWith(String(track) + '_') || r.suffix.startsWith(String(track)));
  if (!rows.length) rows = listRows();
  // Prefer track-1 style single suffix first, then extras in DOM order
  rows = rows.slice().sort((a, b) => {{
    if (a.suffix === String(track)) return -1;
    if (b.suffix === String(track)) return 1;
    return String(a.suffix).localeCompare(String(b.suffix), undefined, {{numeric:true}});
  }});
  const out = [];
  for (let i = 0; i < people.length; i++) {{
    const p = people[i];
    const row = rows[i];
    if (!row) {{ out.push({{ok:false, person:i+1, reason:'row-missing'}}); continue; }}
    const f = setEl(row.first, p.first);
    const m = setEl(row.middle, p.middle);
    const l = setEl(row.last, p.last);
    out.push({{ok: !!(f.ok && l.ok), person:i+1, suffix: row.suffix, first:f, middle:m, last:l}});
  }}
  return {{ok: out.every(x => x.ok), count: out.length, people: out, rowCount: rows.length}};
}})()
"""
    ) or {"ok": False}
    return {"ok": bool(filled.get("ok")), "filled": filled, "steps": steps}



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
