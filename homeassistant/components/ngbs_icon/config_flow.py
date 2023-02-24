"""Config flow."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .icon import (
    CannotConnect,
    IconClient,
    InvalidIDError,
    LogoutNeededError,
    UnauthorizedError,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_ID): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api: IconClient
        self.user: str | None = None
        self.password: str | None = None
        self.xid: str | None = None

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Show the setup form to the user."""

        session = aiohttp_client.async_create_clientsession(self.hass)

        errors = {}

        if user_input is not None:
            self.user = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]
            self.xid = user_input[CONF_ID]

            try:
                self.api = IconClient(session, self.user, self.password, self.xid)
                await self.api.login()
            except InvalidIDError:
                errors["base"] = "invalid_id"
            except UnauthorizedError:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except LogoutNeededError:
                errors["base"] = "logout_needed"
            else:
                return self.async_create_entry(title="ngbs_icon", data=user_input)

            if errors["base"] in ("invalid_id", "logout_needed"):
                await self.api.logout()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
