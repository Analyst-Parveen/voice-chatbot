"""Text-to-speech via Piper.

Synthesizes a WAV clip for a piece of text using a Piper voice model. The voice
``.onnx`` (and its ``.onnx.json`` config) must live under ``models/piper/``
(downloaded by scripts/download_models.py in Phase 8). Runs in a worker thread.

TTS always speaks the EXACT text it is given — the ConversationManager feeds it
the same string that was displayed, preserving the identical-text-and-voice rule.
"""

from __future__ import annotations

import asyncio
import io
import wave
from pathlib import Path

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.hindi_speech_prep import classify_tts_script, prepare_for_hindi_tts

logger = get_logger(__name__)

_MODELS_DIR = Path(__file__).resolve().parents[3] / "models" / "piper"
_FALLBACK_VOICES = (
    "en_US-lessac-medium",
    "en_US-lessac-low",
    "en_GB-alan-medium",
)

# Piper voices: Indian English + Hindi female (clear, free, local).
_LANGUAGE_VOICES: dict[str, str] = {
    "English": "en_US-lessac-medium",
    "Hindi": "hi_IN-priyamvada-medium",
}


def resolve_voice_for_language(language: str | None, settings: Settings) -> str:
    if language == "English":
        indian = _MODELS_DIR / "en_IN-spicor-medium.onnx"
        if indian.exists():
            return "en_IN-spicor-medium"
        return _LANGUAGE_VOICES["English"]
    if language and language in _LANGUAGE_VOICES:
        return _LANGUAGE_VOICES[language]
    return settings.piper_voice


def _resolve_model_path(preferred: str) -> tuple[Path, str]:
    candidates = [preferred, *_FALLBACK_VOICES]
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        path = _MODELS_DIR / f"{name}.onnx"
        if path.exists():
            return path, name
    for path in sorted(_MODELS_DIR.glob("*.onnx")):
        return path, path.stem
    raise RuntimeError(
        f"No Piper voice found under {_MODELS_DIR}. Download with "
        "scripts/download_models.py or place a .onnx voice there."
    )


class PiperTTSService:
    def __init__(self, settings: Settings, voice: str | None = None) -> None:
        try:
            from piper import PiperVoice
        except ImportError as exc:  # pragma: no cover - optional extra
            raise RuntimeError(
                'piper-tts is not installed. Install voice support with: '
                'pip install -e ".[voice]" — or use RUN_MODE=stub for a fake TTS.'
            ) from exc

        preferred = voice or settings.piper_voice
        model_path, voice_name = _resolve_model_path(preferred)
        if voice_name != preferred:
            logger.warning(
                "Piper voice '%s' not found — using '%s'",
                preferred,
                voice_name,
            )
        logger.info("Loading Piper voice '%s'…", voice_name)
        self._voice_name = voice_name
        self._voice = PiperVoice.load(str(model_path))
        self._english_voice = None
        self._settings = settings

    def _get_english_voice(self):
        if self._english_voice is None:
            from piper import PiperVoice

            path, name = _resolve_model_path(_LANGUAGE_VOICES["English"])
            logger.info("Loading English fallback voice '%s' for mixed-language TTS", name)
            self._english_voice = PiperVoice.load(str(path))
        return self._english_voice

    def _synthesize(self, text: str, voice=None) -> bytes:
        voice = voice or self._voice
        # piper-tts >=1.3 writes a complete WAV (headers + frames) via
        # synthesize_wav; the older synthesize(text, wav) signature is gone.
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            voice.synthesize_wav(text, wav)
        return buf.getvalue()

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        speak_text = text
        voice = self._voice

        if self._voice_name.startswith("hi_IN"):
            script = classify_tts_script(text)
            if script == "english":
                # English LLM reply on Hindi mode — use English voice, not Devanagari gibberish.
                voice = self._get_english_voice()
                speak_text = text
            elif script == "hinglish":
                speak_text = prepare_for_hindi_tts(text)
            else:
                speak_text = text

        return await asyncio.to_thread(self._synthesize, speak_text, voice)
