"""ElevenLabs Scribe v2 adapter.

Backend-only multipart request. The reference transcript is never sent to the provider.
"""
from __future__ import annotations

import time
import requests

from .asr_common import ProviderError, build_model_result

ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
_LANGUAGE_CODES = {
    "ar": "ara",  # Scribe v2 documented Arabic code
    "en": "eng",  # Scribe v2 documented English code
}


def request_settings(language: str) -> dict:
    """Build the provider request without transcript hints.

    For a known single language we send the documented Scribe v2 language code.
    For Arabic+English/mixed audio, language_code is omitted so Scribe can detect
    languages itself.
    """
    data = {
        "model_id": "scribe_v2",
        "tag_audio_events": "false",
        "diarize": "false",
        "timestamps_granularity": "word",
        "no_verbatim": "false",
    }
    code = _LANGUAGE_CODES.get((language or "").strip().lower())
    if code:
        data["language_code"] = code
    return data


def _provider_message(response) -> str:
    """Return a short non-secret error message from ElevenLabs when available."""
    try:
        payload = response.json()
    except Exception:
        text = (getattr(response, "text", "") or "").strip()
        return text[:300]

    if not isinstance(payload, dict):
        return ""
    detail = payload.get("detail")
    if isinstance(detail, dict):
        for key in ("message", "status", "code"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:300]
    if isinstance(detail, str):
        return detail.strip()[:300]
    for key in ("message", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:300]
    return ""


def _http_error(response) -> ProviderError:
    status = int(response.status_code)
    base = {
        400: "ElevenLabs rejected the request.",
        401: "ElevenLabs authentication failed. Check the API key.",
        403: "ElevenLabs denied access. Check Speech-to-Text permission, IP restrictions, and account access.",
        413: "ElevenLabs rejected the file size.",
        422: "ElevenLabs rejected the audio or request settings.",
        429: "ElevenLabs rate limit or quota was reached.",
    }.get(status, f"ElevenLabs returned HTTP {status}.")
    provider = _provider_message(response)
    message = base + (f" Provider message: {provider}" if provider else "")
    return ProviderError(message, f"http_{status}")


def transcribe_elevenlabs(audio, credentials: dict, language: str, timeout=300) -> tuple[dict, dict]:
    key = credentials.get("elevenlabs_api_key", "").strip()
    if not key:
        raise ProviderError("ElevenLabs API key is not configured in the backend.", "configuration")

    data = request_settings(language)
    start = time.perf_counter()
    try:
        with audio.open("rb") as f:
            response = requests.post(
                ENDPOINT,
                headers={"xi-api-key": key},
                data=data,
                files={"file": (audio.name, f, "audio/wav")},
                timeout=(10, timeout),
                allow_redirects=False,
            )
    except requests.Timeout:
        raise ProviderError(
            "ElevenLabs timed out. The request may have been accepted; no automatic resubmission was made.",
            "timeout",
        ) from None
    except requests.RequestException as exc:
        raise ProviderError(
            f"Unable to reach ElevenLabs ({type(exc).__name__}). Check network access and TLS.",
            "network",
        ) from None

    if response.status_code != 200:
        raise _http_error(response)

    try:
        raw = response.json()
    except ValueError:
        raise ProviderError("ElevenLabs returned invalid JSON.", "response_schema") from None

    if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
        raise ProviderError("ElevenLabs returned an unexpected transcript structure.", "response_schema")

    result = build_model_result(
        "elevenlabs",
        "ElevenLabs · Scribe v2",
        raw["text"],
        settings=data,
        elapsed_ms=round((time.perf_counter() - start) * 1000),
        metadata={
            "language_code": raw.get("language_code"),
            "language_probability": raw.get("language_probability"),
            "words": raw.get("words", []),
            "response_kind": "provider_json",
        },
    )
    return result, raw
