"""Config flow."""
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client

from .biactrl import get_devices
from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class Hub:
    """Virtual hub controller."""

    def __init__(self, hass, host):
        """Initialize a hub."""
        self._hass = hass
        self._host = host

    async def validate(self):
        """Validate connection."""
        return await get_devices(
            self._host, aiohttp_client.async_get_clientsession(self._hass)
        )


async def validate_input(hass: core.HomeAssistant, host):
    """Validate connection."""
    hub = Hub(hass, host)
    result = await hub.validate()
    if result:
        if len(result) < 1:
            raise CannotConnect


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show the setup form to the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input[CONF_HOST])
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(title="BiaCtrl", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
