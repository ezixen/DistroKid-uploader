"""
DistroKid store destinations, eligibility popups, and release-date helpers.
"""
from __future__ import annotations

import json
import time
from datetime import date


def dismiss_simple_alerts(cdp) -> dict:
    """Dismiss one-button SweetAlert / OK dialogs (e.g. Dolby file-size warning)."""
    return (
        cdp.evaluate(
            r"""
(() => {
  const popup = document.querySelector('.swal2-popup.swal2-show, .swal2-container .swal2-popup');
  if (!popup) return {ok:false, reason:'none'};
  const text = (popup.innerText || '').slice(0, 240);
  // Leave multi-step store eligibility / publishing-rights dialogs alone.
  if (/eligibility|roblox|publishing rights|snapchat|to distribute/i.test(text)) {
    return {ok:false, reason:'store-dialog', text};
  }
  const checks = [...popup.querySelectorAll('input[type=checkbox]')].filter(c => c.offsetParent !== null || c.getClientRects().length);
  if (checks.length >= 2) return {ok:false, reason:'eligibility', text};
  const btn = [...popup.querySelectorAll('button')].find(b => {
    const t = (b.innerText || b.value || '').trim().toLowerCase();
    return /^(ok|got it|okay|close)$/.test(t) || /ok,? got it/i.test(t);
  }) || popup.querySelector('.swal2-confirm');
  if (!btn) return {ok:false, reason:'no-button', text};
  // Never click Cancel / No from this helper
  if (/cancel|don.?t|no\b/i.test(btn.innerText || '')) return {ok:false, reason:'cancel-btn', text};
  btn.click();
  return {ok:true, text};
})()
"""
        )
        or {"ok": False}
    )


def accept_store_eligibility_popups(cdp) -> dict:
    """
    Accept store-terms popups:
    - Roblox: check every confirm box, then CONTINUE
    - Snapchat / similar: YES I OWN publishing rights
    Does not click CANCEL / NO / close.
    """
    return (
        cdp.evaluate(
            r"""
(() => {
  const popup = document.querySelector('.swal2-popup.swal2-show, .swal2-container .swal2-popup');
  if (!popup) return {ok:false, reason:'none'};
  const text = (popup.innerText || '').slice(0, 280);
  const looksStore = /eligibility|roblox|publishing rights|snapchat|to distribute|terms of service/i.test(text);
  const checks = [...popup.querySelectorAll('input[type=checkbox]')];
  const realChecks = checks.filter(c => {
    // ignore decorative/hidden empty boxes when possible
    return true;
  });
  if (!looksStore && realChecks.filter(c => (c.id||c.name||'').length).length < 2) {
    return {ok:false, reason:'not-store-dialog', text};
  }

  let checked = 0;
  for (const c of realChecks) {
    if (!c.checked) { c.click(); checked++; }
    else checked++;
  }

  const buttons = [...popup.querySelectorAll('button, a.btn, input[type=button]')];
  const prefer = buttons.find(b => {
    const t = (b.innerText || b.value || '').trim().toLowerCase();
    return /yes.*own|own 100%|continue|i agree|confirm/.test(t) && !/cancel|don.?t|no i/.test(t);
  });
  const cont = prefer
    || popup.querySelector('.snapSAConfirmButton, .roblox-sa-continue-button, .swal2-confirm');
  if (!cont) return {ok:false, reason:'no-continue', checked, text};
  const label = (cont.innerText || cont.value || '').trim().toLowerCase();
  if (/cancel|don.?t|no i\b|^no$/.test(label)) {
    return {ok:false, reason:'only-cancel', text};
  }
  cont.click();
  return {ok:true, checked, via:(cont.innerText||'').trim().slice(0,60), text};
})()
"""
        )
        or {"ok": False}
    )


def handle_visible_popups(cdp, *, rounds: int = 4) -> list[dict]:
    """Poll briefly for store eligibility / publishing-rights popups and simple OK alerts."""
    out: list[dict] = []
    for _ in range(max(1, rounds)):
        elig = accept_store_eligibility_popups(cdp)
        if elig.get("ok"):
            out.append({"eligibility": elig})
            time.sleep(0.45)
            # stop if popup cleared
            still = cdp.evaluate(
                "!!document.querySelector('.swal2-popup.swal2-show')"
            )
            if not still:
                break
            continue
        simple = dismiss_simple_alerts(cdp)
        if simple.get("ok"):
            out.append({"alert": simple})
            time.sleep(0.25)
            continue
        break
    return out


def set_release_date_today(cdp, iso_date: str | None = None) -> dict:
    """Set DistroKid release date (and original release date if empty) to today / given ISO date."""
    day = iso_date or date.today().isoformat()
    js = f"""
(() => {{
  const day = {json.dumps(day)};
  const setDate = (sel) => {{
    const el = document.querySelector(sel);
    if (!el) return {{ok:false, selector: sel}};
    el.focus();
    el.value = day;
    el.dispatchEvent(new Event('input', {{bubbles:true}}));
    el.dispatchEvent(new Event('change', {{bubbles:true}}));
    if (typeof el.onchange === 'function') try {{ el.onchange(); }} catch (e) {{}}
    el.blur();
    return {{ok:true, selector: sel, value: el.value}};
  }};
  const release = setDate('#release-date-dp, input[name=releaseDate]');
  const originalEl = document.querySelector('#original-release-date-dp, input[name=originalReleaseDate]');
  let original = {{ok:false, skipped:true}};
  if (originalEl && !String(originalEl.value || '').trim()) {{
    original = setDate('#original-release-date-dp, input[name=originalReleaseDate]');
  }} else if (originalEl) {{
    original = {{ok:true, kept: originalEl.value}};
  }}
  return {{ok: !!(release && release.ok), day, release, original}};
}})()
"""
    return cdp.evaluate(js) or {"ok": False, "day": day}


def configure_free_stores_only(cdp, *, include_social: bool = True) -> dict:
    """
    Check all free DistroKid store destinations (including social destinations by default).
    Never check paid extras (Social Media Pack, Leave a Legacy, Discovery Pack, etc.).
    After enabling stores that show eligibility popups (e.g. Roblox), accept those popups.
    """
    social_values = {"facebook", "tiktok", "snap"}
    social_ids = {"chkfacebook", "chktiktok", "chksnap"}
    stores = (
        cdp.evaluate(
            r"""
(() => [...document.querySelectorAll('input.distroStore[type=checkbox][name=store]')].map(el => ({
  id: el.id || '', value: (el.value || '').toLowerCase(), checked: !!el.checked
})))()
"""
        )
        or []
    )
    enabled: list[str] = []
    disabled: list[str] = []
    popups: list[dict] = []
    for st in stores:
        if not isinstance(st, dict):
            continue
        v = (st.get("value") or "").lower()
        sid = (st.get("id") or "").lower()
        is_social = v in social_values or sid in social_ids
        want = True if include_social else not is_social
        key = v or sid or "store"
        toggled = cdp.evaluate(
            f"""
(() => {{
  const want = {json.dumps(want)};
  const value = {json.dumps(v)};
  const id = {json.dumps(sid)};
  const el = [...document.querySelectorAll('input.distroStore[type=checkbox][name=store]')]
    .find(x => (x.value||'').toLowerCase() === value || (x.id||'').toLowerCase() === id);
  if (!el) return {{ok:false}};
  if (el.checked !== want) el.click();
  return {{ok:true, checked: el.checked, value: el.value || el.id}};
}})()
"""
        ) or {"ok": False}
        (enabled if want else disabled).append(key)
        if want and toggled.get("ok"):
            time.sleep(0.25)
            handled = handle_visible_popups(cdp, rounds=3)
            if handled:
                popups.extend(handled)

    # Paid extras — always off (but never disable free Audiomack)
    paid = (
        cdp.evaluate(
            r"""
(() => {
  const disabled = [];
  const isAudiomack = (el) => {
    const t = ((el.closest('label')?.innerText || el.parentElement?.innerText || '') + ' ' + (el.value||'') + ' ' + (el.id||'')).toLowerCase();
    return /\baudiomack\b/.test(t);
  };
  for (const el of document.querySelectorAll('input[type=checkbox][name=extras], input.extras[type=checkbox], #socialmediapack, #socialmediapack_alternate')) {
    if (isAudiomack(el)) continue;
    if (el.checked) el.click();
    disabled.push(el.id || el.value || 'extra');
  }
  for (const el of document.querySelectorAll('input[type=checkbox]')) {
    if (isAudiomack(el)) continue;
    const label = (el.closest('label')?.innerText || el.parentElement?.innerText || '').toLowerCase();
    if (/\$\s*\d|one-time fee|\/yr|\/mo|social media pack|leave a legacy|discovery pack|store maximizer|distrovid|loudness|dolby|cover song licensing/.test(label)) {
      if (el.checked) el.click();
      disabled.push(el.id || el.value || 'paid');
    }
  }
  return {disabled: [...new Set(disabled)].slice(0, 40)};
})()
"""
        )
        or {}
    )
    disabled.extend(paid.get("disabled") or [])
    # Final popup sweep (Roblox / Snapchat may appear late)
    time.sleep(0.4)
    late = handle_visible_popups(cdp, rounds=3)
    if late:
        popups.extend(late)
    return {
        "ok": True,
        "enabledCount": len(enabled),
        "disabledCount": len(disabled),
        "enabled": enabled,
        "disabled": list(dict.fromkeys(disabled))[:40],
        "popups": popups[:12],
    }
