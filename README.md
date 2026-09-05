## Overview

This project builds a static interactive map of Australian childcare services using quarterly ACECQA NQS data.
The generated site is published from [`docs/index.html`](docs/index.html) and is suitable for GitHub Pages.

## Project Structure

```text
data/raw/              raw quarterly NQS files added manually
docs/                  build output directory used for local preview and Pages artifacts
scripts/build_map.ps1  local build helper
scripts/prepare_data.py data integration helper
scripts/download_data.py official data downloader
nqs_map.py             map generator
requirements.txt       Python dependencies
```

## Data Source

- Primary source: ACECQA quarterly NQS data workbook, for example `NQS Data Q4 2025.XLSX`
- Recommended workflow: drop the latest quarterly file into `data/raw/`, then rebuild the map
- The map page also shows the loaded source file, mapped service count, and rating date range

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Build

Prepare a current service dataset and rating history from ACECQA exports:

```powershell
python scripts/prepare_data.py `
  --registers "data/raw/Education-services-au-export.csv" `
  --nqs-timeseries "data/raw/NQS time series Q3 2013-Q2 2026.XLSX" `
  --out-current "data/processed/current_services.csv" `
  --out-history "data/processed/rating_history.csv"
```

The current dataset uses National Registers for current service details and
status, and the latest quarterly sheet from the NQS time-series workbook for
coordinates and ratings. The history output keeps one rating row per service
and quarter.

Download the official source files into `data/raw/`:

```powershell
python scripts/download_data.py
```

The raw files are deliberately not part of the normal code commit. They are
large, can change at the source, and the time-series workbook exceeds GitHub's
single-file limit. The downloader uses temporary files and only replaces an
existing file after a successful non-empty download.

Recommended:

```powershell
.\scripts\build_map.ps1
```

On macOS, Linux or CI, use the cross-platform Python builder:

```bash
python scripts/build_map.py
```

This script:
- looks in `data/raw/`
- selects the newest `.xlsx`, `.xls`, or `.csv`
- builds [`docs/index.html`](docs/index.html)

The `docs/` output is treated as a build artifact. GitHub Actions rebuilds it during deployment, so the committed source of truth is the raw data plus the build scripts rather than the generated HTML.

Explicit input:

```powershell
python nqs_map.py --input "data/raw/NQS Data Q4 2025.XLSX" --out "docs/index.html" --facets rating
```

Export a normalized CSV snapshot and build the map:

```powershell
python nqs_map.py --input "data/raw/NQS Data Q4 2025.XLSX" --export-normalized "normalized_q4_2025.csv" --out "docs/index.html"
```

Filter to a smaller map and export the filtered rows:

```powershell
python nqs_map.py --input "data/raw/NQS Data Q4 2025.XLSX" --out "docs/vic_exceeding.html" --filter "`Address State`=='VIC' and `Overall Rating` in ['Exceeding NQS','Excellent']" --export-filtered "filtered_vic_exceeding.csv"
```

Fast cluster overview:

```powershell
python nqs_map.py --input "data/raw/NQS Data Q4 2025.XLSX" --out "docs/index.html" --fast-cluster
```

## Notes

- `--input` accepts `.csv`, `.xlsx`, and `.xls`
- The legacy `--csv` flag still works as an alias for `--input`
- For Excel files, the script auto-detects a suitable sheet such as `Approved Services`
- `--sheet` is available if a workbook needs an explicit worksheet name
- `--export-normalized` writes the normalized input table after column-name cleanup, before filtering and map-only derived columns
- The generated map includes both `OpenStreetMap` and `CARTO Light` base layers
- `OpenStreetMap` is the default because it does not require a CARTO API key
- Hosted pages and local `file://` previews automatically fall back to `CARTO Light` if OSM tiles fail

## GitHub Pages

1. Commit the repo with at least one input file in `data/raw/`.
2. In GitHub, open `Settings -> Pages`.
3. Set `Source` to `GitHub Actions`.
4. Push to `main`, or run the `Deploy GitHub Pages` workflow manually.

The workflow in [`.github/workflows/pages.yml`](.github/workflows/pages.yml) runs the cross-platform Python build script on Ubuntu and publishes the contents of `docs/`.
Local builds are useful for previewing changes, but the deployed site is produced again inside GitHub Actions.

For better indexing on a GitHub Pages project site, add this repository variable in `Settings -> Secrets and variables -> Actions -> Variables`:

- `SITE_URL`
  Example: `https://yourusername.github.io/project_name/`

When `SITE_URL` is set, the build also generates:

- `docs/sitemap.xml`
- `docs/robots.txt`
- page `title`, `description`, `canonical`, and Open Graph tags

The page title and description are already defined in the project code, so you do not need to configure them in GitHub unless you later decide to make them dynamic.

## Filter Notes

Pandas query supports backticks around column names with spaces.

Examples:

```text
`Address State`=='VIC' and `Overall Rating`=='Excellent'
`Service Type`.str.contains('Centre-Based', case=False)
```

## TODO

1. Add a short intro panel explaining NQS ratings and what the map is showing.
2. Improve fullscreen behavior so fixed info cards and legends stay tidy.
3. Add optional external links in popups, such as Google Maps directions.
4. Add optional `tel:` links for service phone numbers in popups.
5. Consider highlighting stale ratings based on `Final Report Sent Date`.
6. Evaluate whether cluster styling should better reflect rating distribution.
7. Decide whether to expose provider-level views or keep the project service-focused.
