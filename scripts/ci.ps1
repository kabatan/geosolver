[CmdletBinding()]
param(
    [ValidateSet("Smoke", "Pr", "Nightly")]
    [string]$Tier = "Pr"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$JuliaProject = Join-Path $Root "julia"

& (Join-Path $PSScriptRoot "doctor.ps1")

$env:JULIA_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
& julia +1.12.6 --startup-file=no --history-file=no `
    "--project=$JuliaProject" `
    -e "using Pkg; Pkg.instantiate()"
if ($LASTEXITCODE -ne 0) { throw "Julia instantiate failed." }

& julia +1.12.6 --startup-file=no --history-file=no `
    "--project=$JuliaProject" `
    (Join-Path $Root "julia\integration\runtests.jl")
if ($LASTEXITCODE -ne 0) { throw "Julia tests failed." }

& uv sync --project (Join-Path $Root "python") --frozen --group dev
if ($LASTEXITCODE -ne 0) { throw "Python environment sync failed." }
& uv run --project (Join-Path $Root "python") ruff format --check (Join-Path $Root "python")
if ($LASTEXITCODE -ne 0) { throw "ruff format check failed." }
& uv run --project (Join-Path $Root "python") ruff check (Join-Path $Root "python")
if ($LASTEXITCODE -ne 0) { throw "ruff check failed." }
& uv run --project (Join-Path $Root "python") mypy (Join-Path $Root "python\src")
if ($LASTEXITCODE -ne 0) { throw "mypy failed." }
& uv run --project (Join-Path $Root "python") pytest (Join-Path $Root "python\tests")
if ($LASTEXITCODE -ne 0) { throw "pytest failed." }

if ($Tier -eq "Nightly") {
    Write-Host "Nightly property/fuzz suites are not implemented yet."
}

Write-Host "GeoTarget CI tier '$Tier': OK"
