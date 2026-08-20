# DistroKid-uploader

**GitHub:** https://github.com/ezixen/DistroKid-uploader

Automates DistroKid album **form fill** for artist **ezixen** (same folder/title rules as BandCamp-uploader).

**Safeguard:** if the album title already appears in DistroKid My Music â†’ **warn, do not overwrite**.  
**You** verify in Chrome and push/upload if OK â€” this tool never final-submits.

## Settings (one-time)

Edit [`upload-settings.txt`](upload-settings.txt):

- Releaser, real name, artist  
- Instrumental on/off  
- AI disclosure (`off` / `on` / `both` + DistroKid checkboxes)  
- Per-track credits (artist + roles from DistroKid dropdowns)  
- Prices  

Details: [`docs/DISTROKID_UPLOAD.md`](docs/DISTROKID_UPLOAD.md)

## Quick start

1. `.\1_install.bat`  
2. `.\2_start_chrome.bat` â€” log into DistroKid (and 2FA if asked)  
3. `.\4_distrokid_uploader.bat` â€” paste album folder path  

## If stuck Chrome / Temp folders

See `docs/DEV_REMOVE_STUCK_BROWSER_PROFILES.md` (Safe Mode bat).
