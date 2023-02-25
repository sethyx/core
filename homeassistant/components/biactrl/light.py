"""Light module."""
from __future__ import annotations

from asyncio import sleep
import logging
from typing import Any

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BiaCtrlDataUpdateCoordinator
from .biactrl import control_device
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DELAY_BEFORE_UPDATE = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Async setup entry."""
    host: str = entry.data[CONF_HOST]
    coordinator: BiaCtrlDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, host, device, coordinator)
        for device in coordinator.data
        if device["type"] == "light"
    )


class Device(CoordinatorEntity[BiaCtrlDataUpdateCoordinator], LightEntity):
    """Light device class."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        device: dict[str, Any],
        coordinator: BiaCtrlDataUpdateCoordinator,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._host = host
        self._attr_name = device["name"]
        self._attr_unique_id = device["id"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["id"])},
            manufacturer="BiaHome",
            model=device["type"],
            name=self.name,
        )
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["id"] == self._attr_unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            self._attr_is_on = state == "on"
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        _LOGGER.info("In light/async_added_to_hass")
        self._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async function to set on to light."""
        await control_device(
            self._session, self._host, "light", self._attr_unique_id, "on"
        )
        await sleep(DELAY_BEFORE_UPDATE)
        _LOGGER.info("In light turn on")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Async function to set off to light."""
        await control_device(
            self._session, self._host, "light", self._attr_unique_id, "off"
        )
        _LOGGER.info("In light turn off")
        await sleep(DELAY_BEFORE_UPDATE)
        await self.coordinator.async_request_refresh()
