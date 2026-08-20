# Shared Chrome profile path + session cleanup for PowerShell steps.
# Dot-source from 2 / 4 / 5. Keeps DistroKid login; clears locks/caches/legacy folders.

function Get-DistroKidChromeProfileDir {
  Join-Path $env:LOCALAPPDATA "DistroKid-Uploader\chrome-debug-profile"
}

function Ensure-DistroKidChromeProfileWritable {
  $dir = Get-DistroKidChromeProfileDir
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $me = $env:USERNAME
  cmd /c "icacls `"$dir`" /grant `"$me`:(OI)(CI)F`" /T /C /Q" >$null 2>&1
  return $dir
}

function Stop-DistroKidDebugChrome {
  $markers = @(
    "DistroKid-Uploader\chrome-debug-profile",
    "local-secrets\chrome-debug-profile",
    "chrome-debug-profile"
  )
  $n = 0
  Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return }
    foreach ($m in $markers) {
      if ($cmd -like "*$m*") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $n++
        break
      }
    }
  }
  return $n
}

function Clear-DistroKidChromeLocks {
  $dir = Get-DistroKidChromeProfileDir
  if (-not (Test-Path -LiteralPath $dir)) { return }
  Get-ChildItem -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @("LOCK", "SingletonLock", "SingletonCookie", "SingletonSocket") } |
    Remove-Item -Force -ErrorAction SilentlyContinue
}

function Remove-DistroKidEphemeralCache {
  $ephemeral = @(
    "Cache", "Code Cache", "GPUCache", "GrShaderCache", "GraphiteDawnCache",
    "ShaderCache", "DawnCache", "DawnWebGPUCache", "Media Cache", "Crashpad",
    "Service Worker", "blob_storage", "File System"
  )
  $keep = @("Cookies", "Login Data", "Preferences", "Secure Preferences", "Web Data", "Network", "Local Storage", "Session Storage", "IndexedDB")
  foreach ($base in @((Get-DistroKidChromeProfileDir), (Join-Path (Get-DistroKidChromeProfileDir) "Default"))) {
    if (-not (Test-Path -LiteralPath $base)) { continue }
    Get-ChildItem -LiteralPath $base -Force -ErrorAction SilentlyContinue | ForEach-Object {
      if ($keep -contains $_.Name) { return }
      if ($_.PSIsContainer -and ($ephemeral -contains $_.Name)) {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
      }
    }
  }
}

function Remove-DistroKidLegacyLocalSecrets {
  param([string[]]$Roots)
  foreach ($r in $Roots) {
    if (-not $r) { continue }
    foreach ($name in @("local-secrets", "local-secrets.to_delete", "local-secrets.__delete_me__")) {
      $legacy = Join-Path $r $name
      if (-not (Test-Path -LiteralPath $legacy)) { continue }
      Write-Host "Removing legacy: $legacy"
      Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.CommandLine -and ($_.CommandLine -like "*$legacy*" -or $_.CommandLine -like "*local-secrets*")) {
          Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
      }
      Start-Sleep -Seconds 1
      $me = $env:USERNAME
      cmd /c "takeown /F `"$legacy`" /R /D Y" >$null 2>&1
      cmd /c "icacls `"$legacy`" /grant `"$me`":(F) /T /C /Q" >$null 2>&1
      cmd /c "icacls `"$legacy`" /grant Administrators:(F) /T /C /Q" >$null 2>&1
      Get-ChildItem -LiteralPath $legacy -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        try { $_.Attributes = "Normal" } catch {}
      }
      $empty = Join-Path $env:TEMP ("empty_del_" + [guid]::NewGuid().ToString("N"))
      New-Item -ItemType Directory -Force -Path $empty | Out-Null
      & robocopy $empty $legacy /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /nc /ns /np >$null 2>&1
      cmd /c "rd /s /q `"$empty`"" >$null 2>&1
      cmd /c "rd /s /q `"$legacy`"" >$null 2>&1
      if (Test-Path -LiteralPath $legacy) {
        Write-Host "  still locked - run .\6_force_remove_browser_temps.bat" -ForegroundColor Yellow
      }
    }
  }
}

function Invoke-DistroKidSessionCleanup {
  param(
    [string[]]$AppRoots = @($PSScriptRoot),
    [switch]$RemoveLogin
  )
  $n = Stop-DistroKidDebugChrome
  Start-Sleep -Seconds 1
  Clear-DistroKidChromeLocks
  if ($RemoveLogin) {
    $root = Join-Path $env:LOCALAPPDATA "DistroKid-Uploader"
    if (Test-Path -LiteralPath $root) {
      $me = $env:USERNAME
      cmd /c "takeown /F `"$root`" /R /D Y" >$null 2>&1
      cmd /c "icacls `"$root`" /grant `"$me`":(F) /T /C /Q" >$null 2>&1
      cmd /c "icacls `"$root`" /grant Administrators:(F) /T /C /Q" >$null 2>&1
      Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
  } else {
    Remove-DistroKidEphemeralCache
    Ensure-DistroKidChromeProfileWritable | Out-Null
  }
  Remove-DistroKidLegacyLocalSecrets -Roots $AppRoots
  return $n
}

