"""Speech-to-text via faster-whisper.

Runs locally on CPU (int8) or GPU. The model is loaded once; transcription runs
in a worker thread so the event loop is never blocked. Accepts the raw audio
bytes captured by the browser (WebM/Opus, WAV, etc.) — faster-whisper decodes
them via its bundled ffmpeg/av backend.
"""

from __future__ import annotations

import asyncio
import io

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.dto import STTResult

logger = get_logger(__name__)


class WhisperSTTService:
    def __init__(self, settings: Settings) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                'faster-whisper is not installed. Install voice support with: '
                'pip install -e ".[voice]" — or use RUN_MODE=stub for a fake STT.'
            ) from exc
        device = settings.whisper_device
        compute_type = "float16" if device == "cuda" else "int8"
        logger.info("Loading Whisper model '%s' on %s (first run downloads weights)…",
                    settings.whisper_model, device)
        self._model = WhisperModel(settings.whisper_model, device=device, compute_type=compute_type)

    def _transcribe(self, audio: bytes, language: str | None) -> STTResult:
        if len(audio) < 1000:
            return STTResult(text="", language=language)
        initial_prompt = None
        if language == "hi":
            initial_prompt = "नमस्ते, मैं हिंदी में बात कर रहा हूं।"
        elif language == "en":
            initial_prompt = "Hello, I am speaking in English."
        segments, info = self._model.transcribe(
            io.BytesIO(audio),
            language=language,
            vad_filter=True,
            beam_size=5,
            best_of=3,
            temperature=0.0,
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
        )
        text = "".join(seg.text for seg in segments).strip()
        return STTResult(text=text, language=getattr(info, "language", language))

    async def transcribe(self, audio: bytes, language: str | None = None) -> STTResult:
        return await asyncio.to_thread(self._transcribe, audio, language)
