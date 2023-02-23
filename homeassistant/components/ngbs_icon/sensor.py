"""Sensor module."""
from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, PERCENTAGE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IconDataUpdateCoordinator
from .const import DOMAIN

SUPPORTED_SENSORS = {Platform.SENSOR, Platform.CLIMATE}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Async setup entry."""
    icon_id: str = entry.data[CONF_ID]
    coordinator: IconDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    devices_to_add = []
    for device in coordinator.data:
        if device["type"] == Platform.SENSOR:
            devices_to_add.append(SensorDevice(hass, icon_id, device, coordinator))
        elif device["type"] == Platform.CLIMATE:
            devices_to_add.append(
                SensorDevice(
                    hass, icon_id, device, coordinator, SensorDeviceClass.TEMPERATURE
                )
            )
            devices_to_add.append(
                SensorDevice(
                    hass, icon_id, device, coordinator, SensorDeviceClass.HUMIDITY
                )
            )
    async_add_entities(devices_to_add)


class SensorDevice(CoordinatorEntity[IconDataUpdateCoordinator], SensorEntity):
    """Sensor device class."""

    def __init__(
        self,
        hass: HomeAssistant,
        icon_id: str,
        device: dict[str, Any],
        coordinator: IconDataUpdateCoordinator,
        subtype="",
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._icon_id = icon_id
        self._subtype = subtype
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._attr_name = " ".join([device["name"], subtype])
        self._attr_unique_id = "_".join([device["id"], subtype])
        self._attr_native_unit_of_measurement = (
            UnitOfTemperature.CELSIUS
            if subtype in ("", SensorDeviceClass.TEMPERATURE)
            else PERCENTAGE
        )
        self._attr_device_class = subtype or SensorDeviceClass.TEMPERATURE
        if self._subtype == SensorDeviceClass.TEMPERATURE:
            self._attr_native_value = device[ATTR_CURRENT_TEMPERATURE]
        elif self._subtype == SensorDeviceClass.HUMIDITY:
            self._attr_native_value = device[ATTR_CURRENT_HUMIDITY]
        else:
            self._attr_native_value = device["value"]
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
            if self._subtype == SensorDeviceClass.TEMPERATURE:
                self._attr_native_value = device[ATTR_CURRENT_TEMPERATURE]
            elif self._subtype == SensorDeviceClass.HUMIDITY:
                self._attr_native_value = device[ATTR_CURRENT_HUMIDITY]
            else:
                self._attr_native_value = device["value"]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
