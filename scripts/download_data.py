#!/usr/bin/env python3
"""Download the official ACECQA source files used by the data pipeline."""

import argparse
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen


SOURCES = {
    'nqs_latest': {
        'filename': 'NQS Data Q2 2026.XLSX',
        'url': 'https://www.acecqa.gov.au/media/48446',
        'referer': 'https://www.acecqa.gov.au/resources/snapshot-and-reports/nqf-snapshots',
    },
    'nqs_history': {
        'filename': 'NQS time series Q3 2013-Q2 2026.XLSX',
        'url': 'https://acecqara.learnupon.com/r/wjsqj4omvea6yt15un3hn3tnilsvq96',
        'referer': 'https://www.acecqa.gov.au/resources/snapshot-and-reports/nqf-snapshots',
    },
    'registers': {
        'filename': 'Education-services-au-export.csv',
        'url': 'https://www.acecqa.gov.au/sites/default/files/national-registers/services/Education-services-au-export.csv',
        'referer': 'https://www.acecqa.gov.au/resources/national-registers',
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('data/raw'))
    parser.add_argument('--source', choices=[*SOURCES, 'all'], default='all')
    return parser.parse_args()


def download(source: dict, output_dir: Path) -> Path:
    destination = output_dir / source['filename']
    output_dir.mkdir(parents=True, exist_ok=True)
    request = Request(source['url'], headers={
        'Accept': '*/*',
        'Referer': source['referer'],
        'User-Agent': 'Mozilla/5.0 (compatible; ACECQA-NQS-map-data-loader/1.0)',
    })

    with tempfile.NamedTemporaryFile(dir=output_dir, prefix='.download-', delete=False) as tmp:
        temporary_path = Path(tmp.name)
        try:
            with urlopen(request, timeout=120) as response:
                shutil.copyfileobj(response, tmp)
            if temporary_path.stat().st_size == 0:
                raise RuntimeError('downloaded file is empty')
            temporary_path.replace(destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    return destination


def main() -> None:
    args = parse_args()
    selected = SOURCES if args.source == 'all' else {args.source: SOURCES[args.source]}
    for name, source in selected.items():
        try:
            path = download(source, args.output_dir)
            print(f'{name}: {path}')
        except Exception as error:
            raise SystemExit(f'{name}: download failed: {error}') from error


if __name__ == '__main__':
    main()
