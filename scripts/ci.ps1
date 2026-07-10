[CmdletBinding()]
param(
    [ValidateSet("Smoke", "Pr", "Nightly")]
    [string]$Tier = "Pr"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$JuliaProject = Join-Path $Root "julia"

& (Join-Path $PSScriptRoot "doctor.ps1")
& python (Join-Path $PSScriptRoot "governance_lint.py")
if ($LASTEXITCODE -ne 0) { throw "Governance lint failed." }
& python (Join-Path $PSScriptRoot "architecture_lint.py")
if ($LASTEXITCODE -ne 0) { throw "Architecture lint failed." }
& python (Join-Path $Root "research\validate.py")
if ($LASTEXITCODE -ne 0) { throw "Research contract validation failed." }
& python -m unittest discover -s (Join-Path $Root "research\tests") -v
if ($LASTEXITCODE -ne 0) { throw "Research harness tests failed." }

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

$BenchmarkProject = Join-Path $Root "julia\GeoTargetBenchmarks"
if ($Tier -eq "Smoke") {
    & julia +1.12.6 --startup-file=no --history-file=no `
        "--project=$BenchmarkProject" `
        -e "using Pkg; Pkg.instantiate(); using GeoTargetBenchmarks"
} else {
    & julia +1.12.6 --startup-file=no --history-file=no `
        "--project=$BenchmarkProject" `
        -e "using Pkg; Pkg.instantiate(); Pkg.test()"
}
if ($LASTEXITCODE -ne 0) { throw "Analytic benchmark tests failed." }

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

$Qa02Runner = Join-Path $Root "julia\qa\run_qa02.jl"
if ($Tier -eq "Smoke") {
    $Qa02Arguments = @(
        "--graph-evaluations", "20",
        "--solve-executions", "4",
        "--skip-isolation"
    )
} elseif ($Tier -eq "Pr") {
    $Qa02Arguments = @(
        "--graph-evaluations", "60",
        "--solve-executions", "20",
        "--skip-isolation"
    )
} else {
    $Qa02Arguments = @(
        "--graph-evaluations", "10000",
        "--solve-executions", "1000",
        "--require-nightly-minimum"
    )
}
& julia +1.12.6 --startup-file=no --history-file=no `
    "--project=$JuliaProject" `
    $Qa02Runner @Qa02Arguments
if ($LASTEXITCODE -ne 0) { throw "QA-02 deterministic fuzz/metamorphic suite failed." }

Write-Host "GeoTarget CI tier '$Tier': OK"
