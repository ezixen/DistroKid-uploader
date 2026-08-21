# 2) Start debug Chrome — log into DistroKid once
# Profile: %LOCALAPPDATA%\DistroKid-Uploader\chrome-debug-profile
#
#   .\2_start_chrome.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_chrome_session.ps1")

$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) {
  $chrome = "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
}
if (-not (Test-Path $chrome)) {
  throw "Chrome not found. Install Google Chrome first."
}

Remove-DistroKidLegacyLocalSecrets -Roots @($PSScriptRoot, (Join-Path $PSScriptRoot "app\DistroKid-Uploader"))

$userData = Ensure-DistroKidChromeProfileWritable
Clear-DistroKidChromeLocks

try {
  $null = Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 2
  Write-Host "CDP already up on 9222 - using existing debug Chrome."
  Write-Host "Each uploader instance opens its own new tab(s) when it starts."
} catch {
  Write-Host "Starting debug Chrome..."
  Write-Host "  --remote-debugging-port=9222"
  Write-Host "  --user-data-dir=$userData"

  Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=9222",
    "--remote-allow-origins=*",
    "--user-data-dir=$userData",
    "https://distrokid.com/"
  )

  Start-Sleep -Seconds 2
  $ver = (Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 5).Content
  Write-Host "OK CDP:" $ver
}

Write-Host ""
Write-Host "Log into DistroKid if needed (login kept under %LOCALAPPDATA%\DistroKid-Uploader)."
Write-Host "Optional title check:  .\3_check_titles.bat"
Write-Host "Upload:               .\4_distrokid_uploader.bat"
