"""Fetch company web pages, save them to ``data/``, and embed them into Qdrant.

Give it one or more URLs (or a whole site with ``--crawl``). It:

  1. Extracts each page to clean, RAG-ready Markdown (YAML frontmatter + body)
     and saves it under ``data/extracted/`` — the exact format the ingestion
     pipeline already understands.
  2. Runs the normal ingestion pipeline (clean -> chunk -> embed -> upsert into
     Qdrant) over the WHOLE ``data/`` folder, incrementally: unchanged files are
     skipped, only new/changed ones are re-embedded, and nothing is deleted by
     surprise.

Nothing about the app or its logic is modified — this only *reuses* the existing
``ingestion`` modules. No URL is hardcoded; you pass it on the command line.

Prerequisites
-------------
* Backend deps installed (the venv created by backend-setup).
* ``backend/.env`` in a real mode (e.g. RUN_MODE=local-light) so a real
  embedding model is used. The first run downloads the embedder (bge-m3, ~2GB).
* Stop the backend (uvicorn) first — the embedded Qdrant is a single-writer
  local folder and the app locks it while running with RAG enabled.

Usage (run from anywhere)
-------------------------
    python scripts/fetch_and_ingest.py https://acme.com/about https://acme.com/faq
    python scripts/fetch_and_ingest.py --urls-file urls.txt
    python scripts/fetch_and_ingest.py https://acme.com --crawl --max-pages 30
    python scripts/fetch_and_ingest.py https://acme.com --extract-only   # save .md, skip embed
    python scripts/fetch_and_ingest.py https://acme.com --recreate       # rebuild the collection

After it finishes: set RAG_ENABLED=true in backend/.env (if not already) and
restart uvicorn — the assistant will then answer from these pages.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

# --- Make the backend package importable no matter where this is launched. ---
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.rag.embedder import get_embedder  # noqa: E402
from app.rag.vector_store import QdrantVectorStore  # noqa: E402
from ingestion.run_ingestion import discover  # noqa: E402  (full-folder discovery)
from ingestion.pipeline import IngestionPipeline  # noqa: E402
from ingestion.website_extractor import extract_website, save_extracted  # noqa: E402

logger = get_logger("fetch_and_ingest")

_USER_AGENT = "voice-ai-fetch/1.0 (+company-knowledge-ingest)"
_DATA_DIR = _REPO_ROOT / "data"
_EXTRACTED_DIR = _DATA_DIR / "extracted"


# ---------------------------------------------------------------------------
# URL collection
# ---------------------------------------------------------------------------
def _read_seed_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = list(args.urls)
    if args.urls_file:
        for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    # Normalise + de-duplicate, preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u = u.strip()
        if not u:
            continue
        if not u.startswith(("http://", "https://")):
            u = f"https://{u}"
        key = u.split("#")[0].rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _same_domain_links(html: str, base_url: str) -> list[str]:
    from bs4 import BeautifulSoup

    base_host = urlparse(base_url).netloc
    links: list[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        joined = urljoin(base_url, a["href"]).split("#")[0].rstrip("/")
        parsed = urlparse(joined)
        if parsed.scheme in ("http", "https") and parsed.netloc == base_host:
            # Skip obvious non-content assets.
            if not parsed.path.lower().endswith(
                (".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf", ".zip", ".mp4", ".css", ".js")
            ):
                links.append(joined)
    return links


def _crawl(seeds: list[str], *, max_pages: int, timeout: float) -> list[str]:
    """Breadth-first, same-domain crawl starting from the seed URL(s)."""
    import requests

    seen: set[str] = set()
    queue: list[str] = list(seeds)
    pages: list[str] = []
    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        pages.append(url)
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": _USER_AGENT})
            resp.raise_for_status()
            for link in _same_domain_links(resp.text, url):
                if link not in seen and link not in queue:
                    queue.append(link)
        except Exception as exc:  # noqa: BLE001 - crawling is best-effort
            print(f"  (crawl skip {url}: {exc})", file=sys.stderr)
    return pages[:max_pages]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch web page(s) -> data/extracted/*.md -> embed into Qdrant."
    )
    parser.add_argument("urls", nargs="*", help="One or more page URLs.")
    parser.add_argument("--urls-file", help="Text file with one URL per line (# comments ok).")
    parser.add_argument("--crawl", action="store_true",
                        help="Follow same-domain links from the seed URL(s).")
    parser.add_argument("--max-pages", type=int, default=25,
                        help="Max pages to fetch when crawling (default 25).")
    parser.add_argument("--timeout", type=float, default=20.0,
                        help="Per-page fetch timeout in seconds (default 20).")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite an existing .md for the same URL.")
    parser.add_argument("--extract-only", action="store_true",
                        help="Only fetch + save Markdown; skip embedding.")
    parser.add_argument("--recreate", action="store_true",
                        help="Rebuild the Qdrant collection from scratch.")
    args = parser.parse_args()

    seeds = _read_seed_urls(args)
    if not seeds:
        parser.error("Provide at least one URL (positional) or --urls-file.")

    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=False)

    # ---- Resolve the page list ------------------------------------------
    if args.crawl:
        print(f"Crawling from {len(seeds)} seed(s), up to {args.max_pages} pages ...")
        page_urls = _crawl(seeds, max_pages=args.max_pages, timeout=args.timeout)
    else:
        page_urls = seeds
    print(f"Pages to fetch: {len(page_urls)}\n")

    # ---- 1) Fetch + save each page as RAG-ready Markdown ----------------
    saved: list[Path] = []
    for url in page_urls:
        try:
            print(f"[fetch] {url}")
            page = extract_website(url, timeout=args.timeout)
            path = save_extracted(page, _EXTRACTED_DIR, overwrite=args.overwrite)
            words = len(page.markdown.split())
            print(f"   -> {path.relative_to(_REPO_ROOT)}  ({words} words | {page.title!r})")
            saved.append(path)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"   !! failed: {exc}", file=sys.stderr)

    if not saved:
        print("\nNo pages were saved. Nothing to embed.")
        return 1

    if args.extract_only:
        print(f"\nExtract-only: {len(saved)} file(s) saved under "
              f"{_EXTRACTED_DIR.relative_to(_REPO_ROOT)}.")
        print("Embed later with:  python -m ingestion.run_ingestion --data-dir "
              f"{_DATA_DIR}   (run from the backend/ folder)")
        return 0

    # ---- 2) Embed the WHOLE data/ folder into Qdrant --------------------
    # Run with cwd = backend/ so the relative QDRANT_PATH (./qdrant_local) and the
    # manifest resolve to the SAME place the backend reads at query time.
    os.chdir(_BACKEND_DIR)

    documents = discover(_DATA_DIR)  # every file in data/, incl. the new pages
    if not documents:
        print("\nNo ingestable documents found in data/.")
        return 1

    embedder = get_embedder(settings)
    store = QdrantVectorStore.from_settings(settings)
    pipeline = IngestionPipeline(embedder, store)
    manifest_path = _DATA_DIR / ".ingest_manifest.json"

    print(f"\n[embed] {len(documents)} source(s) -> collection '{store.collection}' "
          f"(model={getattr(embedder, 'name', '?')}, dim={embedder.dimension}) ...")
    print("        (first run downloads the embedding model — this can take a while)")
    stats = pipeline.run(documents, manifest_path=manifest_path, recreate=args.recreate)

    print(
        "\nDone:\n"
        f"  pages fetched:   {len(saved)}\n"
        f"  sources total:   {stats.sources_total}\n"
        f"  indexed:         {stats.indexed}\n"
        f"  skipped:         {stats.skipped} (unchanged)\n"
        f"  deleted:         {stats.deleted} (sources removed from data/)\n"
        f"  chunks upserted: {stats.chunks_upserted}\n"
        f"  total vectors:   {store.count()}"
    )
    print(
        "\nNext: ensure RAG_ENABLED=true in backend/.env, then restart uvicorn.\n"
        "The assistant will now answer from the pages you just ingested."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
