"""Config flow for the NGBS Icon integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .icon import (
    CannotConnect,
    IconClient,
    InvalidIDError,
    LogoutNeededError,
    UnauthorizedError,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_POLLING_INTERVAL = 300

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
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
            session = aiohttp_client.async_create_clientsession(self.hass)
            user, password, system_id = (
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input[CONF_ID],
            )
            api = IconClient(session, user, password, system_id)

            try:
                await api.async_login()
                return self.async_create_entry(title="NGBS iCON", data=user_input)

            except InvalidIDError:
                errors["base"] = "invalid_id"
            except UnauthorizedError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except LogoutNeededError:
                errors["base"] = "logout_needed"

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
            session = aiohttp_client.async_create_clientsession(self.hass)
            user, password, xid = (
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input[CONF_ID],
            )
            api = IconClient(session, user, password, xid)

            try:
                await api.async_login()
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

            except InvalidIDError:
                errors["base"] = "invalid_id"
            except UnauthorizedError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except LogoutNeededError:
                errors["base"] = "logout_needed"

        return self.async_show_form(
            step_id="reconfigure", data_schema=STEP_USER_DATA_SCHEMA
        )
