## Australian Childcare NQS Map

Generate an interactive Folium map from the ACECQA National Registers CSV and publish it with GitHub Pages.

## What Was Improved

1. Fixed a syntax error in `nqs_map.py` so the script can run again.
2. Made `--fast-cluster` actually work, which is important for large datasets and GitHub Pages.
3. Added a GitHub Actions workflow to build and deploy the map to GitHub Pages.
4. Updated the docs to use `python3` and the current script name.

## Local Setup

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```shell
# Recommended for a full national map
python3 nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out nqs_map.html --facets rating --fast-cluster

# Basic
python3 nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out nqs_map.html

# Faster CSV reading if pyarrow is installed
python3 nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out nqs_map.html --engine pyarrow

# Toggle layers by state, rating, or type
python3 nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out nqs_map.html --facets state
python3 nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out nqs_map.html --facets rating
python3 nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out nqs_map.html --facets type

# Filter first, then export the filtered CSV as well
python3 nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out nqs_map_vic_exceeding.html \
  --filter "`Address State`=='VIC' and `Overall Rating` in ['Exceeding NQS','Excellent']" \
  --export-filtered filtered_vic_exceeding.csv
```

Notes on `--filter`:

```text
`Address State`=='VIC' and `Overall Rating`=='Excellent'
`Service Type`.str.contains('Centre-Based', case=False)
```

## GitHub Pages

This repo now includes `.github/workflows/deploy-pages.yml`, which:

1. Installs Python and dependencies
2. Builds `site/index.html` from the CSV
3. Deploys that static site to GitHub Pages

After pushing to `main`, do this once in GitHub:

1. Open `Settings -> Pages`
2. Set `Source` to `GitHub Actions`
3. Push again if GitHub asks for a fresh deployment

The workflow currently publishes:

```shell
python3 nqs_map.py --csv 'NQS Data Q2 2025.CSV' --out site/index.html --facets rating --fast-cluster
```

That setting is a good default for GitHub Pages because it keeps the page lighter than the full rich-marker version.

## Next Obvious Improvements

1. Split the popup into a compact summary plus optional details, because the current HTML gets very large.
2. Add a generated timestamp and source CSV name into the page so users know how fresh the map is.
3. Add tests for CLI argument parsing and a tiny fixture CSV to protect the script from regressions.
4. Consider a state-level prefilter or multiple published pages if the national dataset gets too heavy.
