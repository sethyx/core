"""Binary sensor module for the iCON integration."""

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IconDataUpdateCoordinator
from .const import DOMAIN

SUPPORTED_BINARY_SENSORS = {Platform.BINARY_SENSOR}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensor entities from a config entry."""
    coordinator: IconDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SensorDevice(device, coordinator)
        for device in coordinator.data
        if device["type"] in SUPPORTED_BINARY_SENSORS
    )


class SensorDevice(CoordinatorEntity[IconDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a binary sensor device."""

    def __init__(
        self, device: dict[str, Any], coordinator: IconDataUpdateCoordinator
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = device["id"]
        self._attr_name = device["name"]
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_is_on = device["is_on"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["parent"])},
            manufacturer="NGBS",
            name=device["parent"],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        updated_device = next(
            (dev for dev in self.coordinator.data if dev[CONF_ID] == self.unique_id),
            None,
        )
        if updated_device:
            self._attr_is_on = updated_device["is_on"]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
