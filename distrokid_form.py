"""
Best-effort DistroKid upload form fillers via CDP Runtime.evaluate.
Selectors are discovered by visible label / nearby text (UI changes often).
Store / popup / release-date helpers live in distrokid_stores.py.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from upload_settings import UploadSettings


def fill_text_near_label(
    cdp,
    label_substrings: list[str],
    value: str,
    *,
    exclude_ids: list[str] | None = None,
    exclude_names: list[str] | None = None,
) -> dict:
    js = f"""
(() => {{
  const want = {json.dumps([s.lower() for s in label_substrings])};
  const value = {json.dumps(value)};
  const excludeIds = new Set({json.dumps(exclude_ids or [])});
  const excludeNames = new Set({json.dumps(exclude_names or [])});
  const bad = (el) => excludeIds.has(el.id) || excludeNames.has(el.name)
    || /albumtitle|bandname|recordlabel/i.test(el.name+el.id);
  const nodes = [...document.querySelectorAll('label, div, span, p, th, td, h1, h2, h3, h4')];
  for (const n of nodes) {{
    const t = (n.innerText || '').trim().toLowerCase();
    if (!t || t.length > 80) continue;
    if (!want.some(w => t.includes(w))) continue;
    if (/album title/.test(t) && want.some(w => w.includes('song') || w === 'title')) continue;
    let root = n.closest('div,fieldset,tr,li,section') || n.parentElement;
    for (let i = 0; i < 6 && root; i++) {{
      const input = root.querySelector('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]), textarea');
      if (input && !bad(input)) {{
        input.focus();
        input.value = value;
        input.dispatchEvent(new Event('input', {{bubbles:true}}));
        input.dispatchEvent(new Event('change', {{bubbles:true}}));
        input.blur();
        return {{ok:true, label:t.slice(0,60), name:input.name||'', id:input.id||''}};
      }}
      root = root.parentElement;
    }}
  }}
  for (const input of document.querySelectorAll('input,textarea')) {{
    if (bad(input)) continue;
    const ph = (input.placeholder || '').toLowerCase();
    const aria = (input.getAttribute('aria-label') || '').toLowerCase();
    const name = (input.name || '').toLowerCase();
    if (want.some(w => ph.includes(w) || aria.includes(w) || name.includes(w))) {{
      input.focus();
      input.value = value;
      input.dispatchEvent(new Event('input', {{bubbles:true}}));
      input.dispatchEvent(new Event('change', {{bubbles:true}}));
      return {{ok:true, via:'placeholder', name:input.name||'', id:input.id||''}};
    }}
  }}
  return {{ok:false, tried: want}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def fill_by_selector(cdp, selector: str, value: str) -> dict:
    js = f"""
(() => {{
  const el = document.querySelector({json.dumps(selector)});
  if (!el) return {{ok:false, selector: {json.dumps(selector)}}};
  el.focus();
  el.value = {json.dumps(value)};
  el.dispatchEvent(new Event('input', {{bubbles:true}}));
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
  el.blur();
  return {{ok:true, selector: {json.dumps(selector)}, value: el.value}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def fill_track_song_title(cdp, track_index_1based: int, value: str) -> dict:
    """Fill DistroKid per-track song title by DOM order of title_<uuid> inputs."""
    js = f"""
(() => {{
  const i = {int(track_index_1based)};
  const value = {json.dumps(value)};
  const candidates = [...document.querySelectorAll('input[name^="title_"], input[id^="title_"]')]
    .filter(el => el.type !== 'hidden' && !/album/i.test(el.name+el.id));
  const el = candidates[i-1];
  if (!el) return {{ok:false, count: candidates.length, names: candidates.map(c=>c.name).slice(0,15)}};
  el.scrollIntoView({{block:'center'}});
  el.focus();
  el.value = value;
  el.dispatchEvent(new Event('input', {{bubbles:true}}));
  el.dispatchEvent(new Event('change', {{bubbles:true}}));
  el.blur();
  return {{ok:true, name: el.name||'', id: el.id||'', value: el.value, index: i}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def set_track_instrumental(cdp, track_index_1based: int, instrumental: bool) -> dict:
    js = f"""
(() => {{
  const i = {int(track_index_1based)};
  const wantInstr = {json.dumps(instrumental)};
  // radios often share a name per track; pick by nearby text + index
  const radios = [...document.querySelectorAll('input[type=radio]')].filter(el => {{
    const t = (el.closest('label')?.innerText || el.parentElement?.innerText || '').toLowerCase();
    return /instrumental|contains lyrics|no lyrics/.test(t);
  }});
  // Group by name
  const byName = {{}};
  for (const r of radios) {{
    const k = r.name || '_';
    (byName[k] = byName[k] || []).push(r);
  }}
  const groups = Object.values(byName);
  const group = groups[i-1] || groups[0];
  if (!group) return {{ok:false, radioCount: radios.length}};
  const target = group.find(r => {{
    const t = (r.closest('label')?.innerText || r.parentElement?.innerText || '').toLowerCase();
    return wantInstr ? /instrumental|no lyrics/.test(t) : /contains lyrics/.test(t);
  }}) || group[wantInstr ? group.length-1 : 0];
  if (!target.checked) target.click();
  return {{ok:true, name: target.name, checked: target.checked}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def set_checkbox_near_label(cdp, label_substrings: list[str], checked: bool) -> dict:
    js = f"""
(() => {{
  const want = {json.dumps([s.lower() for s in label_substrings])};
  const checked = {json.dumps(checked)};
  const nodes = [...document.querySelectorAll('label, div, span, p')];
  for (const n of nodes) {{
    const t = (n.innerText || '').trim().toLowerCase();
    if (!t || t.length > 100) continue;
    if (!want.some(w => t.includes(w))) continue;
    let root = n.closest('label,div,fieldset,tr,li,section') || n;
    const box = root.querySelector('input[type=checkbox], input[type=radio]');
    if (box) {{
      if (box.checked !== checked) box.click();
      return {{ok:true, label:t.slice(0,60), checked: box.checked}};
    }}
  }}
  return {{ok:false}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def set_song_count(cdp, n: int) -> dict:
    """MUST run before other fills — DistroKid rebuilds the form when this changes."""
    js = f"""
(() => {{
  const n = {int(n)};
  const sel = document.querySelector('#howManySongsOnThisAlbum, select[name=howmanysongs]');
  if (!sel) return {{ok:false, reason:'missing howManySongs select'}};
  const opt = [...sel.options].find(o => String(o.value) === String(n));
  if (!opt) return {{ok:false, reason:'no option for '+n, values:[...sel.options].map(o=>o.value)}};
  sel.value = String(n);
  sel.dispatchEvent(new Event('input', {{bubbles:true}}));
  sel.dispatchEvent(new Event('change', {{bubbles:true}}));
  if (typeof sel.onchange === 'function') try {{ sel.onchange(); }} catch(e) {{}}
  return {{ok:true, value: sel.value, text: opt.textContent.trim()}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def accept_free_terms(cdp) -> list[dict]:
    """Accept DistroKid free/required legal checkboxes (not paid packs)."""
    results = []
    # Distribution agreement
    results.append(
        cdp.evaluate(
            r"""
(() => {
  const el = [...document.querySelectorAll('input[type=checkbox]')].find(box => {
    const t = (box.closest('label')?.innerText || box.parentElement?.innerText || '').toLowerCase();
    return /distrokid distribution agreement|agree to the terms/.test(t);
  });
  if (!el) return {ok:false, which:'distribution agreement'};
  if (!el.checked) el.click();
  return {ok:true, which:'distribution agreement', checked: el.checked};
})()
"""
        )
    )
    # No promo services / fake streams
    results.append(
        cdp.evaluate(
            r"""
(() => {
  const el = document.querySelector('#areyousurepromoservices') || [...document.querySelectorAll('input[type=checkbox]')].find(box => {
    const t = (box.closest('label')?.innerText || box.parentElement?.innerText || '').toLowerCase();
    return /promo services|fake stream|guarantee streams/.test(t);
  });
  if (!el) return {ok:false, which:'promo services'};
  if (!el.checked) el.click();
  return {ok:true, which:'promo services', checked: el.checked};
})()
"""
        )
    )
    # Artist name rights
    results.append(
        cdp.evaluate(
            r"""
(() => {
  const el = [...document.querySelectorAll('input[type=checkbox]')].find(box => {
    const t = (box.closest('label')?.innerText || box.parentElement?.innerText || '').toLowerCase();
    return /other artist's name|without their approval/.test(t);
  });
  if (!el) return {ok:false, which:'artist name rights'};
  if (!el.checked) el.click();
  return {ok:true, which:'artist name rights', checked: el.checked};
})()
"""
        )
    )
    return results


def click_text(cdp, texts: list[str]) -> dict:
    js = f"""
(() => {{
  const want = {json.dumps([t.lower() for t in texts])};
  const els = [...document.querySelectorAll('a,button,div,span,label,li')];
  for (const el of els) {{
    const t = (el.innerText || el.textContent || '').trim().toLowerCase();
    if (!t || t.length > 80) continue;
    if (want.some(w => t === w || t.includes(w))) {{
      el.click();
      return {{ok:true, text:t.slice(0,80)}};
    }}
  }}
  return {{ok:false}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def set_file_input(cdp, index: int, path: Path) -> None:
    doc = cdp.call("DOM.getDocument", {"depth": -1})
    root = doc["root"]["nodeId"]
    cdp.evaluate(
        f"""
(() => {{
  const files = [...document.querySelectorAll('input[type=file]')];
  files.forEach((el,i) => el.setAttribute('data-dk-idx', String(i)));
  return {{count: files.length}};
}})()
"""
    )
    node = cdp.call(
        "DOM.querySelector",
        {"nodeId": root, "selector": f'input[type=file][data-dk-idx="{index}"]'},
    )
    node_id = node.get("nodeId")
    if not node_id:
        raise RuntimeError(f"file input index {index} not found")
    cdp.call("DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(path.resolve())]})


def apply_ai_settings(cdp, s: UploadSettings) -> list[dict]:
    results = []
    if not s.ai_enabled:
        results.append(
            cdp.evaluate(
                r"""
(() => {
  const el = [...document.querySelectorAll('input[type=radio],input[type=checkbox],label,button,div,span')].find(n => {
    const t = (n.innerText || n.value || '').toLowerCase();
    return /none of (this|it)|no ai|not generated by ai|no,? none/.test(t);
  });
  if (!el) return {ok:false, which:'ai off'};
  el.click();
  return {ok:true, which:'ai off'};
})()
"""
            )
        )
        return results
    results.append(
        cdp.evaluate(
            r"""
(() => {
  // Prefer explicit AI yes option near "generated by AI" / similar
  const nodes = [...document.querySelectorAll('input[type=radio],input[type=checkbox],label,button,div,span')];
  const hit = nodes.find(n => {
    const t = (n.innerText || n.getAttribute('aria-label') || '').toLowerCase();
    return /yes.*ai|generated by ai|ai-generated|contains ai/.test(t) && t.length < 120;
  });
  if (hit) { hit.click(); return {ok:true, which:'ai yes', text:(hit.innerText||'').slice(0,80)}; }
  return {ok:false, which:'ai yes'};
})()
"""
        )
    )
    time.sleep(0.5)
    if s.ai_lyrics:
        results.append(set_checkbox_near_label(cdp, ["the lyrics", "lyrics —", "lyrics -"], True))
    if s.ai_music and not (s.ai_part_audio or s.ai.lower() == "both"):
        results.append(set_checkbox_near_label(cdp, ["the music", "composed the melody", "music —", "music -"], True))
    if s.ai_all_audio:
        results.append(set_checkbox_near_label(cdp, ["all of the audio"], True))
    if s.ai_part_audio or s.ai.lower() == "both":
        # Prefer DistroKid "Part of the audio" then Instruments (user-corrected default)
        results.append(set_checkbox_near_label(cdp, ["part of the audio"], True))
        time.sleep(0.4)
        if getattr(s, "ai_part_instruments", True) or s.ai_music:
            results.append(
                cdp.evaluate(
                    r"""
(() => {
  const nodes = [...document.querySelectorAll('input[type=checkbox],label,span,div')];
  const hit = nodes.find(n => {
    const t = (n.innerText || '').replace(/\s+/g,' ').trim();
    return /^(instruments)$/i.test(t) || /^instruments\b/i.test(t) && t.length < 40;
  });
  if (!hit) return {ok:false, which:'instruments'};
  hit.click();
  return {ok:true, which:'instruments', text:(hit.innerText||'').slice(0,40)};
})()
"""
                )
            )
        if getattr(s, "ai_part_vocals", False):
            results.append(set_checkbox_near_label(cdp, ["vocals"], True))
    if s.ai_all_audio:
        if s.ai_artist_persona == "ai":
            results.append(click_text(cdp, ["ai persona", "an ai"]))
        else:
            results.append(click_text(cdp, ["a human", "human"]))
    return results


def apply_credits_to_tracks(cdp, s: UploadSettings, track_count: int) -> list[dict]:
    """
    For each track: open credits if needed, set contributor name + roles from dropdowns.
    DistroKid UI varies; we try common patterns and report what stuck.
    """
    out = []
    for i in range(track_count):
        # Try open credits for track i
        out.append(
            cdp.evaluate(
                f"""
(() => {{
  const buttons = [...document.querySelectorAll('a,button,div,span')].filter(el => {{
    const t = (el.innerText || '').trim();
    if (!/credit/i.test(t) || t.length > 40) return false;
    const href = (el.getAttribute('href') || el.closest('a')?.getAttribute('href') || '').toLowerCase();
    // Never follow DistroKid global Credits nav
    if (/\\/credits/.test(href) || /ref=globalmenu/.test(href)) return false;
    if (/globalmenu|main-nav|navbar|topnav/i.test(el.className || '') || /globalmenu|main-nav/i.test(el.parentElement?.className || '')) return false;
    return true;
  }});
  if (buttons[{i}]) {{ buttons[{i}].click(); return {{ok:true, i:{i}, text:(buttons[{i}].innerText||'').slice(0,40)}}; }}
  if (buttons[0] && {i}===0) {{ buttons[0].click(); return {{ok:true, i:0, via:'first', text:(buttons[0].innerText||'').slice(0,40)}}; }}
  return {{ok:false, creditButtons: buttons.length}};
}})()
"""
            )
        )
        time.sleep(0.6)
        # Fill artist name in credit fields
        out.append(fill_text_near_label(cdp, ["artist", "name", "contributor", "who"], s.credit_artist))
        for role in s.credit_roles:
            out.append(
                cdp.evaluate(
                    f"""
(() => {{
  const role = {json.dumps(role)}.toLowerCase();
  const selects = [...document.querySelectorAll('select')];
  for (const sel of selects) {{
    const opts = [...sel.options];
    const hit = opts.find(o => (o.textContent||'').trim().toLowerCase() === role
      || (o.textContent||'').trim().toLowerCase().includes(role));
    if (hit) {{
      sel.value = hit.value;
      sel.dispatchEvent(new Event('change', {{bubbles:true}}));
      return {{ok:true, role: hit.textContent.trim()}};
    }}
  }}
  // clickable dropdown items
  const items = [...document.querySelectorAll('li,div,button,span,a')];
  const item = items.find(el => {{
    const t = (el.innerText||'').trim().toLowerCase();
    return t === role || t.includes(role);
  }});
  if (item) {{ item.click(); return {{ok:true, role, via:'click'}}; }}
  return {{ok:false, role}};
}})()
"""
                )
            )
            time.sleep(0.3)
        # try save/done on credit modal (avoid loose matches that hit DistroKid nav)
        out.append(
            cdp.evaluate(
                r"""
(() => {
  const popup = document.querySelector('.swal2-popup, [role=dialog], .modal, .fancybox-content');
  const root = popup || document;
  const buttons = [...root.querySelectorAll('button, a.btn, input[type=button], input[type=submit]')];
  const hit = buttons.find(el => {
    const t = (el.innerText || el.value || '').trim().toLowerCase();
    return /^(done|save|add|ok|close)$/.test(t) || t === 'save credits' || t === 'done';
  });
  if (!hit) return {ok:false, which:'credit-done'};
  hit.click();
  return {ok:true, which:'credit-done', text:(hit.innerText||hit.value||'').slice(0,40)};
})()
"""
            )
        )
        time.sleep(0.4)
    return out


def snapshot_form(cdp) -> dict:
    return (
        cdp.evaluate(
            r"""
(() => {
  const inputs = [...document.querySelectorAll('input,select,textarea')].slice(0,150).map(el => ({
    tag: el.tagName, type: el.type||'', name: el.name||'', id: el.id||'',
    placeholder: el.placeholder||'', value: (el.value||'').toString().slice(0,80),
    checked: !!el.checked,
  }));
  return {href: location.href, title: document.title, inputCount: inputs.length, inputs,
          body: (document.body.innerText||'').slice(0,2000)};
})()
"""
        )
        or {}
    )
