"""SQL loader — turn rows from the company database into documents.

Runs a read-only SQL query (against the existing MS SQL Server, or the SQLite
dev DB) and renders each row into a text document using a template. This lets
structured data — product catalogs, policies stored in tables — participate in
retrieval alongside PDFs and web pages.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from ingestion.loaders.base import Document


def load_sql(
    sync_url: str,
    query: str,
    *,
    source_prefix: str = "sql",
    template: str | None = None,
) -> list[Document]:
    """Execute ``query`` and map each row to a Document.

    ``template`` is a str.format template over the row's columns; when omitted,
    all columns are rendered as ``key: value`` lines.
    """
    engine = create_engine(sync_url)
    docs: list[Document] = []
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())
            for i, row in enumerate(result):
                mapping = dict(zip(columns, row))
                if template:
                    body = template.format(**mapping)
                else:
                    body = "\n".join(f"{k}: {v}" for k, v in mapping.items())
                docs.append(
                    Document(text=body, source=f"{source_prefix}#{i}", type="sql")
                )
    finally:
        engine.dispose()
    return docs
