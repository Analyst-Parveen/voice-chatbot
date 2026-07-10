"""Download local model assets."""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

from app.core.config import get_settings

_MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
_PIPER_DIR = _MODELS_DIR / "piper"
_PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Voices used by Ask a Query (Hindi + clear English).
_CHAT_VOICES = (
    "hi_IN-priyamvada-medium",
    "en_US-lessac-medium",
)

# Indian English (IISc SPICOR) — optional, clearer Indian accent for English mode.
_CUSTOM_VOICES: dict[str, tuple[str, str]] = {
    "en_IN-spicor-medium": (
        "https://huggingface.co/navgurukul-ai-labs/text-to-speech-en-IN-piper/resolve/main/"
        "en_IN-dataset%3Dspicor-english-base%3Dljspeech-epochs%3D1089.onnx",
        "https://huggingface.co/navgurukul-ai-labs/text-to-speech-en-IN-piper/resolve/main/"
        "en_IN-dataset%3Dspicor-english-base%3Dljspeech-epochs%3D1089.onnx.json",
    ),
}


def _piper_urls(voice: str) -> tuple[str, str]:
    lang_region, name, quality = voice.split("-", 2)
    lang = lang_region.split("_")[0]
    onnx = f"{_PIPER_BASE}/{lang}/{lang_region}/{name}/{quality}/{voice}.onnx"
    return onnx, f"{onnx}.json"


def _download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [skip] {dest.name} already present")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [get]  {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"  [ok]   saved {dest}")


def download_piper(voice: str) -> None:
    print(f"Piper voice: {voice}")
    if voice in _CUSTOM_VOICES:
        onnx_url, json_url = _CUSTOM_VOICES[voice]
    else:
        onnx_url, json_url = _piper_urls(voice)
    _download(onnx_url, _PIPER_DIR / f"{voice}.onnx")
    _download(json_url, _PIPER_DIR / f"{voice}.onnx.json")


def warm_models(settings) -> None:
    print(f"Warming Whisper '{settings.whisper_model}'…")
    from faster_whisper import WhisperModel

    WhisperModel(settings.whisper_model, device=settings.whisper_device,
                 compute_type="int8")
    print(f"Warming embeddings '{settings.embed_model}'…")
    from sentence_transformers import SentenceTransformer

    SentenceTransformer(settings.embed_model)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download local model assets.")
    parser.add_argument("--piper", action="store_true", help="Download Piper voices.")
    parser.add_argument("--warm", action="store_true", help="Pre-cache Whisper + bge-m3.")
    args = parser.parse_args()

    settings = get_settings()
    do_piper = args.piper or not args.warm

    if do_piper:
        for voice in _CHAT_VOICES:
            try:
                download_piper(voice)
            except Exception as exc:  # noqa: BLE001
                print(f"Piper download failed ({voice}): {exc}", file=sys.stderr)
        try:
            download_piper("en_IN-spicor-medium")
        except Exception as exc:  # noqa: BLE001
            print(f"Optional Indian English voice skipped: {exc}", file=sys.stderr)
        if settings.piper_voice not in _CHAT_VOICES and settings.piper_voice not in ("", "stub"):
            try:
                download_piper(settings.piper_voice)
            except Exception as exc:  # noqa: BLE001
                print(f"Piper download failed: {exc}", file=sys.stderr)
    if args.warm:
        warm_models(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
