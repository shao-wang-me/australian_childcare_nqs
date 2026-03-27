param(
    [string]$InputPath = "",
    [string]$Sheet = "",
    [string]$OutputPath = "docs/index.html",
    [string]$SiteUrl = $env:SITE_URL,
    [string]$SiteTitle = $env:SITE_TITLE,
    [string]$SiteDescription = $env:SITE_DESCRIPTION
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

if (-not $SiteTitle) {
    $SiteTitle = "Australian Childcare NQS Map"
}

if (-not $SiteDescription) {
    $SiteDescription = "Interactive map of Australian childcare services using quarterly ACECQA NQS data."
}

$args = @(
    "nqs_map.py",
    "--input", $InputPath,
    "--out", $OutputPath,
    "--facets", "rating",
    "--site-title", $SiteTitle,
    "--site-description", $SiteDescription
)

if ($Sheet) {
    $args += @("--sheet", $Sheet)
}

if ($SiteUrl) {
    $SiteUrl = $SiteUrl.TrimEnd('/') + '/'
    $args += @("--site-url", $SiteUrl)
}

Write-Host "Building map from: $InputPath"
& $python @args

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($SiteUrl) {
    $sitemapPath = Join-Path $outputDir "sitemap.xml"
    $robotsPath = Join-Path $outputDir "robots.txt"
    $sitemap = @"
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>$SiteUrl</loc>
  </url>
</urlset>
"@
    $robots = @"
User-agent: *
Allow: /

Sitemap: ${SiteUrl}sitemap.xml
"@
    Set-Content -LiteralPath $sitemapPath -Value $sitemap -Encoding utf8
    Set-Content -LiteralPath $robotsPath -Value $robots -Encoding utf8
}
