"""The BiaControl integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .biactrl import get_devices
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.COVER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]

    coordinator = BiaCtrlDataUpdateCoordinator(hass, host)
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


class BiaCtrlDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator class."""

    def __init__(self, hass: HomeAssistant, host) -> None:
        """Initialize."""
        self._hass = hass
        self._host = host
        self._devices: list[dict[str, Any]] | None = None
        update_interval = timedelta(seconds=5)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        result = await get_devices(
            self._host, aiohttp_client.async_get_clientsession(self._hass)
        )
        if result:
            self._devices = result
        else:
            raise UpdateFailed()

        return self._devices
