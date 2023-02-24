"""The iCON integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .icon import IconClient

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup entry."""
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_create_clientsession(hass)
    api = IconClient(
        session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], entry.data[CONF_ID]
    )
    await api.login()
    coordinator = IconDataUpdateCoordinator(hass, api, entry.data)
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""

    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class IconDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator class."""

    def __init__(self, hass: HomeAssistant, api: IconClient, data) -> None:
        """Initialize."""
        self.api = api
        self.hass = hass
        self.devices: list[dict[str, Any]] | None = None
        update_interval = timedelta(seconds=10)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        result = await self.api.poll_api()
        if result:
            self.devices = result
        else:
            raise UpdateFailed()

        return self.devices
