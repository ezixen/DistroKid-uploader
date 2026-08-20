# Shared helpers (not a numbered step). Dot-sourced by steps 3 and 4.

function Resolve-PythonExe {
  $candidates = [System.Collections.Generic.List[string]]::new()
  function Add-Cand([string]$p) {
    if ($p -and (Test-Path -LiteralPath $p) -and ($p -notmatch '\\WindowsApps\\') -and -not $candidates.Contains($p)) {
      [void]$candidates.Add($p)
    }
  }

  Add-Cand "C:\.venv\Scripts\python.exe"
  foreach ($cmd in @("python", "python3")) {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($c -and $c.Source) { Add-Cand $c.Source }
  }
  if (Get-Command "py" -ErrorAction SilentlyContinue) {
    foreach ($arg in @("-3", "-3.14", "-3.13", "-3.12", "-3.11", "-3.10")) {
      try {
        $viaPy = & py $arg -c "import sys; print(sys.executable)" 2>$null
        if ($viaPy) { Add-Cand $viaPy.Trim() }
      } catch {}
    }
  }
  $pf = ${env:ProgramFiles}
  $local = $env:LOCALAPPDATA
  # Newest first
  foreach ($n in 20..10) {
    Add-Cand "$pf\Python3$n\python.exe"
    Add-Cand "$local\Programs\Python\Python3$n\python.exe"
  }

  $scored = @()
  foreach ($p in $candidates) {
    try {
      $raw = & $p -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
      if (-not $raw) { continue }
      $parts = ($raw.Trim() -split '\.') | ForEach-Object { [int]$_ }
      if ($parts[0] -ne 3 -or $parts[1] -lt 10) { continue }
      $hasWs = & $p -c "import websocket; print('WS')" 2>$null
      $scored += [pscustomobject]@{
        Path = $p
        Major = $parts[0]; Minor = $parts[1]; Patch = $parts[2]
        HasWs = ($hasWs -match 'WS')
      }
    } catch {}
  }
  if ($scored.Count -eq 0) {
    throw "Python 3.10+ not found on PATH. Run .\1_install.ps1 first (elevated)."
  }
  $bestWs = $scored | Where-Object { $_.HasWs } | Sort-Object Major, Minor, Patch -Descending | Select-Object -First 1
  if ($bestWs) { return $bestWs.Path }
  $fallback = $scored | Sort-Object Major, Minor, Patch -Descending | Select-Object -First 1
  Write-Warning "Python found but websocket-client missing: $($fallback.Path)"
  Write-Warning "Run .\1_install.ps1 or: pip install -r requirements.txt"
  return $fallback.Path
}

function Split-AlbumPathInput([string]$PathIn) {
  # Newlines / | / ; always separate.
  # Comma separates only when the next piece looks like a Windows path (D:\... or "D:\...).
  $normalized = $PathIn -replace '[\r\n]+', ';'
  $chunks = [regex]::Split($normalized, '\s*;\s*|\s*\|\s*|\s*,\s*(?=[A-Za-z]:\\|"[A-Za-z]:\\)')
  $out = @()
  foreach ($c in $chunks) {
    $t = $c.Trim().Trim('"').Trim("'")
    if ($t) { $out += $t }
  }
  return $out
}

function Resolve-AlbumFolders([string]$PathIn) {
  if ([string]::IsNullOrWhiteSpace($PathIn)) {
    Write-Host "Paste one album folder path, or several separated by ; (or , between drive paths)."
    Write-Host 'Example: d:\music\album1; d:\music\album2'
    $PathIn = Read-Host "Path(s)"
  }

  $rawParts = Split-AlbumPathInput $PathIn
  if ($rawParts.Count -eq 0) {
    throw "No folder path given."
  }

  $ok = New-Object System.Collections.Generic.List[string]
  $errors = New-Object System.Collections.Generic.List[string]

  foreach ($part in $rawParts) {
    if (-not (Test-Path -LiteralPath $part)) {
      $msg = "BAD PATH (not found): $part"
      $errors.Add($msg) | Out-Null
      Write-Host "ERROR: $msg" -ForegroundColor Red
      continue
    }
    $item = Get-Item -LiteralPath $part -ErrorAction SilentlyContinue
    if (-not $item -or -not $item.PSIsContainer) {
      $msg = "BAD PATH (not a folder): $part"
      $errors.Add($msg) | Out-Null
      Write-Host "ERROR: $msg" -ForegroundColor Red
      continue
    }
    $resolved = (Resolve-Path -LiteralPath $part).Path
    if (-not $ok.Contains($resolved)) { $ok.Add($resolved) | Out-Null }
  }

  return [pscustomobject]@{
    Folders = @($ok)
    Errors  = @($errors)
  }
}

function Get-UploaderPy {
  $p = Join-Path $PSScriptRoot "distrokid_upload_album.py"
  if (-not (Test-Path -LiteralPath $p)) {
    throw "Uploader not found: $p"
  }
  return $p
}
