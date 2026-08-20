# Sign a Windows EXE as publisher CN=ezixen (Authenticode, SHA256).
# Creates a CurrentUser code-signing cert named "ezixen" if none is valid.
# Self-signed: improves Properties / Digital Signatures tab; Smart App Control on
# other PCs may still require a CA-trusted (paid) code-signing certificate.
#
# Usage:
#   . .\app\sign_exe.ps1
#   Invoke-EzixenSign -ExePath '.\app\DistroKid-Uploader\DistroKid-Uploader.exe'

function Get-SignToolPath {
  $kits = 'C:\Program Files (x86)\Windows Kits\10\bin'
  $found = Get-ChildItem -LiteralPath $kits -Recurse -Filter 'signtool.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1
  if (-not $found) { throw "signtool.exe (x64) not found under Windows Kits. Install Windows SDK." }
  return $found.FullName
}

function Get-EzixenCodeSigningCert {
  $now = Get-Date
  $existing = Get-ChildItem Cert:\CurrentUser\My -ErrorAction SilentlyContinue |
    Where-Object {
      $_.Subject -eq 'CN=ezixen' -and
      $_.HasPrivateKey -and
      $_.NotAfter -gt $now.AddDays(1) -and
      ($_.EnhancedKeyUsageList | Where-Object { $_.FriendlyName -eq 'Code Signing' -or $_.ObjectId -eq '1.3.6.1.5.5.7.3.3' })
    } |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1

  if ($existing) {
    Write-Host "Using code-signing cert: $($existing.Thumbprint) (expires $($existing.NotAfter.ToString('yyyy-MM-dd')))"
    return $existing
  }

  Write-Host "Creating new CurrentUser code-signing certificate: CN=ezixen"
  $cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject 'CN=ezixen' `
    -FriendlyName 'ezixen code signing' `
    -KeyExportPolicy Exportable `
    -KeySpec Signature `
    -KeyLength 2048 `
    -HashAlgorithm SHA256 `
    -NotAfter (Get-Date).AddYears(5) `
    -CertStoreLocation 'Cert:\CurrentUser\My'

  Write-Host "Created cert thumbprint: $($cert.Thumbprint)"
  return $cert
}

function Invoke-EzixenSign {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath
  )
  if (-not (Test-Path -LiteralPath $ExePath)) { throw "EXE not found: $ExePath" }

  $signtool = Get-SignToolPath
  $cert = Get-EzixenCodeSigningCert
  $thumb = $cert.Thumbprint

  Write-Host "Signing $ExePath as CN=ezixen ..."
  & $signtool sign `
    /fd SHA256 `
    /td SHA256 `
    /tr 'http://timestamp.digicert.com' `
    /sha1 $thumb `
    /d 'ezixen' `
    /du 'https://github.com/ezixen' `
    $ExePath

  if ($LASTEXITCODE -ne 0) {
    Write-Host "Timestamped sign failed (exit $LASTEXITCODE); retrying without timestamp..."
    & $signtool sign `
      /fd SHA256 `
      /sha1 $thumb `
      /d 'ezixen' `
      /du 'https://github.com/ezixen' `
      $ExePath
    if ($LASTEXITCODE -ne 0) { throw "signtool failed: $LASTEXITCODE" }
  }

  $sig = Get-AuthenticodeSignature -FilePath $ExePath
  Write-Host "Signature Status: $($sig.Status)  Signer: $($sig.SignerCertificate.Subject)"
  if (-not $sig.SignerCertificate) { throw "No Authenticode signature on $ExePath" }
  Write-Host "Signed OK: $ExePath"
  Write-Host "Note: self-signed CN=ezixen - Smart App Control on other PCs may still block until you use a CA-trusted code-signing cert."
}
