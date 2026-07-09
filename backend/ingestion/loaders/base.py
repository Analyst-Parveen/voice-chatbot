"""Loader primitives shared by all source loaders."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Document:
    """A single loaded source document before cleaning/chunking.

    ``source`` uniquely identifies the origin (file path or URL) and is the key
    used for incremental re-indexing and deletion.
    """

    text: str
    source: str
    type: str  # "text" | "faq" | "pdf" | "docx" | "web" | "sql"
    url: str | None = None
    meta: dict = field(default_factory=dict)
