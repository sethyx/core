"""Binary sensor module."""
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IconDataUpdateCoordinator
from .const import DOMAIN

SUPPORTED_SENSORS = {Platform.BINARY_SENSOR}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Async setup entry."""
    icon_id: str = entry.data[CONF_ID]
    coordinator: IconDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SensorDevice(hass, icon_id, device, coordinator)
        for device in coordinator.data
        if device["type"] in SUPPORTED_SENSORS
    )


class SensorDevice(CoordinatorEntity[IconDataUpdateCoordinator], BinarySensorEntity):
    """Binary sensor device class."""

    def __init__(
        self,
        hass: HomeAssistant,
        icon_id: str,
        device: dict[str, Any],
        coordinator: IconDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._icon_id = icon_id
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._attr_name = device["name"]
        self._attr_unique_id = device["id"]
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_is_on = device["is_on"]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device[CONF_ID]),
            },
            manufacturer="NGBS",
            model=device["type"],
            name=self.name,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device[CONF_ID] == self.unique_id
            ),
            None,
        )
        if device is not None:
            self._attr_is_on = device["is_on"]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
