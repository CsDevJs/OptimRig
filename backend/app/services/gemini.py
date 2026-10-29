"""Minimal client for Google's Gemini generateContent REST API.

The API key stays on the server (GEMINI_API_KEY in .env); browsers only talk to
our /ai endpoints, never to Google directly.
"""

import httpx

from app.config import settings

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AiNotConfigured(RuntimeError):
    """GEMINI_API_KEY is not set."""


class AiUnavailable(RuntimeError):
    """Gemini could not be reached or returned no text."""


def generate(system: str, prompt: str, *, client: httpx.Client | None = None) -> str:
    if not settings.gemini_api_key:
        raise AiNotConfigured("GEMINI_API_KEY is not set")
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    own_client = client is None
    client = client or httpx.Client(timeout=45)
    try:
        response = client.post(
            API_URL.format(model=settings.gemini_model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=payload,
        )
    except httpx.HTTPError as error:
        raise AiUnavailable(f"network error: {error.__class__.__name__}") from error
    finally:
        if own_client:
            client.close()
    if response.status_code != 200:
        raise AiUnavailable(f"Gemini returned HTTP {response.status_code}")
    try:
        parts = response.json()["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise AiUnavailable("Gemini returned an unexpected response") from error
    if not text:
        raise AiUnavailable("Gemini returned no text")
    return text
