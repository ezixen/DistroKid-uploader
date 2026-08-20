# DistroKid upload playbook (detailed)

**Local app folder:** `DistroKid-uploader/`  
**GitHub:** https://github.com/ezixen/DistroKid-uploader  
**Short human guide:** [`how2use.txt`](../how2use.txt) · **README:** [`README.md`](../README.md)

## Rules (aligned with Bandcamp)

- Numbered `.wav` only, numeric order  
- Title-only track names (`01. ezixen - Song.wav` → `Song`)  
- Trailing `...` in titles is **kept** (`yes, and....wav` → `yes, and...`)  
- `_` in titles → `?`  
- Largest `.jpg` / `.jpeg` cover  
- Audio files are **queued quickly** into all track slots (DistroKid uploads in parallel — no per-track wait)  
- **Never final-publish / push upload** without your review in Chrome  
- Chrome profile: `%LOCALAPPDATA%\DistroKid-Uploader`

## upload-settings.txt (one-time)

Edit `upload-settings.txt` in the DistroKid-uploader folder (also copied beside the EXE). Read on every run.

| Key | Meaning | New-user default | Notes |
|---|---|---|---|
| `album` / `track` | Prices | `9.99` / `0.99` | |
| `releaser` | Record label / released-by | `(ezixen) records` | Edit for your label |
| `real_name` | Legal name → First / Middle / Last | — | Or set `real_name_first` / `_middle` / `_last` |
| `artist` | Primary artist (+ Apple credits name) | `ezixen` | |
| `instrumental` | `on` \| `off` | `on` | |
| `explicit` | `on` \| `off` | **`off`** | Instrumentals → keep off |
| `ai` | `off` \| `on` \| `both` | **`off`** | See AI section below |
| `ai_lyrics` | Lyrics written by AI | `off` | DistroKid modal checkbox |
| `ai_music` | Music composed by AI | `off` | |
| `ai_all_audio` | All of the audio performed by AI | `off` | |
| `ai_part_audio` | Part of the audio (AI + humans) | `off` | |
| `ai_part_instruments` | Under part-of-audio: Instruments | `off` | Radios — one of instruments/vocals |
| `ai_part_vocals` | Under part-of-audio: Vocals | `off` | If both on, Instruments preferred |
| `ai_artist_persona` | `human` \| `ai` | `human` | If all audio |
| `audiomack` | Free Audiomack extra | **`on`** | Paid extras stay off |
| `mandatory_checkboxes` | Bottom “Important” boxes | **`off`** | Set `on` only if you want them ticked |
| `credit_artist` | Apple Music credit name | = `artist` | |
| `credit_performer_role` | Performer role dropdown | `Unknown` | |
| `credit_producer_role` | Producer role dropdown | `Executive producer` | |

**Always auto:** album title from folder; songwriter first/middle/last + **Copy to all tracks** (confirms “Do it” / OK popups); all free stores ON (including social + Roblox/Snapchat); store eligibility popups; DistroKid distribution terms; **release date = today**; audio into `#js-track-upload-N` (never Dolby Atmos slots); Apple Music performer + producer + copy to all.

**Never auto:** paid extras (Leave a Legacy, Discovery Pack, Store Maximizer, DistroVid, Loudness Normalization, Social Media Pack, etc.), genre — set those yourself if needed. **Never final-publish.**

### Track count (critical)

The uploader counts numbered `.wav` files and sets DistroKid **Number of songs** first, then fills the rest. Changing track count later forces a DistroKid restart — do not change it by hand after the script starts.

### AI options (DistroKid popup)

When DistroKid asks *Does this song include AI-generated…?* and you answer Yes, a modal appears: **Which parts of this song were AI-generated?**

| Setting | DistroKid wording |
|---|---|
| `ai=off` | Answer **No** (default for new users) |
| `ai_lyrics=on` | Lyrics (written by AI) |
| `ai_music=on` | Music (composed by AI) |
| `ai_all_audio=on` | All of the audio (performed by AI) |
| `ai_part_audio=on` | Part of the audio (performed by AI + humans) |
| `ai_part_instruments=on` | → Instruments radio |
| `ai_part_vocals=on` | → Vocals radio |

Typical “AI helped on instruments”: `ai=both` (or `on`), `ai_part_audio=on`, `ai_part_instruments=on`. The uploader also checks **Apply these selections to all songs**, then **Save**, and dismisses confirmation popups.

DistroKid uses **radios** for Vocals vs Instruments (one choice). If both settings are on, Instruments wins.

### Confirmation popups

The uploader confirms DistroKid SweetAlert / modal buttons for:

- Copy songwriters to all tracks → **Do it** → **OK**  
- AI disclosure → **Save**  
- Copy performer / producer credits to all tracks → **Do it** → **OK**  

It does **not** click unrelated Save buttons as a fallback.

## Album-exists safeguard

Before filling a new release, My Music is scanned for an exact album title.

- Match found → **WARNING**, exit `3`, no overwrite  
- Override: `--force` (still never auto-publishes)

## Steps

### EXE

1. Unpack release ZIP  
2. Edit `upload-settings.txt`  
3. Run `app\DistroKid-Uploader\DistroKid-Uploader.exe`  
4. Log in once → paste album paths → review in Chrome → you push  

### Scripts

1. `.\0_associate_ps1.bat` (first time)  
2. `.\1_install.bat` (once)  
3. `.\2_start_chrome.bat` → log into DistroKid (2FA if prompted)  
4. Optional: `.\3_check_titles.bat`  
5. `.\4_distrokid_uploader.bat` with album folder path  
6. **You** verify the filled form in Chrome and push/upload if OK  

## Status

Fills identity, stores, instrumental, explicit, AI disclosure, cover/tracks, songwriters, Apple credits, Audiomack, and optional mandatory checkboxes as far as the live DistroKid UI allows. DistroKid changes markup often — if a field is missed, the console prints `ok:false` for that step; finish that field manually before you submit.
