#!/usr/bin/env python3
"""Build the static map using the same entry point on every platform."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the static NQS map.")
    parser.add_argument("--input", help="Input data file. Defaults to the newest raw data file.")
    parser.add_argument("--sheet", default="", help="Optional Excel worksheet name.")
    parser.add_argument("--output", default="docs/index.html", help="Generated HTML path.")
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", ""))
    parser.add_argument("--site-title", default=os.environ.get("SITE_TITLE", "Australian Childcare NQS Map"))
    parser.add_argument(
        "--site-description",
        default=os.environ.get(
            "SITE_DESCRIPTION",
            "Interactive map of Australian childcare services using quarterly ACECQA NQS data.",
        ),
    )
    return parser.parse_args()


def choose_input(repo_root: Path, requested: str) -> Path:
    if requested:
        path = Path(requested)
        if not path.is_absolute():
            path = repo_root / path
        if not path.exists():
            raise SystemExit(f"Input file not found: {path}")
        return path

    raw_dir = repo_root / "data" / "raw"
    candidates = sorted(
        (path for path in raw_dir.iterdir() if path.suffix.lower() in {".csv", ".xls", ".xlsx"}),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if raw_dir.exists() else []
    if not candidates:
        raise SystemExit("No input file found in data/raw. Pass --input explicitly.")
    return candidates[0]


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_path = choose_input(repo_root, args.input or "")
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(repo_root / "nqs_map.py"),
        "--input", str(input_path),
        "--out", str(output_path),
        "--facets", "rating",
        "--site-title", args.site_title,
        "--site-description", args.site_description,
        "--build-rev", subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, text=True
        ).strip(),
    ]
    if args.sheet:
        command.extend(["--sheet", args.sheet])
    if args.site_url:
        command.extend(["--site-url", args.site_url.rstrip("/") + "/"])

    print(f"Building map from: {input_path}")
    subprocess.run(command, cwd=repo_root, check=True)

    site_url = args.site_url.rstrip("/") + "/" if args.site_url else ""
    if site_url:
        (output_path.parent / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{site_url}</loc></url>\n"
            "</urlset>\n",
            encoding="utf-8",
        )
        (output_path.parent / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\n\nSitemap: {site_url}sitemap.xml\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
