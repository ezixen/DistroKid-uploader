# DistroKid upload playbook

**Local app folder:** `DistroKid-uploader/`

## Rules (aligned with Bandcamp)

- Numbered `.wav` only, numeric order  
- Title-only track names (`01. ezixen - Song.wav` → `Song`)  
- Largest `.jpg` cover  
- **Never final-publish / push upload** without your review in Chrome  
- Chrome profile: `%LOCALAPPDATA%\DistroKid-Uploader`

## upload-settings.txt (one-time)

Edit `upload-settings.txt` in the DistroKid-uploader folder (replaces `prices.txt` for this app).

| Key | Meaning | Example (ezixen) |
|---|---|---|
| `album` / `track` | Prices | `9.99` / `0.99` |
| `releaser` | Record label / released-by | `(ezixen) records` |
| `real_name` | Legal / real name | `George 'ezixen' Lawrence` |
| `artist` | Primary artist | `ezixen` |
| `instrumental` | `on` \| `off` | `on` |
| `ai` | `off` \| `on` \| `both` | `both` (AI + you) |
| `ai_lyrics` | DistroKid “The lyrics” | `off` |
| `ai_music` | DistroKid “The music” | `on` |
| `ai_all_audio` | DistroKid “All of the audio” | `off` |
| `ai_part_audio` | DistroKid “Part of the audio” | `on` |
| `ai_artist_persona` | `human` \| `ai` (if all audio) | `human` |
| `credit_artist` | Contributor name on every track | `ezixen` |
| `credit_roles` | Comma-separated DistroKid roles | `unknown instrument, executive producer` |
| `real_name` | Songwriter legal name (split to first/middle/last) | `George 'ezixen' Lawrence` |
| `ai_part_instruments` | DistroKid “Instruments” under Part of the audio | `on` (default with ai_music) |

**Always auto:** album title from folder name; songwriter first/middle/last + **Copy to all tracks**; all free stores ON (including social + Roblox/Snapchat); store eligibility popups; DistroKid distribution terms; **release date = today**; audio files into `#js-track-upload-N` (never Dolby Atmos slots).  
**Never auto:** paid extras (Social Media Pack $$, Leave a Legacy, Discovery Pack, Store Maximizer, etc.), genre — set those yourself per album if needed.

### Track count (critical)

The uploader counts numbered `.wav` files and sets DistroKid **Number of songs** (`#howManySongsOnThisAlbum`) **first**, then fills the rest. Changing track count later forces a DistroKid restart — do not change it by hand after the script starts.

### AI options (DistroKid wording)

When DistroKid asks if AI generated any of the track:

- **The lyrics** — AI wrote the words (`ai_lyrics`)  
- **The music** — AI composed melody/arrangement (`ai_music`)  
- **All of the audio** — everything heard is AI (`ai_all_audio`)  
- **Part of the audio** — some AI, some human (`ai_part_audio`)  

`ai=both` with `ai_music=on` + `ai_part_audio=on` is the “AI and me on instruments” setup.

## Album-exists safeguard

Before filling a new release, My Music is scanned for an exact album title.

- Match found → **WARNING**, exit `3`, no overwrite  
- Override: `--force` (still never auto-publishes)

## Steps

1. `.\1_install.bat` (once)  
2. `.\2_start_chrome.bat` → log into DistroKid (complete 2FA if prompted)  
3. Optional: `.\3_check_titles.bat`  
4. `.\4_distrokid_uploader.bat` with album folder path  
5. **You** verify the filled form in Chrome and push/upload if OK  

## Status

Fills identity, instrumental, AI disclosure, cover/tracks, and credits as far as the live DistroKid UI allows. DistroKid changes markup often — if a field is missed, the console prints `ok:false` for that step; adjust selectors or finish that field manually before you submit.
