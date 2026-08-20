# DistroKid Uploader

**GitHub (latest always):** https://github.com/ezixen/DistroKid-uploader  
**[Latest release](https://github.com/ezixen/DistroKid-uploader/releases/latest)** · **[ZIP (scripts + EXE)](https://github.com/ezixen/DistroKid-uploader/releases/latest/download/DistroKid-uploader.zip)** · **[EXE only](https://github.com/ezixen/DistroKid-uploader/releases/latest/download/DistroKid-Uploader-exe.zip)**  

Unpack either ZIP → you get a **`DistroKid-uploader/`** folder (no need to create one).

---

Fill DistroKid **new release** forms from local album folders. You review in Chrome and push/upload yourself — this tool **never final-publishes**.

**Safeguard:** if the album title already appears in DistroKid My Music → **warn, do not overwrite** (unless `--force`).

Same folder / filename rules as [BandCamp-uploader](https://github.com/ezixen/BandCamp-uploader).

## Option A — EXE (easiest, no install)

1. Unpack and open **`DistroKid-uploader/app/DistroKid-Uploader/`** (ZIP already contains the `DistroKid-uploader` folder)
2. Edit **`upload-settings.txt`** beside the exe once (or use defaults)
3. Double-click **`DistroKid-Uploader.exe`**
4. Log into DistroKid in the Chrome window that opens (once per PC; complete 2FA if asked)
5. Paste one album folder path at a time; press Enter after each
6. Review the filled form in Chrome — you push/upload

Requires **Google Chrome**.  

Chrome login profile is stored under **`%LOCALAPPDATA%\DistroKid-Uploader\`** (not inside the app folder), so you can delete the unpacked folder anytime — including when the EXE lives on `D:\` or another drive.  
After each quit the app stops debug Chrome, clears caches/locks/temp beside the app if any, and **keeps DistroKid login** in LocalAppData.

Rebuild from source: `app/build_exe.ps1` (uses `C:/.venv` Python + PyInstaller).

## Option B — PowerShell scripts

| Step | File | Purpose |
|---|---|---|
| 0 | `0_associate_ps1.bat` | **Do this first** — bind `.ps1` to built-in Windows PowerShell and clear other handlers |
| 1 | `1_install.bat` / `.ps1` | Elevated install: **newest** winget Python 3.x + pip deps; skips if 3.10+ already present |
| 2 | `2_start_chrome.bat` / `.ps1` | Debug Chrome; log in once (`%LOCALAPPDATA%\DistroKid-Uploader`) |
| 3 | `3_check_titles.bat` / `.ps1` | Optional title / cover / price preview |
| 4 | `4_distrokid_uploader.bat` / `.ps1` | Fill DistroKid form for album folder(s) |

Prefer the **`.bat`** step files for double-click. They always call:

`%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`

Helpers: `_run_ps1.bat`, `_common.ps1`, `distrokid_upload_album.py`, `upload-settings.txt`, `prices.txt`, `requirements.txt`  
Short guide: [`how2use.txt`](how2use.txt)  
Detailed playbook: [`docs/DISTROKID_UPLOAD.md`](docs/DISTROKID_UPLOAD.md)

### Step 0 — Windows PowerShell for `.ps1`

1. Double-click **`0_associate_ps1.bat`**
2. It **only** uses the default Windows PowerShell path (no pwsh hunt, no questions)
3. Then use **`1_install.bat`** … or the raw `.ps1` files

On some Windows 11 PCs Explorer may still show a picker once; the `.bat` twins and the EXE avoid that entirely.

---

## Settings (`upload-settings.txt`)

Edit once (read every run):

- Prices, releaser, real name, artist  
- Instrumental / explicit  
- AI disclosure (`off` / `on` / `both` + DistroKid checkboxes)  
- Apple Music credits (performer / producer)  
- Audiomack (free) on/off  
- Mandatory bottom checkboxes on/off  

**Code defaults for new users:** AI off, explicit off, mandatory checkboxes off, Audiomack on.  
Your personal file can override (e.g. AI part-of-audio + instruments).

---

## Multiple albums (script path)

Separate full folder paths with **`;`**:

```powershell
.\4_distrokid_uploader.ps1 "d:\music\album1; d:\music\album2"
```

The EXE asks for one path per line instead.

---

## What it fills (per album)

- Album title, prices, largest jpg/jpeg cover  
- Numbered `.wav` files in order, title-only (`01. Artist - title.wav`) — trailing `...` kept  
- Free stores + socials; release date = today  
- Songwriters (first/middle/last) + copy to all tracks (confirms DistroKid popups)  
- Instrumental / explicit / AI disclosure (with modal Save)  
- Apple Music performer + producer credits + copy to all  
- Audiomack free extra (default on)  
- **Does not** tick paid extras · **does not** final-publish  

---

## File naming

```text
01. ezixen - intro.wav
07. ezixen - yes, and....wav   → title: yes, and...
```

Number → order · Artist stripped · Title kept (including `...`) · `_` → `?`

---

## Safety

No final publish · no passwords in repo · album-exists warning · respect DistroKid terms  

Latest: https://github.com/ezixen/DistroKid-uploader

---

## If stuck Chrome / Temp folders ever happen

If you cannot delete automation leftovers (e.g. `C:\Temp\playwright_chromiumdev_profile-*`, `chrome-canary*`, old `local-secrets`), **this is the solution:**

1. Read [`docs/DEV_REMOVE_STUCK_BROWSER_PROFILES.md`](docs/DEV_REMOVE_STUCK_BROWSER_PROFILES.md)
2. Boot into **Safe Mode (Minimal)** via `msconfig`
3. Run [`docs/SAFE_MODE_DELETE_STUCK_CHROME.bat`](docs/SAFE_MODE_DELETE_STUCK_CHROME.bat) as **Administrator**
4. Turn Safe boot **off**, reboot normally

That bat clears matching stuck **subfolders** under `C:\Temp` / `D:\Temp` (it does not wipe all of Temp).
