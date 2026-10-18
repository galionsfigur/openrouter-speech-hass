"""Minimal async client for the OpenRouter REST API.

Only the few endpoints needed for speech are implemented, so the integration
stays free of third-party requirements.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
import json
from typing import Any

import aiohttp

from .const import BASE_URL, HTTP_REFERER, LOGGER, X_TITLE


class OpenRouterError(Exception):
    """Base error for the OpenRouter API."""


class OpenRouterAuthError(OpenRouterError):
    """Raised when the API key is rejected."""


class OpenRouterConnectionError(OpenRouterError):
    """Raised when OpenRouter cannot be reached."""


@dataclass(frozen=True, slots=True)
class AudioModel:
    """An OpenRouter model that can take or return audio."""

    id: str
    name: str


def _error_message(status: int, body: Any) -> str:
    """Extract a readable message from an OpenRouter error body."""
    message = "unknown error"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", error))
            raw = (error.get("metadata") or {}).get("raw")
            if raw:
                message = f"{message}: {raw}"
        elif error is not None:
            message = str(error)
    return f"OpenRouter error ({status}): {message}"


class OpenRouterClient:
    """Thin wrapper around the OpenRouter HTTP API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._api_key = api_key
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": HTTP_REFERER,
            "X-Title": X_TITLE,
        }

    async def _post_stream(
        self, path: str, *, json_body: Any, timeout: int
    ) -> aiohttp.ClientResponse:
        """Open a request and return the response, raising on HTTP errors."""
        try:
            response = await self._session.request(
                "POST",
                f"{BASE_URL}{path}",
                headers=self._headers,
                json=json_body,
                timeout=aiohttp.ClientTimeout(total=timeout),
            )
        except TimeoutError as err:
            raise OpenRouterConnectionError(
                f"Timeout after {timeout}s while talking to OpenRouter"
            ) from err
        except aiohttp.ClientError as err:
            raise OpenRouterConnectionError(f"Error talking to OpenRouter: {err}") from err

        if response.status in (401, 403):
            response.release()
            raise OpenRouterAuthError("OpenRouter rejected the API key")
        if response.status >= 400:
            try:
                body = await response.json(content_type=None)
            except (aiohttp.ClientError, ValueError):
                body = None
            raise OpenRouterError(_error_message(response.status, body))
        return response

    async def _request(
        self, method: str, path: str, *, json_body: Any = None, timeout: int = 30
    ) -> dict[str, Any]:
        """Perform a request and return the decoded JSON body."""
        try:
            response = await self._session.request(
                method,
                f"{BASE_URL}{path}",
                headers=self._headers,
                json=json_body,
                timeout=aiohttp.ClientTimeout(total=timeout),
            )
        except TimeoutError as err:
            raise OpenRouterConnectionError(
                f"Timeout after {timeout}s while talking to OpenRouter"
            ) from err
        except aiohttp.ClientError as err:
            raise OpenRouterConnectionError(f"Error talking to OpenRouter: {err}") from err

        if response.status in (401, 403):
            raise OpenRouterAuthError("OpenRouter rejected the API key")

        try:
            body = await response.json(content_type=None)
        except (aiohttp.ClientError, ValueError, asyncio.TimeoutError) as err:
            raise OpenRouterError("OpenRouter returned a non-JSON response") from err

        if response.status >= 400 or (isinstance(body, dict) and body.get("error")):
            raise OpenRouterError(_error_message(response.status, body))

        if not isinstance(body, dict):
            raise OpenRouterError("Unexpected response from OpenRouter")

        return body

    async def async_verify_key(self) -> str:
        """Validate the API key and return a label for the config entry."""
        body = await self._request("GET", "/key")
        data = body.get("data") or {}
        label = data.get("label")
        return str(label) if label else "OpenRouter"

    async def async_get_audio_models(self, direction: str) -> list[AudioModel]:
        """Return models with audio in their input or output modalities.

        ``direction`` is ``"input"`` or ``"output"``.
        """
        body = await self._request("GET", "/models")
        models: list[AudioModel] = []
        for raw in body.get("data") or []:
            if not isinstance(raw, dict):
                continue
            architecture = raw.get("architecture") or {}
            modalities = architecture.get(f"{direction}_modalities") or []
            if "audio" not in modalities:
                continue
            if direction == "output" and (
                "text" not in (architecture.get("input_modalities") or [])
                or "lyria" in str(raw.get("id", ""))
            ):
                # Lyria generates music, not speech.
                continue
            model_id = raw.get("id")
            if not model_id:
                continue
            models.append(
                AudioModel(id=str(model_id), name=str(raw.get("name") or model_id))
            )
        models.sort(key=lambda model: model.name.lower())
        LOGGER.debug("Found %s models with audio %s", len(models), direction)
        return models

    async def async_transcribe(
        self,
        *,
        model: str,
        wav: bytes,
        system_prompt: str,
        hint: str,
        timeout: int,
    ) -> str:
        """Send a WAV recording to an audio capable chat model and return text."""
        user_text = "Transcribe this recording."
        if hint:
            user_text += f" Context that may help with spelling: {hint}"
        payload = {
            "model": model,
            "temperature": 0,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(wav).decode("ascii"),
                                "format": "wav",
                            },
                        },
                    ],
                },
            ],
        }
        body = await self._request(
            "POST", "/chat/completions", json_body=payload, timeout=timeout
        )
        try:
            content = body["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as err:
            raise OpenRouterError("Unexpected transcription response") from err
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        return str(content)

    async def async_speak(
        self,
        *,
        model: str,
        text: str,
        voice: str,
        system_prompt: str,
        timeout: int,
    ) -> bytes:
        """Return raw 16 bit PCM audio for ``text``.

        Audio output on OpenRouter only works with streaming and pcm16.
        """
        payload = {
            "model": model,
            "modalities": ["text", "audio"],
            "audio": {"voice": voice, "format": "pcm16"},
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"<text>{text}</text>"},
            ],
        }
        response = await self._post_stream(
            "/chat/completions", json_body=payload, timeout=timeout
        )
        chunks: list[bytes] = []
        try:
            async for raw_line in response.content:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except ValueError:
                    continue
                if event.get("error"):
                    raise OpenRouterError(_error_message(200, event))
                for choice in event.get("choices") or []:
                    audio = (choice.get("delta") or {}).get("audio") or {}
                    if audio.get("data"):
                        try:
                            chunks.append(base64.b64decode(audio["data"]))
                        except (binascii.Error, ValueError) as err:
                            raise OpenRouterError("Invalid audio chunk") from err
        except TimeoutError as err:
            raise OpenRouterConnectionError(
                f"Timeout after {timeout}s while receiving audio"
            ) from err
        except aiohttp.ClientError as err:
            raise OpenRouterConnectionError(f"Error receiving audio: {err}") from err
        finally:
            response.release()
        return b"".join(chunks)
