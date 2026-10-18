"""Text-to-speech platform for OpenRouter Speech."""

from __future__ import annotations

import io
from typing import Any
import wave

from homeassistant.components import tts
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenRouterSpeechConfigEntry
from .api import OpenRouterError
from .const import (
    CONF_TIMEOUT,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
    DEFAULT_TIMEOUT,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DOMAIN,
    SUPPORTED_LANGUAGES,
    TTS_SAMPLE_RATE,
    TTS_SYSTEM_PROMPT,
    TTS_VOICES,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterSpeechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the text-to-speech entity."""
    async_add_entities([OpenRouterTTSEntity(config_entry)])


class OpenRouterTTSEntity(tts.TextToSpeechEntity):
    """Speaks text with an audio output model on OpenRouter."""

    _attr_has_entity_name = True
    _attr_translation_key = "tts"
    _attr_supported_languages = SUPPORTED_LANGUAGES
    _attr_default_language = "de"
    _attr_supported_options = [tts.ATTR_VOICE]

    def __init__(self, entry: OpenRouterSpeechConfigEntry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tts"
        self._attr_default_options = {
            tts.ATTR_VOICE: entry.options.get(CONF_TTS_VOICE, DEFAULT_TTS_VOICE)
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="OpenRouter",
            entry_type=DeviceEntryType.SERVICE,
        )

    @callback
    def async_get_supported_voices(self, language: str) -> list[tts.Voice]:
        """Return the voices offered by the gpt-audio models."""
        return [tts.Voice(voice, voice.capitalize()) for voice in TTS_VOICES]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Return a WAV file with ``message`` spoken."""
        entry_options = self.entry.options
        voice = options.get(tts.ATTR_VOICE) or entry_options.get(
            CONF_TTS_VOICE, DEFAULT_TTS_VOICE
        )
        try:
            pcm = await self.entry.runtime_data.async_speak(
                model=entry_options.get(CONF_TTS_MODEL, DEFAULT_TTS_MODEL),
                text=message,
                voice=voice,
                system_prompt=TTS_SYSTEM_PROMPT,
                timeout=int(entry_options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            )
        except OpenRouterError as err:
            raise HomeAssistantError(f"OpenRouter speech failed: {err}") from err

        if not pcm:
            raise HomeAssistantError("OpenRouter returned no audio")

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(TTS_SAMPLE_RATE)
            wav_file.writeframes(pcm)
        return "wav", buffer.getvalue()
