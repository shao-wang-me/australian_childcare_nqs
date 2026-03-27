## Usage

```shell
pip install -r requirements.txt

# Most useful: build the GitHub Pages site from the latest file in data/raw
powershell -ExecutionPolicy Bypass -File .\scripts\build_map.ps1

# Build directly from a raw quarterly workbook
python nqs_map.py --input "data/raw/NQS Data Q4 2025.XLSX" --out "docs/index.html" --facets rating

# Explicit Excel sheet
python nqs_map.py --input "data/raw/NQAITS Quarterly Data Splits (Q3 2013 - Q4 2025).xlsx" --sheet Q42025data --out "docs/index.html"

# Export a normalized CSV from the raw Excel before mapping
python nqs_map.py --input "data/raw/NQS Data Q4 2025.XLSX" --export-normalized normalized_q4_2025.csv --out "docs/index.html"

# Filter then export a filtered CSV and map only those records
python nqs_map.py --input "data/raw/NQS Data Q4 2025.XLSX" --out "docs/vic_exceeding.html" \
  --filter "`Address State`=='VIC' and `Overall Rating` in ['Exceeding NQS','Excellent']" \
  --export-filtered filtered_vic_exceeding.csv

# When too many points: use fast cluster (no rich popups, best for overview)
python nqs_map.py --input "data/raw/NQS Data Q4 2025.XLSX" --out "docs/index.html" --fast-cluster
```

## Notes

- `--input` accepts `.csv`, `.xlsx`, and `.xls`. The legacy `--csv` flag still works.
- For Excel files, the script auto-detects a suitable sheet such as `Approved Services` or `Q42025data`. Use `--sheet` to override.
- `--export-normalized` is useful when you want to keep a flat CSV snapshot generated from the original quarterly workbook.
- `scripts/build_map.ps1` looks in `data/raw/` and uses the newest `.xlsx/.xls/.csv` it finds.
- The generated map includes both `OpenStreetMap` and `CARTO Light` base layers.
- Local `file://` opens default to `CARTO Light` because OSM may block requests without a referer.
- Hosted pages such as GitHub Pages prefer `OpenStreetMap` and automatically fall back to `CARTO Light` if OSM tiles fail.
- The layer control lets you switch base maps manually at any time.

## Structure

```text
data/raw/              raw quarterly NQS files you drop in manually
docs/index.html        published GitHub Pages site
scripts/build_map.ps1  local build helper
nqs_map.py             map generator
```

## GitHub Pages

1. Commit the repo with at least one input file in `data/raw/`.
2. In GitHub, open `Settings -> Pages`.
3. Set `Source` to `GitHub Actions`.
4. Push to `main`, or run the `Deploy GitHub Pages` workflow manually.

> Notes on --filter:
> 
> Pandas query supports backticks around column names with spaces.
> Examples:
> 
> ```
> `Address State`=='VIC' and `Overall Rating`=='Excellent'`
> `Service Type`.str.contains('Centre-Based', case=False)
> ```

## TODO

1. cluster style customisation
2. provider id
3. explain NQS etc. (link to A...)
4. legends not shown in fullscreen
5. starting blocks links
6. red if report date is too long ago
7. tel:
8. google maps link?
