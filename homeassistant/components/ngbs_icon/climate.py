"""Climate module for the iCON integration."""

from asyncio import sleep
import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_NAME, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IconDataUpdateCoordinator
from .const import DOMAIN

SUPPORTED_CLIMATE_DEVICES = {Platform.CLIMATE}
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the climate entities from a config entry."""
    coordinator: IconDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ClimateDevice(device, coordinator, optimistic=True)
        for device in coordinator.data
        if device["type"] in SUPPORTED_CLIMATE_DEVICES
    )


class ClimateDevice(CoordinatorEntity[IconDataUpdateCoordinator], ClimateEntity):
    """Representation of a climate device."""

    def __init__(
        self,
        entity: dict[str, Any],
        coordinator: IconDataUpdateCoordinator,
        optimistic: bool = True,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        _LOGGER.info("Setting up: %s", entity)
        self._device = entity
        self._optimistic = optimistic  # Track if optimistic mode is enabled
        self._attr_unique_id = entity[CONF_ID]
        self._attr_name = entity[CONF_NAME]
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_target_temperature_step = 0.5
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )
        self._attr_preset_modes = [PRESET_ECO, PRESET_COMFORT]
        self._initialize_device_state()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entity["parent"])},
            manufacturer="NGBS",
            name=entity["parent"],
        )

    def _initialize_device_state(self) -> None:
        """Initialize the current device state attributes."""
        self._attr_current_temperature = self._device[ATTR_CURRENT_TEMPERATURE]
        self._attr_current_humidity = self._device[ATTR_CURRENT_HUMIDITY]
        self._attr_target_temperature = self._device["target_temperature"]
        self._attr_max_temp = self._device["target_temperature_max"]
        self._attr_min_temp = self._device["target_temperature_min"]
        self._attr_preset_mode = self._device[ATTR_PRESET_MODE]
        self._attr_hvac_action = self._device[ATTR_HVAC_ACTION]
        self._attr_hvac_mode = self._device[ATTR_HVAC_MODE]
        self._attr_hvac_modes = (
            [HVACMode.COOL, HVACMode.HEAT]
            if self._device.get("hc_controller")
            else [self._device[ATTR_HVAC_MODE]]
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (dev for dev in self.coordinator.data if dev[CONF_ID] == self.unique_id),
            None,
        )
        if device:
            self._device = device
            self._initialize_device_state()
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set a new target HVAC mode."""
        if hvac_mode != self._attr_hvac_mode:
            await self.coordinator.api.set_hc_mode(self._attr_unique_id, hvac_mode)
            if self._optimistic:
                # Optimistically update the hvac mode immediately
                self._attr_hvac_mode = hvac_mode
                self.async_write_ha_state()  # Notify HA about the updated state
            await sleep(2)
            if not self._optimistic:
                await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a new preset mode."""
        if preset_mode != self._attr_preset_mode:
            await self.coordinator.api.set_ce_mode(self._attr_unique_id, preset_mode)
            if self._optimistic:
                # Optimistically update the preset mode immediately
                self._attr_preset_mode = preset_mode
                self.async_write_ha_state()  # Notify HA about the updated state
            await sleep(2)
            if not self._optimistic:
                await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            raise ValueError(f"Missing {ATTR_TEMPERATURE} parameter")

        if target_temperature != self._attr_target_temperature:
            await self.coordinator.api.set_temperature(
                self._attr_unique_id, target_temperature
            )
            if self._optimistic:
                # Optimistically update the target temperature immediately
                self._attr_target_temperature = target_temperature
                self.async_write_ha_state()  # Notify HA about the updated state
            await sleep(2)
            if not self._optimistic:
                await self.coordinator.async_request_refresh()
