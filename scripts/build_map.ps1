param(
    [string]$InputPath = "",
    [string]$Sheet = "",
    [string]$OutputPath = "docs/index.html"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if (-not $InputPath) {
    $candidates = Get-ChildItem -Path (Join-Path $repoRoot "data\raw") -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in ".xlsx", ".xls", ".csv" } |
        Sort-Object LastWriteTimeUtc -Descending

    if ($candidates.Count -eq 0) {
        throw "No input file found. Put a quarterly NQS file in data\raw or pass -InputPath."
    } else {
        $InputPath = $candidates[0].FullName
    }
}

$outputDir = Split-Path -Parent $OutputPath
if ($outputDir) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$args = @(
    "nqs_map.py",
    "--input", $InputPath,
    "--out", $OutputPath,
    "--facets", "rating"
)

if ($Sheet) {
    $args += @("--sheet", $Sheet)
}

Write-Host "Building map from: $InputPath"
& $python @args
