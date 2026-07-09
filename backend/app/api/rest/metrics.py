"""Prometheus metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import Response

from app.core.metrics import CONTENT_TYPE, render

router = APIRouter()


@router.get("/metrics", include_in_schema=False, summary="Prometheus metrics")
async def metrics() -> Response:
    return Response(content=render(), media_type=CONTENT_TYPE)
