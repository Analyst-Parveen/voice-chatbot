"""Helpdesk wizard REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.helpdesk import (
    HelpdeskRespondRequest,
    HelpdeskRespondResponse,
    HelpdeskStartResponse,
)
from app.services.helpdesk_api_client import submit_to_external_api
from app.services.helpdesk_flow import helpdesk_service

router = APIRouter(tags=["helpdesk"])


@router.post(
    "/helpdesk/start",
    response_model=HelpdeskStartResponse,
    summary="Start a helpdesk wizard session",
)
async def start_helpdesk() -> HelpdeskStartResponse:
    session, step = await helpdesk_service.start()
    return HelpdeskStartResponse(session_id=session.session_id, step=step)


@router.post(
    "/helpdesk/respond",
    response_model=HelpdeskRespondResponse,
    summary="Answer the current helpdesk step",
)
async def respond_helpdesk(payload: HelpdeskRespondRequest) -> HelpdeskRespondResponse:
    try:
        session, step, completed, completion_msg = await helpdesk_service.respond(
            payload.session_id, payload.answer
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Helpdesk session not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not completed:
        assert step is not None
        return HelpdeskRespondResponse(
            session_id=session.session_id,
            completed=False,
            step=step,
        )

    summary = helpdesk_service.summary(session)
    external_ref = await submit_to_external_api(summary)
    return HelpdeskRespondResponse(
        session_id=session.session_id,
        completed=True,
        step=None,
        summary=summary,
        external_ref=external_ref,
        message=completion_msg,
    )
