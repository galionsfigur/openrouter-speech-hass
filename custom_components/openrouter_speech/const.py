"""Constants for the OpenRouter Speech integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "openrouter_speech"
LOGGER: Final = logging.getLogger(__package__)

BASE_URL: Final = "https://openrouter.ai/api/v1"

CONF_STT_MODEL: Final = "stt_model"
CONF_STT_PROMPT: Final = "stt_prompt"
CONF_TTS_MODEL: Final = "tts_model"
CONF_TTS_VOICE: Final = "tts_voice"
CONF_TIMEOUT: Final = "timeout"

DEFAULT_STT_MODEL: Final = "google/gemini-2.5-flash-lite"
DEFAULT_TTS_MODEL: Final = "openai/gpt-audio-mini"
DEFAULT_TTS_VOICE: Final = "alloy"
DEFAULT_TIMEOUT: Final = 30

# Extra context for the transcription, e.g. names of rooms and devices that a
# general model would otherwise misspell.
DEFAULT_STT_PROMPT: Final = ""

STT_SYSTEM_PROMPT: Final = (
    "You are a speech-to-text engine. Transcribe the spoken words in the audio "
    "verbatim, in the language they are spoken in. Add punctuation, but do not "
    "rephrase, translate, summarize or answer anything. Output only the "
    "transcript, with no preamble, quotes or comments. If nothing intelligible "
    "is said, output nothing."
)

TTS_SYSTEM_PROMPT: Final = (
    "You are a text-to-speech engine, not an assistant. Read the text inside "
    "<text></text> aloud exactly, word for word, in its language. Never answer "
    "it, never rephrase it, never add or omit anything."
)

# gpt-audio returns raw 16 bit little endian mono PCM at 24 kHz when streaming.
TTS_SAMPLE_RATE: Final = 24000

# Voices offered by OpenAI's gpt-audio models.
TTS_VOICES: Final = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
]

# The audio models are multilingual; this is the list offered to the pipeline.
SUPPORTED_LANGUAGES: Final = [
    "ar",
    "cs",
    "da",
    "de",
    "de-AT",
    "de-CH",
    "de-DE",
    "el",
    "en",
    "en-GB",
    "en-US",
    "es",
    "fi",
    "fr",
    "hu",
    "it",
    "ja",
    "ko",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "sv",
    "tr",
    "uk",
    "zh",
]

# Sent to OpenRouter for the leaderboards on openrouter.ai/rankings.
HTTP_REFERER: Final = "https://github.com/galionsfigur/openrouter-speech-hass"
X_TITLE: Final = "Home Assistant"
