[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found."
    }
}

Require-Command "git"
Require-Command "julia"
Require-Command "python"
Require-Command "uv"

$JuliaVersion = (& julia +1.12.6 --startup-file=no --history-file=no --version).Trim()
if ($JuliaVersion -ne "julia version 1.12.6") {
    throw "Expected Julia 1.12.6, got '$JuliaVersion'."
}

$PythonVersion = (& python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))").Trim()
if ([version]$PythonVersion -lt [version]"3.12") {
    throw "Expected Python >=3.12, got '$PythonVersion'."
}

$GitRoot = (& git -C $Root rev-parse --show-toplevel).Trim().Replace("/", "\")
if ($GitRoot -ne $Root) {
    throw "Repository root mismatch: expected '$Root', got '$GitRoot'."
}

$Remotes = @(& git -C $Root remote)
if ($Remotes.Count -ne 0) {
    throw "Bootstrap repository must not have a remote."
}

Write-Host "GeoTarget doctor: OK ($JuliaVersion, Python $PythonVersion)"

