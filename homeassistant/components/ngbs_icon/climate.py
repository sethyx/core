"""Climate module."""
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
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IconDataUpdateCoordinator
from .const import DOMAIN
from .icon import set_ce_mode, set_hc_mode, set_temperature

SUPPORTED_SENSORS = {Platform.CLIMATE}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Async setup entry."""
    icon_id: str = entry.data[CONF_ID]
    coordinator: IconDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ClimateDevice(hass, icon_id, device, coordinator)
        for device in coordinator.data
        if device["type"] in SUPPORTED_SENSORS
    )


class ClimateDevice(CoordinatorEntity[IconDataUpdateCoordinator], ClimateEntity):
    """Climate device class."""

    def __init__(
        self,
        hass: HomeAssistant,
        icon_id: str,
        device: dict[str, Any],
        coordinator: IconDataUpdateCoordinator,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._icon_id = icon_id
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._attr_name = device[CONF_NAME]
        self._attr_target_temperature_step = 0.5
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_unique_id = device[CONF_ID]
        self._attr_current_temperature = device[ATTR_CURRENT_TEMPERATURE]
        self._attr_current_humidity = device[ATTR_CURRENT_HUMIDITY]
        self._attr_target_temperature = device["target_temperature"]
        self._attr_max_temp = device["target_temperature_max"]
        self._attr_min_temp = device["target_temperature_min"]
        self._attr_preset_mode = device[ATTR_PRESET_MODE]
        self._attr_preset_modes = [PRESET_ECO, PRESET_COMFORT]
        self._attr_hvac_action = device[ATTR_HVAC_ACTION]
        self._attr_hvac_mode = device[ATTR_HVAC_MODE]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device[CONF_ID]),
            },
            manufacturer="NGBS",
            model=device["type"],
            name=self.name,
        )

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )
        if device["hc_controller"]:
            self._attr_hvac_modes = [HVACMode.COOL, HVACMode.HEAT]
        else:
            self._attr_hvac_modes = [device[ATTR_HVAC_MODE]]
        self._attr_device_class = Platform.CLIMATE

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
            self._attr_current_temperature = device[ATTR_CURRENT_TEMPERATURE]
            self._attr_current_humidity = device[ATTR_CURRENT_HUMIDITY]
            self._attr_target_temperature = device["target_temperature"]
            self._attr_target_temperature_high = device["target_temperature_max"]
            self._attr_target_temperature_low = device["target_temperature_min"]
            self._attr_preset_mode = device[ATTR_PRESET_MODE]
            self._attr_hvac_action = device[ATTR_HVAC_ACTION]
            self._attr_hvac_mode = device[ATTR_HVAC_MODE]
            if device["hc_controller"]:
                self._attr_hvac_modes = [HVACMode.COOL, HVACMode.HEAT]
            else:
                self._attr_hvac_modes = [device[ATTR_HVAC_MODE]]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        await set_hc_mode(self._session, self._icon_id, self._attr_unique_id, hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        await set_ce_mode(
            self._session, self._icon_id, self._attr_unique_id, preset_mode
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            raise ValueError(f"Missing parameter {ATTR_TEMPERATURE}")

        temperature = kwargs[ATTR_TEMPERATURE]
        await set_temperature(
            self._session, self._icon_id, self._attr_unique_id, temperature
        )
