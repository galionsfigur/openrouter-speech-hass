"""Speech-to-text platform for OpenRouter Speech."""

from __future__ import annotations

from collections.abc import AsyncIterable
import io
import re
import wave

from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenRouterSpeechConfigEntry
from .api import OpenRouterError
from .const import (
    CONF_STT_MODEL,
    CONF_STT_PROMPT,
    CONF_TIMEOUT,
    DEFAULT_STT_MODEL,
    DEFAULT_STT_PROMPT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGGER,
    STT_SYSTEM_PROMPT,
    SUPPORTED_LANGUAGES,
)

# Models like to wrap the transcript in quotes or prefix it with a label.
_PREFIX = re.compile(r"^(transcript(ion)?|transkript(ion)?|text)\s*[:.-]\s*", re.I)
_QUOTES = "\"'„“”«»"


def _clean(text: str) -> str:
    """Strip labels and quotes that models add around a transcript."""
    text = _PREFIX.sub("", text.strip())
    if len(text) > 2 and text[0] in _QUOTES and text[-1] in _QUOTES:
        text = text[1:-1].strip()
    return " ".join(text.split())


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterSpeechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the speech-to-text entity."""
    async_add_entities([OpenRouterSTTEntity(config_entry)])


class OpenRouterSTTEntity(stt.SpeechToTextEntity):
    """Transcribes audio with an audio capable OpenRouter chat model."""

    _attr_has_entity_name = True
    _attr_translation_key = "stt"

    def __init__(self, entry: OpenRouterSpeechConfigEntry) -> None:
        """Initialize the entity."""
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_stt"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="OpenRouter",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bit rates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Collect the whole utterance, then transcribe it in one request."""
        pcm = bytearray()
        async for chunk in stream:
            pcm.extend(chunk)

        if not pcm:
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(metadata.channel.value)
            wav_file.setsampwidth(metadata.bit_rate.value // 8)
            wav_file.setframerate(metadata.sample_rate.value)
            wav_file.writeframes(bytes(pcm))

        options = self.entry.options
        try:
            text = await self.entry.runtime_data.async_transcribe(
                model=options.get(CONF_STT_MODEL, DEFAULT_STT_MODEL),
                wav=buffer.getvalue(),
                system_prompt=STT_SYSTEM_PROMPT,
                hint=options.get(CONF_STT_PROMPT, DEFAULT_STT_PROMPT),
                timeout=int(options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            )
        except OpenRouterError as err:
            LOGGER.error("Transcription failed: %s", err)
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        text = _clean(text)
        LOGGER.debug("Transcript (%s bytes of audio): %s", len(pcm), text)
        if not text:
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
        return stt.SpeechResult(text, stt.SpeechResultState.SUCCESS)
