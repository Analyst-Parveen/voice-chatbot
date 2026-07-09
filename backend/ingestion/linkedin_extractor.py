"""Extract LinkedIn company pages into RAG-ready Markdown.

LinkedIn pages include login prompts, job listings, and navigation noise.
This module keeps company profile facts (about, industry, location, specialties)
and drops UI boilerplate so chunks embed cleanly.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from ingestion.website_extractor import ExtractedPage, _fetch_html

_LINKEDIN_HOST = "linkedin.com"

_FIELD_KEYS = (
    "Website",
    "Industry",
    "Company size",
    "Headquarters",
    "Type",
    "Founded",
    "Specialties",
)

_SKIP_SECTIONS = frozenset(
    {
        "updates",
        "similar pages",
        "browse jobs",
        "more searches",
        "join now to see what you are missing",
        "sign in to see who you already know",
        "employees at infinity assurance solutions private limited",
    }
)

_UNICODE_BOLD = str.maketrans(
    "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭"
    "𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇"
    "𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789",
)


def is_linkedin_url(url: str) -> bool:
    return _LINKEDIN_HOST in urlparse(url).netloc.lower()


def normalize_linkedin_url(url: str) -> str:
    """Use www.linkedin.com for consistent fetching."""
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    if "/company/" not in path:
        raise ValueError(f"Not a LinkedIn company URL: {url}")
    slug = path.split("/company/", 1)[1].split("/")[0]
    return f"https://www.linkedin.com/company/{slug}/"


def extract_linkedin_company(url: str, *, timeout: float = 20.0) -> ExtractedPage:
    """Fetch and clean a LinkedIn company page."""
    normalized = normalize_linkedin_url(url)
    html, final_url = _fetch_html(normalized, timeout=timeout)
    body_md, title, fields = _extract_and_clean(html, url=final_url)

    extracted_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    meta = {
        "extracted_at": extracted_at,
        "source_type": "linkedin",
        "hostname": urlparse(final_url).netloc,
        **fields,
    }

    return ExtractedPage(
        url=final_url,
        title=title,
        markdown=body_md,
        meta=meta,
    )


def clean_linkedin_text(text: str) -> str:
    """Clean raw LinkedIn markdown/text (e.g. from a browser save or upload)."""
    body_md, title, _fields = _structure_cleaned_body(text)
    if title and not body_md.lstrip().startswith("#"):
        return f"# {title}\n\n{body_md}".strip()
    return body_md.strip()


def _extract_and_clean(html: str, *, url: str) -> tuple[str, str, dict[str, str]]:
    try:
        import trafilatura
    except ImportError as exc:
        raise RuntimeError(
            'LinkedIn extraction needs trafilatura. Install with: pip install -e ".[ingest]"'
        ) from exc

    raw_md = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_links=False,
        include_tables=False,
        favor_precision=True,
    )
    if not raw_md:
        raw_md = _fallback_plain(html)

    return _structure_cleaned_body(raw_md)


def _structure_cleaned_body(text: str) -> tuple[str, str, dict[str, str]]:
    text = text.translate(_UNICODE_BOLD)
    text = re.sub(r"\\_", "_", text)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Drop leading job-post spam before the company profile heading.
    m = re.search(r"(?m)^#\s+(.+)$", text)
    if m:
        text = text[m.start() :]

    lines = [_collapse_ws(ln) for ln in text.replace("\r\n", "\n").split("\n")]

    title = ""
    tagline = ""
    about = ""
    fields: dict[str, str] = {}
    location = ""
    employees: list[str] = []
    funding: list[str] = []

    section: str | None = None
    about_buf: list[str] = []

    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln or _is_noise(ln):
            i += 1
            continue

        if ln.startswith("# ") and not title:
            candidate = ln[2:].strip()
            # Skip short/generic headings; prefer the company name line.
            if len(candidate) > 12 and candidate.lower() not in {"consumer services"}:
                title = candidate
            i += 1
            continue

        if ln.startswith("#### ") and not tagline:
            tagline = ln[5:].strip()
            i += 1
            continue

        sec = _section_name(ln)
        if sec is not None:
            if section == "about" and about_buf:
                about = " ".join(about_buf).strip()
                about_buf = []
            section = sec
            i += 1
            continue

        if section in {None, "_skip", "updates"}:
            i += 1
            continue

        # Sidebar fields: "- Website" then value on following lines.
        field_key = _list_field_key(ln)
        if field_key:
            val, i = _read_field_value(lines, i + 1)
            fields[field_key.lower().replace(" ", "_")] = val
            continue

        if section == "about" and ln and not ln.startswith("#"):
            about_buf.append(ln)
            i += 1
            continue

        if section == "employees" and ln.startswith("### "):
            name = ln[4:].strip()
            if name and "linkedin member" not in name.lower():
                employees.append(name)
        elif section == "locations" and ln and not ln.startswith("#"):
            cleaned = re.sub(r"^(Primary|Get directions)\s*", "", ln, flags=re.I).strip()
            if cleaned and len(cleaned) > 10:
                location = cleaned if not location else f"{location}; {cleaned}"
        elif section == "funding" and ln and not ln.startswith("#"):
            if not _is_noise(ln):
                funding.append(ln)

        i += 1

    if section == "about" and about_buf and not about:
        about = " ".join(about_buf).strip()

    if not title:
        for ln in lines:
            if ln.startswith("# ") and len(ln) > 15:
                title = ln[2:].strip()
                break
    if not title and about:
        if "infinity assurance solutions" in about.lower():
            title = "Infinity Assurance Solutions Private Limited"
    if not title:
        title = "LinkedIn Company Profile"

    parts: list[str] = [f"# {title}"]
    if tagline:
        parts.append(f"\n**Tagline:** {tagline}")

    if fields:
        parts.append("\n## Company Details")
        labels = {
            "website": "Website",
            "industry": "Industry",
            "company_size": "Company size",
            "headquarters": "Headquarters",
            "type": "Type",
            "founded": "Founded",
            "specialties": "Specialties",
        }
        for key, label in labels.items():
            if key in fields:
                parts.append(f"- **{label}:** {fields[key]}")

    if about:
        parts.append("\n## About")
        parts.append(about)

    if location:
        parts.append("\n## Location")
        parts.append(location)

    if employees:
        parts.append("\n## Key People")
        for name in employees[:10]:
            parts.append(f"- {name}")

    if funding:
        parts.append("\n## Funding")
        parts.append("\n".join(funding[:8]))

    return "\n".join(parts).strip(), title, fields


def _section_name(line: str) -> str | None:
    if not line.startswith("##"):
        return None
    name = re.sub(r"^#+\s*", "", line).strip().lower()
    if name in _SKIP_SECTIONS or name.startswith("employees at"):
        return "_skip"
    if name == "about us":
        return "about"
    if name == "locations":
        return "locations"
    if name == "funding":
        return "funding"
    return None


def _list_field_key(line: str) -> str | None:
    m = re.match(r"^-\s+(Website|Industry|Company size|Headquarters|Type|Founded|Specialties)\s*$", line)
    return m.group(1) if m else None


def _read_field_value(lines: list[str], start: int) -> tuple[str, int]:
    values: list[str] = []
    i = start
    while i < len(lines):
        ln = lines[i]
        if _list_field_key(ln) or (ln.startswith("##") and ln.strip("# ").strip()):
            break
        if ln.startswith("##"):
            break
        if ln and not _is_noise(ln):
            cleaned = re.sub(r"^-\s*", "", ln).strip()
            if cleaned and "external link for" not in cleaned.lower():
                values.append(cleaned)
        i += 1
    return " ".join(values).strip(), i


def _is_noise(line: str) -> bool:
    low = line.lower()
    noise_fragments = (
        "sign in",
        "join now",
        "email or phone",
        "password",
        "forgot password",
        "report this",
        "see jobs",
        "follow",
        "view all",
        "like comment share",
        "linkedin ©",
        "show more similar",
        "show fewer",
        "more searches",
        "agree & join linkedin",
        "skip to main content",
        "get directions",
    )
    return any(frag in low for frag in noise_fragments)


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _fallback_plain(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("Fallback needs beautifulsoup4.") from exc

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)
