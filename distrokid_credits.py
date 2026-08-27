"""
DistroKid Apple Music credits (performer / producer rows + copy to all).
"""
from __future__ import annotations

import json
import time

from distrokid_dialogs import click_and_confirm
from upload_settings import UploadSettings


def _force_close_swal(cdp) -> dict:
    return (
        cdp.evaluate(
            r"""
(() => {
  try { if (window.Swal) Swal.close(); } catch (e) {}
  document.querySelectorAll('.swal2-container').forEach(el => el.remove());
  return {ok:true, left: document.querySelectorAll('.swal2-container').length};
})()
"""
        )
        or {"ok": False}
    )


def _open_add_credits(cdp) -> dict:
    return (
        cdp.evaluate(
            r"""
(() => {
  const hit = [...document.querySelectorAll('.requirements-item-title')]
    .find(el => ((el.innerText || '').replace(/\s+/g, ' ').trim()) === 'Add credits for each song on this release')
    || document.querySelector('.requirements-item-title');
  if (!hit) return {ok:false, reason:'add-credits-button-missing'};
  hit.scrollIntoView({block:'center'});
  hit.click();
  return {ok:true, cls: String(hit.className), text:(hit.innerText||'').trim().slice(0,60)};
})()
"""
        )
        or {"ok": False}
    )


def _fill_one_credit(cdp, role_sel: str, name_sel: str, role: str, name: str) -> dict:
    return cdp.evaluate(
        f"""
(() => {{
  const roleWant = {json.dumps(role)};
  const name = {json.dumps(name)};
  const sel = document.querySelector({json.dumps(role_sel)});
  const input = document.querySelector({json.dumps(name_sel)});
  if (!sel || !input) return {{ok:false, reason:'missing', role_sel:{json.dumps(role_sel)}, name_sel:{json.dumps(name_sel)}}};
  const opts = [...sel.options];
  let hit = opts.find(o => (o.textContent || '').trim().toLowerCase() === roleWant.toLowerCase());
  if (!hit) hit = opts.find(o => (o.textContent || '').trim().toLowerCase().includes(roleWant.toLowerCase())
    && !(/co-executive/i.test(o.textContent||'') && /^executive producer$/i.test(roleWant)));
  if (!hit) return {{ok:false, reason:'role-option', roleWant, sample: opts.map(o=>o.textContent.trim()).slice(0,12)}};
  sel.value = hit.value;
  sel.dispatchEvent(new Event('input', {{bubbles:true}}));
  sel.dispatchEvent(new Event('change', {{bubbles:true}}));
  input.focus();
  input.value = name;
  input.dispatchEvent(new Event('input', {{bubbles:true}}));
  input.dispatchEvent(new Event('change', {{bubbles:true}}));
  input.blur();
  return {{ok:true, role: hit.textContent.trim(), name: input.value, roleValue: sel.value}};
}})()
"""
    ) or {"ok": False}


def _ensure_credit_rows(cdp, *, kind: str, need: int) -> dict:
    """
    Ensure DistroKid has need rows for kind in {'performer','producer'} on track 1.
    Clicks "Add another…" inside that requirements section until enough #track-1-{kind}-N-role exist.
    """
    steps: list[dict] = []
    kind = kind.strip().lower()
    need = max(1, int(need))
    for _ in range(need + 4):
        info = cdp.evaluate(
            f"""
(() => {{
  const kind = {json.dumps(kind)};
  const need = {need};
  const count = () => {{
    let n = 0;
    for (let i = 1; i <= 40; i++) {{
      if (document.getElementById('track-1-' + kind + '-' + i + '-role')) n = i;
      else break;
    }}
    return n;
  }};
  const have = count();
  if (have >= need) return {{ok:true, ready:true, have}};
  const root = document.querySelector('.requirements-' + kind) || document.body;
  const els = [...root.querySelectorAll('span.linklike, a, button, span')];
  const hit = els.find(el => {{
    const t = (el.innerText || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    if (!t || t.length > 90) return false;
    if (t.includes('copy')) return false;
    return t.includes('add another') || /^add\\b/.test(t);
  }});
  if (!hit) return {{ok:false, ready:false, have, reason:'add-link-not-found'}};
  hit.scrollIntoView({{block:'center'}});
  hit.click();
  return {{ok:true, ready:false, clicked:true, have, text:(hit.innerText||'').trim().slice(0,60)}};
}})()
"""
        ) or {"ok": False}
        steps.append(info)
        if info.get("ready"):
            return {"ok": True, "have": info.get("have"), "steps": steps}
        if not info.get("ok") and info.get("reason") == "add-link-not-found":
            return {"ok": False, "reason": "add-link-not-found", "have": info.get("have"), "steps": steps}
        time.sleep(0.4)
    last = steps[-1] if steps else {}
    return {"ok": bool(last.get("ready")), "have": last.get("have"), "steps": steps}


def _copy_credit_section(cdp, *, kind: str) -> list[dict]:
    kind = kind.strip().lower()
    return click_and_confirm(
        cdp,
        lambda: cdp.evaluate(
            f"""
(() => {{
  const kind = {json.dumps(kind)};
  const root = document.querySelector('.requirements-' + kind);
  const hit = (root && (root.querySelector('.credit-action.copy-credit .linklike')
    || root.querySelector('.credit-action.copy-credit')))
    || document.querySelector('.requirements-' + kind + ' .credit-action.copy-credit .linklike')
    || document.querySelector('.requirements-' + kind + ' .credit-action.copy-credit');
  if (!hit) return {{ok:false, reason:'copy-' + kind + '-missing'}};
  hit.click();
  return {{ok:true, text:(hit.innerText||'').replace(/\\s+/g,' ').trim().slice(0,70)}};
}})()
"""
        )
        or {"ok": False},
        wait_s=1.0,
        rounds=4,
    )


def fill_apple_music_credits(cdp, s: UploadSettings) -> list[dict]:
    """
    Apple Music "Add credits for each song on this release":
      performers (instrument/players): #track-1-performer-N-role / -name
      producers: #track-1-producer-N-role / -name
    Then copy each section to all tracks (+ Do it).
    """
    out: list[dict] = []
    players = s.player_names()
    producers = s.producer_names()
    player_role = s.resolved_player_role()
    producer_role = s.resolved_producer_role()

    out.append({"close_swal": _force_close_swal(cdp)})
    time.sleep(0.35)
    out.append(_open_add_credits(cdp))
    time.sleep(1.2)

    # --- Performers / instrument players ---
    if players:
        ens = _ensure_credit_rows(cdp, kind="performer", need=len(players))
        out.append({"ensure_performers": ens})
        for i, name in enumerate(players, start=1):
            filled = _fill_one_credit(
                cdp,
                f"#track-1-performer-{i}-role",
                f"#track-1-performer-{i}-name",
                player_role,
                name,
            )
            out.append({"performer": i, "result": filled})
            time.sleep(0.2)
        _force_close_swal(cdp)
        time.sleep(0.25)
        out.extend(_copy_credit_section(cdp, kind="performer"))

    # --- Producers ---
    if producers:
        ens = _ensure_credit_rows(cdp, kind="producer", need=len(producers))
        out.append({"ensure_producers": ens})
        for i, name in enumerate(producers, start=1):
            filled = _fill_one_credit(
                cdp,
                f"#track-1-producer-{i}-role",
                f"#track-1-producer-{i}-name",
                producer_role,
                name,
            )
            out.append({"producer": i, "result": filled})
            time.sleep(0.2)
        _force_close_swal(cdp)
        time.sleep(0.25)
        out.extend(_copy_credit_section(cdp, kind="producer"))

    return out
