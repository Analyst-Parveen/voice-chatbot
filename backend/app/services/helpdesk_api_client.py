"""Optional forward of completed helpdesk payloads to an external API."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("voiceai.helpdesk")


async def submit_to_external_api(payload: dict[str, Any]) -> str | None:
    """POST completed helpdesk data to HELPDESK_API_URL if configured.

    Returns an external reference id from the remote system, or a local stub ref.
    """
    settings = get_settings()
    url = settings.helpdesk_api_url
    if not url:
        return f"LOCAL-{uuid.uuid4().hex[:10].upper()}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            return (
                data.get("reference")
                or data.get("case_id")
                or data.get("id")
                or f"EXT-{uuid.uuid4().hex[:8].upper()}"
            )
    except Exception as exc:
        logger.warning("helpdesk external API failed: %s", exc)
        return f"PENDING-{uuid.uuid4().hex[:8].upper()}"
