"""User preference endpoints — persist widget theme / language / voice settings."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import DbSession
from app.schemas.preferences import PreferencesResponse, PreferencesUpsertRequest
from app.services.telemetry_service import TelemetryService

router = APIRouter(tags=["preferences"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.put(
    "/preferences",
    response_model=PreferencesResponse,
    summary="Save or update user UI/voice preferences",
)
async def upsert_preferences(
    payload: PreferencesUpsertRequest,
    db: DbSession,
    request: Request,
) -> PreferencesResponse:
    pref = await TelemetryService(db).upsert_user_preferences(
        user_ref=payload.user_ref,
        theme=payload.theme,
        language=payload.language,
        voice_enabled=payload.voice_enabled,
        tts_voice=payload.tts_voice,
        client_ip=_client_ip(request),
    )
    return PreferencesResponse(
        user_ref=pref.user_ref,
        theme=pref.theme,
        voice_enabled=pref.voice_enabled,
        tts_voice=pref.tts_voice,
        language=pref.language,
        updated_at=pref.updated_at,
    )
