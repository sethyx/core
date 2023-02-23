"""Config flow."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .icon import login

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_ID): str,
    }
)

_LOGGER = logging.getLogger(__name__)


class Hub:
    """Virtual hub controller."""

    def __init__(self, hass: HomeAssistant, user, password, xid) -> None:
        """Initialize a hub."""
        self._hass = hass
        self._user = user
        self._password = password
        self._id = xid

    async def authenticate(self) -> int:
        """Validate connection."""
        return await login(
            aiohttp_client.async_get_clientsession(self._hass),
            self._user,
            self._password,
            self._id,
        )


async def validate_input(hass: core.HomeAssistant, data: dict[str, Any]):
    """Validate connection."""
    hub = Hub(hass, data[CONF_EMAIL], data[CONF_PASSWORD], data[CONF_ID])
    result = await hub.authenticate()
    if result == 200:
        return True
    if result == 403:
        raise UnauthorizedError
    if result == 404:
        raise InvalidIDError
    if result == 500:
        raise CannotConnect


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Show the setup form to the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except InvalidIDError:
            errors["base"] = "invalid_id"
        except UnauthorizedError:
            errors["base"] = "invalid_auth"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(title="ngbs_icon", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class UnauthorizedError(exceptions.HomeAssistantError):
    """Error to indicate we cannot authorize."""


class InvalidIDError(exceptions.HomeAssistantError):
    """Error to indicate we cannot find a system ID."""
