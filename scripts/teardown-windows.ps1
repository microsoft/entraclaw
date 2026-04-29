# requires -Version 7.0
<#
.SYNOPSIS
  EntraClaw — Windows teardown. Reverse of setup-windows.ps1.

.DESCRIPTION
  Removes:
    - Blueprint cert(s) from Cert:\CurrentUser\My matching the
      Subject CN=entraclaw-blueprint.
    - %LOCALAPPDATA%\entraclaw\ data dir.
    - .env BLUEPRINT_CERT_* lines (preserves the rest of the file).
    - MSAL cache.
    - MCP registration (via mcp_config.py --unregister).

  Does NOT delete the Entra app registrations (Blueprint / Agent
  Identity / Agent User) — those persist in the tenant. Use the
  cleanup-orphans.sh equivalent in the cloud admin portal.
#>

[CmdletBinding()]
param([switch]$Force, [switch]$Help)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($Help) { Get-Help $PSCommandPath -Detailed; exit 0 }
if (-not $IsWindows) { throw "teardown-windows.ps1 must run on Windows." }

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)

if (-not $Force) {
    $resp = Read-Host "Remove all local entraclaw state on this machine? [y/N]"
    if ($resp -notmatch '^[Yy]') { Write-Host "aborted."; exit 0 }
}

# Remove certs by Subject — safer than thumbprint (which may be stale).
Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq 'CN=entraclaw-blueprint' } |
    ForEach-Object {
        Write-Host "Removing cert $($_.Thumbprint)..."
        Remove-Item $_.PSPath -Force
    }

# Local data dir.
$dataDir = Join-Path $env:LOCALAPPDATA 'entraclaw'
if (Test-Path $dataDir) {
    Write-Host "Removing $dataDir..."
    Remove-Item -Recurse -Force $dataDir
}

# .env: strip BLUEPRINT_CERT_* lines but keep the rest.
$envPath = Join-Path $ProjectRoot '.env'
if (Test-Path $envPath) {
    $kept = Get-Content $envPath | Where-Object {
        $_ -notmatch '^(ENTRACLAW_BLUEPRINT_CERT_THUMBPRINT|ENTRACLAW_BLUEPRINT_CERT_SHA1|ENTRACLAW_BLUEPRINT_KSP)='
    }
    $kept | Set-Content $envPath -Encoding utf8
    Write-Host "Stripped BLUEPRINT_CERT_* from .env."
}

# MCP unregister.
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (Test-Path $VenvPython) {
    & $VenvPython (Join-Path $ProjectRoot 'scripts\mcp_config.py') --unregister 2>$null
}

Write-Host "Teardown complete." -ForegroundColor Green
