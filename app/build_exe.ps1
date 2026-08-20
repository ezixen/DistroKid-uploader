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
$prices = Join-Path $root "upload-settings.txt"
if (-not (Test-Path $prices)) { $prices = Join-Path $root "prices.txt" }
$outRoot = Join-Path $PSScriptRoot "_build_out"
$distName = "DistroKid-Uploader"
$final = Join-Path $PSScriptRoot $distName
$work = Join-Path $PSScriptRoot "_pyi_work"
$spec = Join-Path $PSScriptRoot "_pyi_spec"

foreach ($p in @($outRoot, $work, $spec)) {
  if (Test-Path $p) { Remove-Item $p -Recurse -Force }
}

$addData = "$prices;."
& $py -m PyInstaller `
  --noconfirm `
  --clean `
  --console `
  --name $distName `
  --paths $root `
  --distpath $outRoot `
  --workpath $work `
  --specpath $spec `
  --add-data $addData `
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
  $appPy

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }

$built = Join-Path $outRoot $distName
$outExe = Join-Path $built "DistroKid-Uploader.exe"
if (-not (Test-Path $outExe)) { throw "Missing $outExe" }

Copy-Item $prices (Join-Path $built "prices.txt") -Force
@"
DistroKid Uploader (EXE)
=======================

1. Double-click DistroKid-Uploader.exe
2. Log into DistroKid in the Chrome window (once)
3. Paste an album folder path, Enter
4. If album title already exists → WARNING, no overwrite
5. Review in Chrome; publish yourself

Needs: Google Chrome.
Chrome login: %LOCALAPPDATA%\DistroKid-Uploader\
"@ | Set-Content (Join-Path $built "HOW_TO_RUN.txt") -Encoding UTF8

New-Item -ItemType Directory -Force -Path $final | Out-Null
& robocopy $built $final /E /XD local-secrets /NFL /NDL /NJH /NJS /nc /ns /np /R:2 /W:1 | Out-Null
Copy-Item (Join-Path $built "DistroKid-Uploader.exe") (Join-Path $final "DistroKid-Uploader.exe") -Force
Copy-Item (Join-Path $built "prices.txt") (Join-Path $final "prices.txt") -Force
Copy-Item (Join-Path $built "HOW_TO_RUN.txt") (Join-Path $final "HOW_TO_RUN.txt") -Force

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
