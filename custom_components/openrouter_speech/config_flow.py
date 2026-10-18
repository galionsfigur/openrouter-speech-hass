"""Config flow for the OpenRouter Speech integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .api import AudioModel, OpenRouterAuthError, OpenRouterClient, OpenRouterError
from .const import (
    CONF_STT_MODEL,
    CONF_STT_PROMPT,
    CONF_TIMEOUT,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
    DEFAULT_STT_MODEL,
    DEFAULT_STT_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    DOMAIN,
    LOGGER,
    TTS_VOICES,
)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): TextSelector()})

DEFAULT_OPTIONS: dict[str, Any] = {
    CONF_STT_MODEL: DEFAULT_STT_MODEL,
    CONF_STT_PROMPT: DEFAULT_STT_PROMPT,
    CONF_TTS_MODEL: DEFAULT_TTS_MODEL,
    CONF_TTS_VOICE: DEFAULT_TTS_VOICE,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
}


class OpenRouterSpeechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRouter Speech."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return OpenRouterSpeechOptionsFlow()

    async def _async_validate(self, api_key: str) -> tuple[str | None, str | None]:
        """Return (label, error_key)."""
        client = OpenRouterClient(api_key, async_get_clientsession(self.hass))
        try:
            label = await client.async_verify_key()
        except OpenRouterAuthError:
            return None, "invalid_auth"
        except OpenRouterError:
            return None, "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception while validating the API key")
            return None, "unknown"
        return label, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            label, error = await self._async_validate(user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=label or "OpenRouter Speech",
                    data=user_input,
                    options=DEFAULT_OPTIONS,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _, error = await self._async_validate(user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_SCHEMA, errors=errors
        )


def _model_selector(models: list[AudioModel]) -> SelectSelector:
    """Build a dropdown of models that still accepts a typed model id."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=model.id, label=f"{model.name} ({model.id})")
                for model in models
            ],
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=True,
            sort=True,
        )
    )


class OpenRouterSpeechOptionsFlow(OptionsFlow):
    """Choose the models and voice."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            user_input[CONF_TIMEOUT] = int(user_input[CONF_TIMEOUT])
            return self.async_create_entry(data=user_input)

        client: OpenRouterClient = self.config_entry.runtime_data
        try:
            stt_models = await client.async_get_audio_models("input")
            tts_models = await client.async_get_audio_models("output")
        except OpenRouterAuthError:
            return self.async_abort(reason="invalid_auth")
        except OpenRouterError:
            return self.async_abort(reason="cannot_connect")

        options = {**DEFAULT_OPTIONS, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STT_MODEL, default=options[CONF_STT_MODEL]
                    ): _model_selector(stt_models),
                    vol.Optional(
                        CONF_STT_PROMPT,
                        description={"suggested_value": options[CONF_STT_PROMPT]},
                    ): TextSelector(TextSelectorConfig(multiline=True)),
                    vol.Required(
                        CONF_TTS_MODEL, default=options[CONF_TTS_MODEL]
                    ): _model_selector(tts_models),
                    vol.Required(
                        CONF_TTS_VOICE, default=options[CONF_TTS_VOICE]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=TTS_VOICES,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                    vol.Required(
                        CONF_TIMEOUT, default=options[CONF_TIMEOUT]
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=5, max=120, step=5, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )
