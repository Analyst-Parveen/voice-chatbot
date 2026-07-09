"""Extract website content into RAG-ready Markdown.

Paste one or more URLs and get structured Markdown files with YAML frontmatter
(title, source URL, description, etc.) — ready to drop into ``data/`` and ingest
later via ``python -m ingestion.run_ingestion``.

Requires the optional ingest extras::

    pip install -e ".[ingest]"

Example::

    from ingestion.website_extractor import extract_website, save_extracted

    page = extract_website("https://example.com/about")
    print(page.markdown)
    path = save_extracted(page)   # -> data/extracted/example_com_about.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "extracted"
_USER_AGENT = "voice-ai-extractor/1.0 (+https://github.com/voice-agent)"


@dataclass
class ExtractedPage:
    """One page extracted from a website, formatted for RAG ingestion."""

    url: str
    title: str
    markdown: str
    meta: dict = field(default_factory=dict)

    @property
    def rag_text(self) -> str:
        """Full document: YAML frontmatter + Markdown body."""
        return format_rag_markdown(self)


def format_rag_markdown(page: ExtractedPage) -> str:
    """Build a Markdown file with YAML frontmatter (best format for RAG)."""
    lines = ["---"]
    lines.append(f"source_url: {page.url}")
    lines.append(f"title: {_yaml_quote(page.title)}")
    lines.append(f"extracted_at: {page.meta.get('extracted_at', '')}")

    for key in ("description", "author", "sitename", "language", "hostname", "source_type"):
        value = page.meta.get(key)
        if value:
            lines.append(f"{key}: {_yaml_quote(str(value))}")

    doc_type = page.meta.get("source_type") or page.meta.get("type") or "web"
    lines.append(f"type: {doc_type}")
    lines.append("---")
    lines.append("")

    body = page.markdown.strip()
    if body:
        lines.append(body)
    else:
        lines.append(f"# {page.title}")
        lines.append("")
        lines.append("_No main content could be extracted from this page._")

    return "\n".join(lines).strip() + "\n"


def extract_website(url: str, *, timeout: float = 20.0) -> ExtractedPage:
    """Fetch a single URL and return RAG-ready Markdown.

    Uses *trafilatura* for main-content extraction (removes nav, ads, footers).
    Falls back to BeautifulSoup when trafilatura returns nothing.
    LinkedIn company URLs are routed to :mod:`ingestion.linkedin_extractor`.
    """
    url = url.strip()
    if not url:
        raise ValueError("URL must not be empty.")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    from ingestion.linkedin_extractor import extract_linkedin_company, is_linkedin_url

    if is_linkedin_url(url):
        return extract_linkedin_company(url, timeout=timeout)

    html, final_url = _fetch_html(url, timeout=timeout)
    title, description, author, sitename, language, hostname, body_md = _extract_content(
        html, url=final_url
    )

    extracted_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    meta = {
        "extracted_at": extracted_at,
        "description": description,
        "author": author,
        "sitename": sitename,
        "language": language,
        "hostname": hostname,
    }

    page = ExtractedPage(url=final_url, title=title, markdown=body_md, meta=meta)
    return page


def extract_websites(urls: list[str], *, timeout: float = 20.0) -> list[ExtractedPage]:
    """Extract multiple URLs. Skips blanks; raises on the first hard failure."""
    pages: list[ExtractedPage] = []
    for raw in urls:
        url = raw.strip()
        if not url or url.startswith("#"):
            continue
        pages.append(extract_website(url, timeout=timeout))
    return pages


def save_extracted(
    page: ExtractedPage,
    output_dir: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Write an extracted page to ``data/extracted/<slug>.md`` (by default)."""
    out = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    path = out / _url_to_filename(page.url)
    if path.exists() and not overwrite:
        stem = path.stem
        suffix = path.suffix
        n = 2
        while path.exists():
            path = out / f"{stem}_{n}{suffix}"
            n += 1

    path.write_text(page.rag_text, encoding="utf-8")
    return path


def save_all_extracted(
    pages: list[ExtractedPage],
    output_dir: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Save multiple extracted pages."""
    return [save_extracted(p, output_dir, overwrite=overwrite) for p in pages]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _yaml_quote(value: str) -> str:
    if not value:
        return '""'
    if re.search(r'[:#\[\]{}|>&*!?,\\"\']', value) or value.strip() != value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "").replace(".", "_")
    path = parsed.path.strip("/").replace("/", "_") or "index"
    name = f"{host}_{path}" if path != "index" else host
    name = re.sub(r"[^\w\-]", "_", name)
    return f"{name[:120]}.md"


def _fetch_html(url: str, *, timeout: float) -> tuple[str, str]:
    try:
        import trafilatura
    except ImportError as exc:
        raise RuntimeError(
            'Website extraction needs trafilatura. Install with: pip install -e ".[ingest]"'
        ) from exc

    downloaded = trafilatura.fetch_url(url, no_ssl=False)
    if downloaded:
        return downloaded, url

    # trafilatura.fetch_url can fail on some hosts; fall back to requests.
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError(
            'Fallback fetch needs requests. Install with: pip install -e ".[ingest]"'
        ) from exc

    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": _USER_AGENT},
        allow_redirects=True,
    )
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text, str(resp.url)


def _extract_content(html: str, *, url: str) -> tuple[str, str, str, str, str, str, str]:
    """Return (title, description, author, sitename, language, hostname, markdown)."""
    try:
        import trafilatura
    except ImportError as exc:
        raise RuntimeError(
            'Website extraction needs trafilatura. Install with: pip install -e ".[ingest]"'
        ) from exc

    metadata = trafilatura.extract_metadata(html, default_url=url)
    title = (metadata.title if metadata and metadata.title else "") or _title_from_url(url)
    description = metadata.description if metadata and metadata.description else ""
    author = metadata.author if metadata and metadata.author else ""
    sitename = metadata.sitename if metadata and metadata.sitename else ""
    language = metadata.language if metadata and metadata.language else ""
    hostname = urlparse(url).netloc

    body_md = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_links=False,
        include_tables=True,
        include_formatting=True,
        favor_precision=True,
    )

    if body_md and body_md.strip():
        return title, description, author, sitename, language, hostname, body_md.strip()

    # Fallback: strip boilerplate tags and flatten to plain text sections.
    body_md = _fallback_extract(html, title=title)
    return title, description, author, sitename, language, hostname, body_md


def _fallback_extract(html: str, *, title: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError(
            'Fallback extraction needs beautifulsoup4. Install with: pip install -e ".[ingest]"'
        ) from exc

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "aside"]):
        tag.decompose()

    parts: list[str] = [f"# {title}", ""]
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        level = int(heading.name[1])
        text = heading.get_text(" ", strip=True)
        if text:
            parts.append(f"{'#' * level} {text}")
            parts.append("")

    main = soup.find("main") or soup.find("article") or soup.body
    if main:
        for para in main.find_all("p"):
            text = para.get_text(" ", strip=True)
            if len(text) > 40:
                parts.append(text)
                parts.append("")

    if len(parts) <= 2:
        text = soup.get_text("\n", strip=True)
        parts.extend(line for line in text.splitlines() if line.strip())

    return "\n".join(parts).strip()


def _title_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return urlparse(url).netloc
    slug = path.split("/")[-1].replace("-", " ").replace("_", " ")
    return slug.title() or urlparse(url).netloc
