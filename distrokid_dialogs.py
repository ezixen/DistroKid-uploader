"""
DistroKid confirmation dialogs (Copy songwriters / credits / generic Do it / OK / Save).
"""
from __future__ import annotations

import time


def confirm_do_it_popup(cdp) -> dict:
    """
    Confirm DistroKid SweetAlert copy dialogs:
    - "Copy songwriters?" → Do it
    - Copy performer / producer → Do it / OK
    """
    return (
        cdp.evaluate(
            r"""
(() => {
  const popup = document.querySelector('.swal2-popup.swal2-show, .swal2-container .swal2-popup, .swal2-container');
  const box = document.querySelector('.swal2-popup.swal2-show, .swal2-popup');
  if (!box) return {ok:false, reason:'none'};
  const text = (box.innerText || '').replace(/\s+/g, ' ').trim();
  if (/which parts of this song were ai-generated/i.test(text)) {
    return {ok:false, reason:'ai-modal'};
  }
  if (/eligibility|roblox|publishing rights|snapchat can only/i.test(text) && /continue|yes,? i own/i.test(text)) {
    return {ok:false, reason:'store-eligibility'};
  }
  const buttons = [...box.querySelectorAll('button, a.btn, input[type=button], input[type=submit]')];
  const prefer = buttons.find(b => {
    const t = (b.innerText || b.value || '').replace(/\s+/g, ' ').trim().toLowerCase();
    return t === 'do it' || t === 'ok' || t === 'okay' || t === 'confirm' || t === 'yes';
  });
  // Never fall back to a generic .swal2-confirm if it says Save/Cancel (AI modal)
  const btn = prefer;
  if (!btn) return {ok:false, reason:'no-confirm-button', text: text.slice(0, 120)};
  const label = (btn.innerText || btn.value || '').trim();
  if (/cancel|don.?t|^no$|save/i.test(label)) return {ok:false, reason:'wrong-btn', text: text.slice(0, 120)};
  btn.click();
  return {ok:true, via: label.slice(0, 40), text: text.slice(0, 120)};
})()
"""
        )
        or {"ok": False}
    )


def click_and_confirm(cdp, click_fn, *, wait_s: float = 0.7, rounds: int = 3) -> list[dict]:
    """Run a click action, then accept any Do it / OK confirmation popups."""
    out: list[dict] = []
    clicked = click_fn()
    out.append({"click": clicked})
    time.sleep(wait_s)
    for _ in range(max(1, rounds)):
        conf = confirm_do_it_popup(cdp)
        if conf.get("ok"):
            out.append({"confirm": conf})
            time.sleep(0.45)
            continue
        break
    return out
