"""The iCON integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_ID, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import IconDataUpdateCoordinator
from .icon import IconClient

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iCON from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = IconClient(entry.data[CONF_IP_ADDRESS], entry.data[CONF_ID])

    coordinator = IconDataUpdateCoordinator(hass, api, entry.data)
    await coordinator.async_config_entry_first_refresh()
    api.set_coordinator(coordinator)

    entry.async_on_unload(entry.add_update_listener(update_listener))
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the supported platforms (entities)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update for the config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok