# Build DistroKid-Uploader.exe (onedir) into app\DistroKid-Uploader\
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File app\build_exe.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root "distrokid_upload_album.py"))) {
  throw "Run from DistroKid-uploader folder (distrokid_upload_album.py missing)."
}

$py = "C:\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $py = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "Build Python: $py"
& $py -c "import sys; print(sys.version)"
& $py -m pip install -q "pyinstaller>=6.0" "websocket-client>=1.6.0"

$env:PYTHONPATH = $root
$env:PYTHONDONTWRITEBYTECODE = "1"
& $py -c "import chrome_debug, album_media, distrokid_upload_album; print('imports OK')"

$appPy = Join-Path $PSScriptRoot "distrokid_app.py"
$settings = Join-Path $root "upload-settings.txt"
$prices = Join-Path $root "prices.txt"
if (-not (Test-Path $settings)) { throw "Missing upload-settings.txt" }
if (-not (Test-Path $prices)) { throw "Missing prices.txt" }
$outRoot = Join-Path $PSScriptRoot "_build_out"
$distName = "DistroKid-Uploader"
$final = Join-Path $PSScriptRoot $distName
$work = Join-Path $PSScriptRoot "_pyi_work"
$spec = Join-Path $PSScriptRoot "_pyi_spec"

foreach ($p in @($outRoot, $work, $spec)) {
  if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}

# PyInstaller --add-data can be passed multiple times
$addSettings = "$settings;."
$addPrices = "$prices;."
$versionFile = Join-Path $PSScriptRoot "version_info.txt"
if (-not (Test-Path $versionFile)) { throw "Missing version_info.txt" }
$iconFile = Join-Path $PSScriptRoot "uploader.ico"
if (-not (Test-Path $iconFile)) { $iconFile = Join-Path $root "images\uploader-logo.ico" }
if (-not (Test-Path $iconFile)) { throw "Missing uploader.ico / images\uploader-logo.ico" }
& $py -m PyInstaller `
  --noconfirm `
  --clean `
  --console `
  --name $distName `
  --paths $root `
  --distpath $outRoot `
  --workpath $work `
  --specpath $spec `
  --version-file $versionFile `
  --icon $iconFile `
  --add-data $addSettings `
  --add-data $addPrices `
  --hidden-import websocket `
  --hidden-import chrome_debug `
  --hidden-import album_media `
  --hidden-import distrokid_upload_album `
  --hidden-import distrokid_form `
  --hidden-import distrokid_stores `
  --hidden-import distrokid_tracks `
  --hidden-import distrokid_dialogs `
  --hidden-import distrokid_finish `
  --hidden-import upload_settings `
  --hidden-import cdp_owned_tab `
  $appPy

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }

$built = Join-Path $outRoot $distName
$outExe = Join-Path $built "DistroKid-Uploader.exe"
if (-not (Test-Path $outExe)) { throw "Missing $outExe" }

Copy-Item $settings (Join-Path $built "upload-settings.txt") -Force
Copy-Item $prices (Join-Path $built "prices.txt") -Force
@"
DistroKid Uploader (EXE)
=======================

Latest always (GitHub):
  https://github.com/ezixen/DistroKid-uploader
  https://github.com/ezixen/DistroKid-uploader/releases/latest
  EXE pack: https://github.com/ezixen/DistroKid-uploader/releases/latest/download/DistroKid-Uploader-exe.zip

1. Edit upload-settings.txt in this folder (once)
2. Double-click DistroKid-Uploader.exe
3. Log into DistroKid in the Chrome window that opens (once; 2FA if asked)
4. Paste an album folder path, Enter — repeat for more albums
5. If album title already exists → WARNING, no overwrite
6. Review the form in Chrome; you push/upload (never auto-publishes)

Needs: Google Chrome installed.
Edits: upload-settings.txt + prices.txt in this folder
Chrome login: %LOCALAPPDATA%\DistroKid-Uploader\ (kept between runs; never beside this EXE)
On quit: debug Chrome stops; caches/temp cleared; this folder stays deletable
"@ | Set-Content (Join-Path $built "HOW_TO_RUN.txt") -Encoding UTF8

New-Item -ItemType Directory -Force -Path $final | Out-Null
& robocopy $built $final /E /XD local-secrets /NFL /NDL /NJH /NJS /nc /ns /np /R:2 /W:1 | Out-Null
Copy-Item (Join-Path $built "DistroKid-Uploader.exe") (Join-Path $final "DistroKid-Uploader.exe") -Force
Copy-Item (Join-Path $built "upload-settings.txt") (Join-Path $final "upload-settings.txt") -Force
Copy-Item (Join-Path $built "prices.txt") (Join-Path $final "prices.txt") -Force
Copy-Item (Join-Path $built "HOW_TO_RUN.txt") (Join-Path $final "HOW_TO_RUN.txt") -Force

# Authenticode sign as CN=ezixen (FileDescription already embeds GitHub URL via version_info.txt)
. (Join-Path $PSScriptRoot "sign_exe.ps1")
Invoke-EzixenSign -ExePath (Join-Path $final "DistroKid-Uploader.exe")

& $py -c @"
import sys
from pathlib import Path
sys.path.insert(0, r'$root')
from chrome_debug import scrub_app_folder_side_effects, stop_chrome_using_profile
stop_chrome_using_profile()
scrub_app_folder_side_effects(Path(r'$final'))
print('scrubbed', r'$final')
"@

Write-Host "OK built: $(Join-Path $final 'DistroKid-Uploader.exe')"
Get-ChildItem $final | Select-Object Name, Length | Format-Table -AutoSize
