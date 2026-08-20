# 3) Optional â€” preview titles / cover / prices (no upload)
# Supports one path, or several separated by ; (or , between drive paths)
#
#   .\3_check_titles.ps1
#   .\3_check_titles.ps1 "d:\music\a; d:\music\b"

param(
  [Parameter(Mandatory = $false, Position = 0)]
  [string]$AlbumFolder
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_common.ps1")

$resolved = Resolve-AlbumFolders $AlbumFolder
$python = Resolve-PythonExe
$script = Get-UploaderPy

Write-Host "Python: $python"
Write-Host ("Albums to check: {0}" -f $resolved.Folders.Count)
if ($resolved.Errors.Count -gt 0) {
  Write-Host ("Path errors: {0}" -f $resolved.Errors.Count) -ForegroundColor Red
}

$failed = New-Object System.Collections.Generic.List[string]
$i = 0
foreach ($folder in $resolved.Folders) {
  $i++
  Write-Host ""
  Write-Host "======== CHECK $i / $($resolved.Folders.Count): $folder ========" -ForegroundColor Cyan
  try {
    & $python -u $script $folder --dry-run
    if ($LASTEXITCODE -ne 0) {
      $msg = "CHECK FAILED (exit $LASTEXITCODE): $folder"
      $failed.Add($msg) | Out-Null
      Write-Host "ERROR: $msg" -ForegroundColor Red
    }
  } catch {
    $msg = "CHECK FAILED: $folder â€” $($_.Exception.Message)"
    $failed.Add($msg) | Out-Null
    Write-Host "ERROR: $msg" -ForegroundColor Red
  }
}

Write-Host ""
Write-Host "======== CHECK SUMMARY ========"
Write-Host ("OK folders: {0}" -f ($resolved.Folders.Count - $failed.Count))
if ($resolved.Errors.Count -gt 0) {
  Write-Host "Path errors:" -ForegroundColor Red
  $resolved.Errors | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}
if ($failed.Count -gt 0) {
  Write-Host "Check failures:" -ForegroundColor Red
  $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}

if ($resolved.Folders.Count -eq 0) {
  Write-Host "Nothing to check â€” fix paths and try again." -ForegroundColor Red
  exit 1
}

$okFolders = @($resolved.Folders | Where-Object { $f = $_; -not ($failed | Where-Object { $_ -like "*$f" }) })
if ($okFolders.Count -gt 0) {
  Write-Host ""
  Write-Host "Upload draft(s) with:"
  if ($okFolders.Count -eq 1) {
    Write-Host ("  .\4_distrokid_uploader.ps1 `"{0}`"" -f $okFolders[0])
  } else {
    Write-Host ("  .\4_distrokid_uploader.ps1 `"{0}`"" -f ($okFolders -join '; '))
  }
}

if ($resolved.Errors.Count -gt 0 -or $failed.Count -gt 0) { exit 1 }
exit 0
