"""Config flow for the NGBS Icon integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_ID, CONF_SCAN_INTERVAL

from .const import DOMAIN
from .icon import (
    IconApiConnectionError,
    IconClient,
    IconApiClientError
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_POLLING_INTERVAL = 60

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_ID): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_POLLING_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=30)
        ),
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the NGBS Icon integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the configuration flow."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ID])
            host, system_id = (
                user_input[CONF_IP_ADDRESS],
                user_input[CONF_ID],
            )
            

            try:
                api = IconClient(host, system_id)
                await api.async_get_data()
                

            except IconApiClientError:
                errors["base"] = "invalid_id"
            except IconApiConnectionError:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title="NGBS iCON", data=user_input)
            
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add reconfigure step to allow to reconfigure a config entry."""
        if user_input is not None:
            errors = {}
            await self.async_set_unique_id(user_input[CONF_ID])
            self._abort_if_unique_id_mismatch()
            host, system_id = (
                user_input[CONF_IP_ADDRESS],
                user_input[CONF_ID],
            )
            
            try:
                api = IconClient(host, system_id)
                await api.async_get_data()

            except IconApiClientError:
                errors["base"] = "invalid_id"
            except IconApiConnectionError:
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure", data_schema=STEP_USER_DATA_SCHEMA
        )