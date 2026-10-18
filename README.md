# OpenRouter Speech for Home Assistant

Custom integration that uses OpenRouter for Assist speech: a **speech-to-text**
entity and a **text-to-speech** entity, both billed per request through your
OpenRouter key instead of a subscription.

- **Speech-to-text** sends the recorded utterance to any OpenRouter model that
  accepts audio input. The default, `google/gemini-2.5-flash-lite`, transcribes
  a short command in about one second for roughly $0.00003.
- **Text-to-speech** uses an audio output model (default `openai/gpt-audio-mini`,
  roughly $0.0004 per answer). These are chat models told to read the text
  verbatim; they almost always do, but can occasionally rephrase. Any other TTS
  engine can be combined with this STT in an Assist pipeline.

The core `open_router` integration provides the conversation agent; this
integration adds the speech parts and runs alongside it.

## Installation

### HACS

1. HACS → ⋮ → *Custom repositories*
2. Add this repository's URL, category **Integration**
3. Install *OpenRouter Speech*
4. Restart Home Assistant

### Manual

Copy `custom_components/openrouter_speech` to `<config>/custom_components/`
and restart Home Assistant.

## Setup

1. *Settings → Devices & Services → Add Integration → OpenRouter Speech*
2. Enter an API key from <https://openrouter.ai/keys>
3. *Settings → Voice assistants*: pick **OpenRouter Speech** as speech-to-text
   (and optionally as text-to-speech) in your pipeline.

The integration's *Configure* dialog offers:

| Option | Meaning |
| --- | --- |
| Speech-to-text model | Any model with audio input |
| Vocabulary hint | Names of rooms, devices or people, so they are spelled correctly |
| Text-to-speech model | A model with audio output |
| Voice | Default voice (`alloy`, `ash`, `coral`, `nova`, …) |
| Timeout | Seconds until a request is aborted |

## Notes

- Audio is sent as 16 kHz mono WAV after the speaker stops talking, so there
  is no streaming transcription.
- Text-to-speech returns 24 kHz mono WAV.
