# 4) Upload album draft(s) to DistroKid (does not publish)
# Supports one path, or several separated by ; (or , between drive paths)
#
#   .\4_distrokid_uploader.ps1
#   .\4_distrokid_uploader.ps1 "d:\music\a; d:\music\b"

param(
  [Parameter(Mandatory = $false, Position = 0)]
  [string]$AlbumFolder
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_common.ps1")

$resolved = Resolve-AlbumFolders $AlbumFolder
$python = Resolve-PythonExe
$script = Get-UploaderPy

try {
  $null = Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 2
} catch {
  Write-Host "ERROR: Chrome CDP not on 9222. Run .\2_start_chrome.ps1 and log into DistroKid first." -ForegroundColor Red
  exit 1
}

if ($resolved.Folders.Count -eq 0) {
  Write-Host "ERROR: No valid album folders to upload." -ForegroundColor Red
  if ($resolved.Errors.Count -gt 0) {
    $resolved.Errors | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
  }
  exit 1
}

Write-Host "Python: $python"
Write-Host ("Albums to upload: {0}" -f $resolved.Folders.Count)
Write-Host "(cover = largest jpg/jpeg, prices from prices.txt, title-only, no publish)"
if ($resolved.Errors.Count -gt 0) {
  Write-Host "Some paths were invalid and will be skipped:" -ForegroundColor Yellow
  $resolved.Errors | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
}

$failed = New-Object System.Collections.Generic.List[string]
$succeeded = New-Object System.Collections.Generic.List[string]
$i = 0
foreach ($folder in $resolved.Folders) {
  $i++
  Write-Host ""
  Write-Host "======== UPLOAD $i / $($resolved.Folders.Count): $folder ========" -ForegroundColor Cyan
  try {
    & $python -u $script $folder
    if ($LASTEXITCODE -ne 0) {
      $msg = "UPLOAD FAILED (exit $LASTEXITCODE): $folder"
      $failed.Add($msg) | Out-Null
      Write-Host "ERROR: $msg" -ForegroundColor Red
    } else {
      $succeeded.Add($folder) | Out-Null
      Write-Host "OK: draft finished for $folder" -ForegroundColor Green
    }
  } catch {
    $msg = "UPLOAD FAILED: $folder â€” $($_.Exception.Message)"
    $failed.Add($msg) | Out-Null
    Write-Host "ERROR: $msg" -ForegroundColor Red
  }
}

Write-Host ""
Write-Host "======== UPLOAD SUMMARY ========"
Write-Host ("Succeeded: {0}" -f $succeeded.Count) -ForegroundColor Green
$succeeded | ForEach-Object { Write-Host "  + $_" -ForegroundColor Green }
if ($resolved.Errors.Count -gt 0) {
  Write-Host ("Bad paths skipped: {0}" -f $resolved.Errors.Count) -ForegroundColor Red
  $resolved.Errors | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}
if ($failed.Count -gt 0) {
  Write-Host ("Upload failures: {0}" -f $failed.Count) -ForegroundColor Red
  $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}

. (Join-Path $PSScriptRoot "_chrome_session.ps1")
Write-Host ""
Write-Host "Review drafts in Chrome, then press Enter here to stop debug Chrome and clean temp"
Write-Host "(DistroKid login is kept). Or close this window to leave Chrome open for review."
try { $null = Read-Host } catch {}
$n = Invoke-DistroKidSessionCleanup -AppRoots @($PSScriptRoot, (Join-Path $PSScriptRoot "app\DistroKid-Uploader"))
Write-Host "Cleanup done (stopped $n Chrome process(es); login kept)."

if ($succeeded.Count -eq 0 -or $failed.Count -gt 0 -or $resolved.Errors.Count -gt 0) {
  if ($succeeded.Count -eq 0) { exit 1 }
  exit 2
}
exit 0


