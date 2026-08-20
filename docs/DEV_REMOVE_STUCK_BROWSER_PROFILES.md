# Remove stuck automated-browser profile folders

**When:** Undeletable leftovers under `C:\Temp` / `D:\Temp` (or old `local-secrets` beside an unpack) from older BandCamp Uploader builds or Playwright/Chrome automation.

**Product note (v1.5.1+):** Normal use puts the Chrome login profile only under `%LOCALAPPDATA%\BandCamp-Uploader` and cleans beside-EXE junk on quit. This page is the fallback **if folders are still stuck**.

**Tool:** [`SAFE_MODE_DELETE_STUCK_CHROME.bat`](SAFE_MODE_DELETE_STUCK_CHROME.bat) (same folder as this MD).

---

## What went wrong (old builds)

Older builds used:

```text
--user-data-dir=...\BandCamp-Uploader\local-secrets\chrome-debug-profile
```

(next to the EXE). Chrome left profile DBs / `LOCK` files. Windows then returns **Access is denied** on delete even when Chrome is closed and elevated `takeown` + `rd` fail in normal mode.

Same junk class (often dozens of **subfolders** under Temp):

- `C:\Temp\playwright_chromiumdev_profile-*` (and similar `playwright_chromium*`)
- `C:\Temp\chrome-canary*`
- `C:\Temp\chrome-debug-profile*`
- `C:\Temp\local-secrets*` / `BandCamp-Uploader*`
- `D:\Temp\…` (same patterns)
- Unpacked trees like `C:\downloads\BandCamp-Uploader`

**Proven fix when normal delete fails:** Safe Mode + the batch below.

---

## Method A — Safe Mode + `.bat` (preferred)

### What the bat does

It does **not** wipe all of `C:\Temp`. It walks Temp roots and force-removes **matching stuck subfolders**:

| Root scanned | Subfolder name patterns removed |
|---|---|
| `C:\Temp`, `C:\temp`, `D:\Temp`, `D:\temp`, and `%TEMP%` if different | `playwright_chromium*`, `puppeteer_*`, `selenium-*`, `chrome-canary*`, `chrome-debug-profile*`, `chrome-wiwm*`, `ela-chrome*`, `local-secrets*`, `BandCamp-Uploader*`, `*.to_delete`, `*.__delete_me__` |
| Optional hard paths | `C:\downloads\BandCamp-Uploader` (edit the bat to add more unpack paths) |

For each hit: `takeown` → `icacls` → `rd \\?\…` → robocopy empty-mirror fallback → print `GONE` / `STILL`.

### Before Safe Mode (normal Windows)

1. Optional: copy the `.bat` to `C:\Temp\` so it is easy to find if Drive/GitHub is offline in Safe Mode.
2. Edit only if you have stuck folders **outside** those Temp patterns (add another `call :ForceRemoveDir "X:\path"` near the optional BandCamp section).
3. You do not need to list every `playwright_chromiumdev_profile-XXXX` by hand — wildcards cover them.

### Enter Safe Mode

1. `Win+R` → `msconfig` → **Boot** tab  
2. Check **Safe boot** → **Minimal** → OK → reboot  
3. Sign in (plain desktop / “Safe Mode” in corners)

### Run the bat (Administrator, still in Safe Mode)

- Right‑click `SAFE_MODE_DELETE_STUCK_CHROME.bat` → **Run as administrator** → Yes on UAC  
- Or Admin CMD: `cd` to the folder, then run the `.bat`

Want lines like `GONE:` / `OK: no matching stuck folders left under C:\Temp`. Press a key on `pause`.

### Leave Safe Mode

1. `Win+R` → `msconfig` → **Boot** → **uncheck** Safe boot → OK → reboot normally  

### Optional — Bandcamp login wipe

Only if you also want to clear the *new* profile (login cookies), after normal Windows:

```bat
rd /s /q "%LOCALAPPDATA%\BandCamp-Uploader"
```

Do **not** delete that unless you intend to log into Bandcamp again.

---

## Method B — Normal mode first try (often fails on these leftovers)

Close BandCamp EXE / debug Chrome / Cursor browser tools, then try elevated delete / takeown. If anything under Temp remains → **Method A (Safe Mode)**.

---

## Checklist (other PC)

- [ ] Get `docs/SAFE_MODE_DELETE_STUCK_CHROME.bat` from this repo (or release / Drive copy)
- [ ] Safe Mode → Run as administrator → confirm Temp matching folders `GONE`
- [ ] Disable Safe boot → normal reboot
- [ ] Use BandCamp Uploader **v1.5.1+** only (profile under `%LOCALAPPDATA%\BandCamp-Uploader`)

---

## Product regression check

New EXE must print profile under `AppData\Local\BandCamp-Uploader` and leave **no** `local-secrets` beside the EXE.

---

## If it ever happens again

**This is the solution:** boot Windows into Safe Mode (Minimal), run [`SAFE_MODE_DELETE_STUCK_CHROME.bat`](SAFE_MODE_DELETE_STUCK_CHROME.bat) as Administrator, confirm matching Temp subfolders are `GONE`, then turn Safe boot off and reboot normally. Do not spend hours on Handle / reboot-delete in normal mode for this class of leftover — Safe Mode + that bat is what works.
