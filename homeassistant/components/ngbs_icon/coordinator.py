"""The iCON integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .icon import CannotConnect, IconClient

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class IconDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator to manage polling the API and updating devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: IconClient,
        config_data: Any[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.hass = hass
        self.entities: list[dict[str, Any]] | None = None
        self.config_entry = config_data
        scan_interval = config_data.get("scan_interval", 300)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from the API and update devices."""
        try:
            result = await self.api.poll_api()
            if result:
                self.entities = result
                return self.entities
            raise UpdateFailed("Error while fetching data, no result from API.")
        except CannotConnect as err:
            raise UpdateFailed(f"Error while fetching data: {err}") from err
