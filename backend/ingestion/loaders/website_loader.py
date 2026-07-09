"""Website loader (lazy requests + BeautifulSoup)."""

from __future__ import annotations

from ingestion.loaders.base import Document


def load_website(url: str, timeout: float = 15.0) -> Document:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:  # pragma: no cover - optional extra
        raise RuntimeError(
            'Website loading needs requests + beautifulsoup4. '
            'Install with: pip install -e ".[ingest]"'
        ) from exc

    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "voice-ai-ingest/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    text = soup.get_text(separator="\n")
    return Document(text=text, source=url, type="web", url=url, meta={"title": title})
