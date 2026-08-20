# 1) First-time setup — elevated: newest winget Python 3.x + pip requirements
#
#   .\1_install.ps1
#   .\1_install.ps1 -DryRun

param(
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-PythonVersionTuple([string]$Exe) {
  try {
    $raw = & $Exe -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
    if (-not $raw) { return $null }
    $parts = ($raw.Trim() -split '\.') | ForEach-Object { [int]$_ }
    if ($parts.Count -ge 2) { return ,$parts }
  } catch {}
  return $null
}

function Find-BestPython {
  # Prefer newest usable CPython 3.10+ on the machine (skip WindowsApps stubs).
  $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  $found = New-Object System.Collections.Generic.List[object]

  function Consider([string]$p) {
    if (-not $p) { return }
    if ($p -match '\\WindowsApps\\') { return }
    if (-not (Test-Path -LiteralPath $p)) { return }
    if (-not $seen.Add($p)) { return }
    $ver = Get-PythonVersionTuple $p
    if (-not $ver) { return }
    if ($ver[0] -ne 3 -or $ver[1] -lt 10) { return }
    $found.Add([pscustomobject]@{ Path = $p; Version = $ver }) | Out-Null
  }

  foreach ($cmd in @("python", "python3")) {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($c -and $c.Source) { Consider $c.Source }
  }
  if (Get-Command "py" -ErrorAction SilentlyContinue) {
    foreach ($arg in @("-3", "-3.14", "-3.13", "-3.12", "-3.11", "-3.10")) {
      try {
        $exe = & py $arg -c "import sys; print(sys.executable)" 2>$null
        if ($exe) { Consider $exe.Trim() }
      } catch {}
    }
  }

  $roots = @(
    "${env:ProgramFiles}",
    ${env:ProgramFiles(x86)},
    "$env:LOCALAPPDATA\Programs\Python"
  ) | Where-Object { $_ }
  foreach ($root in $roots) {
    foreach ($n in 20..10) {
      Consider (Join-Path $root "Python3$n\python.exe")
      Consider (Join-Path $root "Python\Python3$n\python.exe")
    }
  }
  Consider "C:\.venv\Scripts\python.exe"

  if ($found.Count -eq 0) { return $null }
  return ($found | Sort-Object @{ Expression = { $_.Version[0] } }, @{ Expression = { $_.Version[1] } }, @{ Expression = { $_.Version[2] } } -Descending | Select-Object -First 1).Path
}

function Get-LatestWingetPythonId {
  # Newest Python.Python.3.N from winget (not Embeddable / Install Manager).
  $out = & winget search --id Python.Python.3 --source winget 2>$null | Out-String
  if (-not $out) { return "Python.Python.3.14" }
  $bestId = $null
  $bestMinor = -1
  foreach ($line in ($out -split "`r?`n")) {
    if ($line -notmatch 'Python\.Python\.3\.(\d+)\s') { continue }
    if ($line -match 'Embeddable|InstallManager') { continue }
    $minor = [int]$Matches[1]
    if ($minor -gt $bestMinor) {
      $bestMinor = $minor
      $bestId = "Python.Python.3.$minor"
    }
  }
  if ($bestId) { return $bestId }
  return "Python.Python.3.14"
}

$repoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

if (-not (Test-IsAdmin)) {
  Write-Host "Requesting elevated PowerShell (Administrator) for install..."
  $argList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$PSCommandPath`""
  )
  if ($DryRun) { $argList += "-DryRun" }
  $exe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
  $proc = Start-Process -FilePath $exe -Verb RunAs -ArgumentList $argList -PassThru -Wait
  exit $proc.ExitCode
}

Write-Host "=== Bandcamp Uploader install (elevated) ==="
Write-Host "Repo: $repoRoot"
Write-Host ""

$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
  throw "winget not found. Install App Installer from the Microsoft Store, then re-run."
}

$pythonId = Get-LatestWingetPythonId
$existing = Find-BestPython

Write-Host "Latest winget Python package: $pythonId"
if ($existing) {
  $ev = Get-PythonVersionTuple $existing
  Write-Host ("Already on this PC: {0}  ({1})" -f $existing, ($ev -join '.'))
} else {
  Write-Host "No Python 3.10+ found yet — will install via winget."
}
Write-Host ""

if ($DryRun) {
  Write-Host "DryRun: would ensure $pythonId (skip install if newer/equal already present), then pip install requirements."
  winget --version
  Write-Host "DryRun OK."
  exit 0
}

$needInstall = $true
if ($existing) {
  # Skip winget if we already have a 3.10+ interpreter (user may already have newest).
  Write-Host "Skipping winget Python install — using existing interpreter."
  $needInstall = $false
}

if ($needInstall) {
  $wingetArgs = @(
    "install",
    "-e",
    "--id", $pythonId,
    "--accept-package-agreements",
    "--accept-source-agreements"
  )
  Write-Host ("Installing: winget " + ($wingetArgs -join " "))
  & winget @wingetArgs
  Write-Host "winget exit: $LASTEXITCODE"
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path", "User")
}

$python = Find-BestPython
if (-not $python) {
  throw "Python 3.10+ not found after install. Open a new terminal and re-run .\1_install.ps1"
}

Write-Host "Using Python: $python"
& $python -c "import sys; print(sys.version)"
& $python -m pip install --upgrade pip
$req = Join-Path $repoRoot "requirements.txt"
if (Test-Path $req) {
  & $python -m pip install -r $req
} else {
  & $python -m pip install "websocket-client>=1.6.0"
}

$prices = Join-Path $repoRoot "prices.txt"
if (-not (Test-Path $prices)) {
  $txt = @"
# Default Bandcamp draft prices (edit anytime)
album=9.99
track=0.99
"@
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($prices, $txt, $utf8)
  Write-Host "Created prices.txt"
}

Write-Host ""
Write-Host "Install complete."
Write-Host "Next: .\2_start_chrome.bat  (log into Bandcamp once)"
Write-Host "Or:   app\BandCamp-Uploader\BandCamp-Uploader.exe"
Write-Host "Then: .\4_bandcamp_uploader.bat"
exit 0
