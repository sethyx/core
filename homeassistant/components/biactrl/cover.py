"""Cover module."""
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
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

DEVICE_CLASS_MAP = {"cover": CoverDeviceClass.SHUTTER}

SUPPORTED_SENSORS = {"cover"}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Async setup entry."""
    host: str = entry.data[CONF_HOST]
    coordinator: BiaCtrlDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, host, device, coordinator)
        for device in coordinator.data
        if device["type"] in SUPPORTED_SENSORS
    )


class Device(CoordinatorEntity[BiaCtrlDataUpdateCoordinator], CoverEntity):
    """Cover device class."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        device: dict[str, Any],
        coordinator: BiaCtrlDataUpdateCoordinator,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._host = host
        self._attr_name = device["name"]
        self._attr_unique_id = device["id"]
        self._attr_is_closed = True
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device["id"]),
            },
            manufacturer="BiaHome",
            model=device["type"],
            name=self.name,
        )
        self._attr_supported_features = (
            CoverEntityFeature.CLOSE | CoverEntityFeature.OPEN | CoverEntityFeature.STOP
        )
        self._attr_device_class = DEVICE_CLASS_MAP[device["type"]]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["id"] == self.unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            if state == "opening":
                self._attr_is_opening = True
                self._attr_is_closing = False
                self._attr_is_closed = False
            elif state == "closing":
                self._attr_is_opening = False
                self._attr_is_closing = True
                self._attr_is_closed = False
            else:
                self._attr_is_opening = False
                self._attr_is_closing = False
                self._attr_is_closed = state == "closed"
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.async_control_cover(cmd="open")
        self._attr_is_closed = False

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.async_control_cover(cmd="close")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.async_control_cover(cmd="stop")

    async def async_control_cover(self, cmd: str) -> None:
        """Control the cover."""
        await control_device(
            self._session,
            self._host,
            "cover",
            self.unique_id,
            cmd,
        )
        await self.coordinator.async_request_refresh()
