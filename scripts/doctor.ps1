[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Runner = Join-Path $PSScriptRoot "doctor.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 $Runner
} elseif (Get-Command python3.12 -ErrorAction SilentlyContinue) {
    & python3.12 $Runner
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv run --no-project --python 3.12.11 python $Runner
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $Runner
} else {
    throw "Python 3.12.11 could not be launched with 'py', 'python3.12', 'uv', or 'python'."
}
if ($LASTEXITCODE -ne 0) { throw "GeoTarget doctor failed." }
