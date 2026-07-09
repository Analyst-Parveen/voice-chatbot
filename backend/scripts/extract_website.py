"""CLI: paste website URL(s) → save RAG-ready Markdown under data/extracted/.

Usage (from the ``backend/`` directory, with ingest extras installed)::

    pip install -e ".[ingest]"

    # Single URL
    python scripts/extract_website.py https://example.com/about

    # Multiple URLs
    python scripts/extract_website.py https://example.com https://example.com/faq

    # URLs from a text file (one URL per line)
    python scripts/extract_website.py --file urls.txt

    # Custom output folder + print Markdown to stdout
    python scripts/extract_website.py --url https://example.com --output ./data --print

After extraction, ingest into Qdrant when ready::

    python -m ingestion.run_ingestion --data-dir ../data/extracted
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ingestion.website_extractor import extract_website, extract_websites, save_all_extracted


def _read_url_file(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract website content into RAG-ready Markdown files.",
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="Website URL(s) to extract.",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        dest="url_flags",
        help="Additional URL (repeatable).",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Text file with one URL per line.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: ../data/extracted).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds (default: 20).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .md files instead of creating _2, _3 variants.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print extracted Markdown to stdout (still saves files unless --no-save).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Only print/extract in memory; do not write files.",
    )
    args = parser.parse_args()

    urls = list(args.urls) + list(args.url_flags)
    if args.file:
        if not args.file.exists():
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            return 1
        urls.extend(_read_url_file(args.file))

    urls = [u.strip() for u in urls if u.strip()]
    if not urls:
        parser.error("Provide at least one URL (argument, --url, or --file).")

    print(f"Extracting {len(urls)} URL(s)…\n")

    errors: list[str] = []
    saved: list[Path] = []

    for url in urls:
        try:
            page = extract_website(url, timeout=args.timeout)
            if args.print:
                print("=" * 72)
                print(page.rag_text)
                print()

            if not args.no_save:
                paths = save_all_extracted(
                    [page],
                    output_dir=args.output,
                    overwrite=args.overwrite,
                )
                saved.extend(paths)
                print(f"  OK  {page.url}")
                print(f"       -> {paths[0]}")
                if page.meta.get("description"):
                    desc = str(page.meta["description"])
                    print(f"       {desc[:100]}{'…' if len(desc) > 100 else ''}")
            else:
                print(f"  OK  {page.url}  ({page.title})")
        except Exception as exc:  # noqa: BLE001 - report and continue
            errors.append(f"{url}: {exc}")
            print(f"  FAIL {url}", file=sys.stderr)
            print(f"       {exc}", file=sys.stderr)

    print()
    if saved:
        print(f"Saved {len(saved)} file(s) to: {saved[0].parent}")
        print("\nNext step — ingest when ready:")
        print(f"  python -m ingestion.run_ingestion --data-dir {saved[0].parent}")

    if errors:
        print(f"\n{len(errors)} URL(s) failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
