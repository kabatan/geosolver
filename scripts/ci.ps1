[CmdletBinding()]
param(
    [ValidateSet("Smoke", "Pr", "Nightly")]
    [string]$Tier = "Pr"
)

$ErrorActionPreference = "Stop"
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 (Join-Path $PSScriptRoot "ci.py") --tier $Tier
} elseif (Get-Command python3.12 -ErrorAction SilentlyContinue) {
    & python3.12 (Join-Path $PSScriptRoot "ci.py") --tier $Tier
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv run --no-project --python 3.12.11 python (Join-Path $PSScriptRoot "ci.py") --tier $Tier
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python (Join-Path $PSScriptRoot "ci.py") --tier $Tier
} else {
    throw "Python 3.12.11 could not be launched with 'py', 'python3.12', 'uv', or 'python'."
}
if ($LASTEXITCODE -ne 0) { throw "GeoTarget CI tier '$Tier' failed." }
