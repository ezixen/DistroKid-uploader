"""
DistroKid AI disclosure modal, explicit lyrics, Apple Music credits, mandatory checkboxes, Audiomack.
"""
from __future__ import annotations

import json
import time

from distrokid_credits import fill_apple_music_credits  # noqa: F401 — re-export for callers
from upload_settings import UploadSettings


def set_explicit_lyrics(cdp, *, explicit: bool = False, track_1based: int | None = None) -> dict:
    """Force Explicit lyrics Yes/No via DistroKid js-*-explicit-radio-button-N ids."""
    js = f"""
(() => {{
  const wantYes = {json.dumps(explicit)};
  const track = {json.dumps(track_1based)};
  const results = [];
  const clickId = (id) => {{
    const el = document.getElementById(id);
    if (!el) return false;
    if (!el.checked) el.click();
    return !!el.checked;
  }};
  if (track != null) {{
    const id = wantYes
      ? ('js-explicit-radio-button-' + track)
      : ('js-not-explicit-radio-button-' + track);
    const ok = clickId(id);
    return {{ok, track, id, wantYes}};
  }}
  // All tracks
  for (let n = 1; n <= 50; n++) {{
    const id = wantYes
      ? ('js-explicit-radio-button-' + n)
      : ('js-not-explicit-radio-button-' + n);
    const el = document.getElementById(id);
    if (!el) break;
    if (!el.checked) el.click();
    results.push({{n, id, checked: el.checked}});
  }}
  return {{ok: results.length > 0, count: results.length, wantYes, results: results.slice(0, 20)}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False}


def enable_audiomack(cdp) -> dict:
    """Enable free Audiomack extra/store; never touch paid extras."""
    return (
        cdp.evaluate(
            r"""
(() => {
  // Prefer store checkbox
  let el = document.querySelector('#chkaudiomack, input.distroStore[value=audiomack], input[value=audiomack]');
  if (!el) {
    el = [...document.querySelectorAll('input[type=checkbox]')].find(box => {
      const t = (box.closest('label')?.innerText || box.parentElement?.innerText || '').toLowerCase();
      return /\baudiomack\b/.test(t) && !/\$\s*\d|\/yr|\/mo|one-time/.test(t);
    });
  }
  if (!el) return {ok:false, reason:'audiomack-not-found'};
  if (!el.checked) el.click();
  return {ok:true, checked: el.checked, id: el.id || '', value: el.value || ''};
})()
"""
        )
        or {"ok": False}
    )


def apply_ai_disclosure_modal(cdp, s: UploadSettings) -> dict:
    """
    DistroKid AI gate uses input[name^=ai_gate_] (0=No, 1=Yes).
    Clicking Yes opens "Which parts of this song were AI-generated?" → set flags → Apply to all → Save.
    """
    if not s.ai_enabled:
        return (
            cdp.evaluate(
                r"""
(() => {
  const nos = [...document.querySelectorAll('input[type=radio][name^="ai_gate_"][value="0"]')];
  let n = 0;
  for (const el of nos) { if (!el.checked) el.click(); n++; }
  return {ok: nos.length > 0, which:'ai-off', count:n};
})()
"""
            )
            or {"ok": False}
        )

    opened = cdp.evaluate(
        r"""
(() => {
  const yes = document.querySelector('input[type=radio][name^="ai_gate_"][value="1"]');
  if (!yes) return {ok:false, reason:'ai-gate-yes-missing'};
  yes.scrollIntoView({block:'center'});
  yes.click();
  return {ok:true, name: yes.name, checked: yes.checked};
})()
"""
    ) or {"ok": False}
    time.sleep(1.0)

    # Open edit selections if summary shown instead of modal
    cdp.evaluate(
        r"""
(() => {
  if (document.querySelector('.swal2-popup.swal2-show')) return {ok:true, already:true};
  const edit = [...document.querySelectorAll('a,button,span,div')].find(el => {
    const t = (el.innerText || '').replace(/\s+/g,' ').trim().toLowerCase();
    return t === 'edit selections' || t.includes('edit selections');
  });
  if (edit) { edit.click(); return {ok:true, via:'edit'}; }
  return {ok:false};
})()
"""
    )
    time.sleep(0.8)

    # DistroKid Vocals/Instruments are radios — if both requested, prefer Instruments
    prefer_instruments = bool(s.ai_part_instruments or (s.ai_part_vocals and s.ai_part_instruments) or s.instrumental)
    prefer_vocals = bool(s.ai_part_vocals) and not prefer_instruments

    js = f"""
(() => {{
  const popup = document.querySelector('.swal2-popup.swal2-show, .swal2-popup');
  const root = (popup && /ai-generated|which parts/i.test(popup.innerText || '')) ? popup : document;
  const want = {{
    lyrics: {json.dumps(s.ai_lyrics)},
    music: {json.dumps(s.ai_music)},
    allAudio: {json.dumps(s.ai_all_audio)},
    partAudio: {json.dumps(s.ai_part_audio or s.ai.lower() == "both")},
    vocals: {json.dumps(prefer_vocals)},
    instruments: {json.dumps(prefer_instruments)},
  }};
  const setCheckByText = (re, on) => {{
    const boxes = [...root.querySelectorAll('input[type=checkbox]')];
    for (const box of boxes) {{
      const t = (box.closest('label')?.innerText || box.parentElement?.innerText || '').replace(/\\s+/g,' ').trim();
      if (!re.test(t)) continue;
      if (/apply these selections/i.test(t)) continue;
      if (box.checked !== on) box.click();
      return {{ok:true, text: t.slice(0, 70), checked: box.checked}};
    }}
    return {{ok:false}};
  }};
  const lyrics = setCheckByText(/lyrics\\s*\\(written by ai\\)/i, want.lyrics);
  const music = setCheckByText(/music\\s*\\(composed by ai\\)/i, want.music);
  const allAudio = setCheckByText(/all of the audio/i, want.allAudio);
  const part = setCheckByText(/part of the audio/i, want.partAudio);
  let vocals = {{ok:false}}, instruments = {{ok:false}};
  if (want.partAudio) {{
    const v = root.querySelector('input[type=radio][value="vocals"]') || [...root.querySelectorAll('input[type=radio]')].find(r => /vocals/i.test(r.closest('label')?.innerText||''));
    const i = root.querySelector('input[type=radio][value="instruments"]') || [...root.querySelectorAll('input[type=radio]')].find(r => /instruments/i.test(r.closest('label')?.innerText||''));
    if (want.instruments && i) {{ if (!i.checked) i.click(); instruments = {{ok:true, checked:i.checked}}; }}
    else if (want.vocals && v) {{ if (!v.checked) v.click(); vocals = {{ok:true, checked:v.checked}}; }}
  }}
  const applyAll = setCheckByText(/apply these selections to all songs/i, true);
  // also try exact apply checkbox if text match failed
  let apply2 = {{ok:false}};
  if (!applyAll.ok) {{
    const box = [...root.querySelectorAll('input[type=checkbox]')].find(b => /apply these selections to all songs/i.test((b.closest('label')?.innerText||b.parentElement?.innerText||'')));
    if (box) {{ if (!box.checked) box.click(); apply2 = {{ok:true, checked:box.checked}}; }}
  }}
  const save = [...root.querySelectorAll('button')].find(b => /^(save)$/i.test((b.innerText||'').trim()));
  if (save) save.click();
  return {{
    ok: true,
    opened: {json.dumps(opened)},
    lyrics, music, allAudio, part, vocals, instruments,
    applyAll: applyAll.ok ? applyAll : apply2,
    saved: !!save,
    note: 'Vocals/Instruments are radios; Instruments preferred when both requested'
  }};
}})()
"""
    result = cdp.evaluate(js) or {"ok": False, "opened": opened}
    time.sleep(0.7)
    # Ensure first-track instruments radio on page too
    if s.ai_part_instruments or prefer_instruments:
        cdp.evaluate(
            r"""
(() => {
  const el = document.querySelector('input[type=radio][name^="ai_partial_audio_type_"][value="instruments"]');
  if (el && !el.checked) el.click();
  return {ok: !!el, checked: el?.checked};
})()
"""
        )
    # Remove lingering SweetAlert containers so later "Copy credits" is not blocked
    time.sleep(0.3)
    cdp.evaluate(
        r"""
(() => {
  try { if (window.Swal) Swal.close(); } catch (e) {}
  document.querySelectorAll('.swal2-container').forEach(el => el.remove());
  return true;
})()
"""
    )
    return result


def set_mandatory_checkboxes(cdp, *, enabled: bool) -> dict:
    """Check or leave unchecked the bottom 'Important checkboxes (mandatory)' group."""
    if not enabled:
        return {"ok": True, "skipped": True, "enabled": False}
    return (
        cdp.evaluate(
            r"""
(() => {
  const checked = [];
  const boxes = [...document.querySelectorAll('input[type=checkbox]')];
  const patterns = [
    /youtube music/i,
    /non-standard capitalization|capitalization detected/i,
    /promo services|fake stream/i,
    /opted-in to snapchat|snapchat publishing/i,
    /authorized to sell it in stores worldwide/i,
    /other artist's name|without their approval/i,
    /distrokid distribution agreement/i,
  ];
  for (const box of boxes) {
    const t = (box.closest('label')?.innerText || box.parentElement?.innerText || '');
    if (!patterns.some(re => re.test(t))) continue;
    if (!box.checked) box.click();
    checked.push(t.replace(/\s+/g,' ').trim().slice(0, 70));
  }
  return {ok: checked.length > 0, count: checked.length, checked};
})()
"""
        )
        or {"ok": False}
    )
