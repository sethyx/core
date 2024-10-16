"""Sensor module for the iCON integration."""

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    PERCENTAGE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IconDataUpdateCoordinator
from .const import DOMAIN

SUPPORTED_SENSOR_DEVICES = {Platform.SENSOR}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: IconDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SensorDevice(device, coordinator)
        for device in coordinator.data
        if device["type"] == Platform.SENSOR
    )


class SensorDevice(CoordinatorEntity[IconDataUpdateCoordinator], SensorEntity):
    """Representation of a sensor device."""

    def __init__(
        self, device: dict[str, Any], coordinator: IconDataUpdateCoordinator
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device = device
        self._parent = device.get("parent")
        self._attr_unique_id = device[CONF_ID]
        self._attr_name = device[CONF_NAME]
        self._attr_device_class = (
            SensorDeviceClass.HUMIDITY
            if ("valve" in device[CONF_ID] or "humid" in device[CONF_ID])
            else SensorDeviceClass.TEMPERATURE
        )
        self._attr_native_unit_of_measurement = (
            PERCENTAGE
            if ("valve" in device[CONF_ID] or "humid" in device[CONF_ID])
            else UnitOfTemperature.CELSIUS
        )
        self._attr_native_value = device["value"]
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
            self._attr_native_value = updated_device["value"]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
