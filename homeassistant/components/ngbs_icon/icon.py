"""iCon module for the iCON integration."""

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

API_URL = "https://stat.ngbsh.hu/api"

# may need to expose these on the ui
APP_VERSION = "1.1.3.2"


class IconClient:
    """Class to handle iCON client connections."""

    def __init__(
        self, session: aiohttp.ClientSession, email: str, password: str, system_id: str
    ) -> None:
        """Initialize client."""
        self.session = session
        self.email = email
        self.password = password
        self.token = None
        self.last_data = dict[str, Any]()
        self.system_id = system_id

    async def async_login(self):
        """Perform login to the NGBSH API."""
        url = f"{API_URL}/auth"
        data = {"username": self.email, "password": self.password, "version": "1.1.3.2"}
        try:
            async with self.session.post(url, json=data, timeout=10) as response:
                response.raise_for_status()
                result = await response.json()
                self.token = result["token"]
                return True
        except aiohttp.ClientError as e:
            _LOGGER.error("Login failed: %s", e)
            return False
        except TimeoutError:
            _LOGGER.error("Login timed out")
            return False

    async def async_get_data(self) -> list[dict[str, Any]]:
        """Retrieve data from the NGBSH API and calls _generate_entities."""
        if self.token is None and not await self.async_login():
            return [self.last_data]
        url = f"{API_URL}/icon/iconlist"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with self.session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(10)
            ) as response:
                response.raise_for_status()
                full_data = await response.json()
                self.last_data = full_data.get("ICONS", {}).get(self.system_id, {})
                return _generate_entities(self.last_data)
        except aiohttp.ClientError as e:
            _LOGGER.error("Error getting data: %s", e)
            if response.status in (401, 403):
                if await self.async_login():
                    return await self.async_get_data()
            return [self.last_data]
        except TimeoutError:
            _LOGGER.error("Getting data timed out")
            return [self.last_data]

    async def async_set_temperature(self, thermostat_id, temperature):
        """Set the temperature for a specific thermostat."""
        if self.token is None and not await self.async_login():
            return False
        url = f"{API_URL}/icon/set"
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "attr": "REQ",
            "value": temperature,
            "SNR": self.system_id,
            "TERM": thermostat_id,
        }
        try:
            async with self.session.post(
                url, headers=headers, json=data, timeout=10
            ) as response:
                response.raise_for_status()
                _LOGGER.debug(
                    "Temperature set for %s to %f", thermostat_id, temperature
                )
                return True
        except aiohttp.ClientError as e:
            _LOGGER.error("Error setting temperature: %s", e)
            if response.status in (401, 403):
                if await self.async_login():
                    return await self.async_set_temperature(thermostat_id, temperature)
            return False
        except TimeoutError:
            _LOGGER.error("Setting temperature timed out")
            return False

    async def async_set_hvac_mode(self, mode):
        """Set the heating/cooling mode for the master thermostat."""
        if self.token is None and not await self.async_login():
            return False

        if not self.last_data:
            await self.async_get_data()
        if self.last_data is None:
            return False

        master_id = self.last_data.get("HC_MASTERICON")
        if not master_id:
            _LOGGER.error("Master thermostat not found")
            return False

        value = 0 if mode == "heat" else 1  # 0: heat, 1: cool

        url = f"{API_URL}/icon/set"
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {"value": value, "SNR": self.system_id, "attr": "HC", "TERM": ""}
        try:
            async with self.session.post(
                url, headers=headers, json=data, timeout=10
            ) as response:
                response.raise_for_status()
                _LOGGER.debug("HVAC mode set to %s", mode)
                return True
        except aiohttp.ClientError as e:
            _LOGGER.error("Error setting HVAC mode: %s", e)
            if response.status in (401, 403):
                if await self.async_login():
                    return await self.async_set_hvac_mode(mode)
            return False
        except TimeoutError:
            _LOGGER.error("Setting HVAC mode timed out")
            return False

    async def async_set_eco_mode(self, thermostat_id, mode):
        """Set eco/comfort mode for a specific thermostat."""
        if self.token is None and not await self.async_login():
            return False

        value = 1 if mode == "eco" else 0  # 1: eco, 0: comfort

        url = f"{API_URL}/icon/set"
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "attr": "CE",
            "value": value,
            "SNR": self.system_id,
            "TERM": thermostat_id,
        }
        try:
            async with self.session.post(
                url, headers=headers, json=data, timeout=10
            ) as response:
                response.raise_for_status()
                _LOGGER.debug("Eco mode set for %s to %s", thermostat_id, mode)
                return True
        except aiohttp.ClientError as e:
            _LOGGER.error("Error setting eco mode: %s", e)
            if response.status in (401, 403):
                if await self.async_login():
                    return await self.async_set_eco_mode(thermostat_id, mode)
            return False
        except TimeoutError:
            _LOGGER.error("Setting eco mode timed out")
            return False


def _generate_entities(data: dict) -> list:
    """Generate device data from API response."""
    entities = []
    online = data.get("ONLINE", False)

    if not online:
        entities.append(
            {
                "type": "binary_sensor",
                "id": "icon_system_connection",
                "parent": "iCon system",
                "name": "System connected",
                "is_on": False,
            }
        )
        return entities

    master_name = data.get("HC_MASTERICON")
    entities.append(
        {
            "type": "sensor",
            "id": "icon_system_wtemp",
            "parent": "iCon system",
            "name": "Water temperature",
            "value": data.get("WTEMP"),
        }
    )
    entities.append(
        {
            "type": "binary_sensor",
            "id": "icon_system_pump",
            "parent": "iCon system",
            "name": "Water pump",
            "is_on": data.get("PUMP", 0) > 0,
        }
    )
    entities.append(
        {
            "type": "binary_sensor",
            "id": "icon_system_connection",
            "parent": "iCon system",
            "name": "System connected",
            "is_on": online,
        }
    )
    entities.append(
        {
            "type": "sensor",
            "id": "icon_system_valve_state",
            "parent": "iCon system",
            "name": "Valve state",
            "value": data.get("AO"),
        }
    )

    for therm in data.get("DP", []):
        hc_controller = therm.get("title") == master_name
        preset_mode = "eco" if therm.get("CE") else "comfort"
        hvac_mode = "cool" if therm.get("HC") else "heat"

        # Determine hvac_action
        if therm.get("OUT"):
            hvac_action = "cooling" if therm.get("HC") else "heating"
        else:
            hvac_action = "idle"

        main_name = therm.get("title")
        entities.append(
            {
                "type": "climate",
                "id": therm.get("ID"),
                "name": f"{main_name} thermostat",
                "parent": main_name,
                "current_temperature": therm.get("TEMP"),
                "current_humidity": therm.get("RH"),
                "target_temperature": therm.get("REQ"),
                "target_temperature_max": therm.get("TMAX"),
                "target_temperature_min": therm.get("TMIN"),
                "preset_mode": preset_mode,
                "hvac_mode": hvac_mode,
                "hvac_action": hvac_action,
                "hc_controller": hc_controller,
            }
        )

        entities.append(
            {
                "type": "sensor",
                "id": f"{therm.get('ID')}_humidity",
                "parent": main_name,
                "name": f"{therm.get('title')} humidity",
                "value": therm.get("RH"),
            }
        )

        entities.append(
            {
                "type": "sensor",
                "id": f"{therm.get('ID')}_temperature",
                "parent": main_name,
                "name": f"{therm.get('title')} temperature",
                "value": therm.get("TEMP"),
            }
        )

        entities.append(
            {
                "type": "sensor",
                "id": f"{therm.get('ID')}_dewpoint_temperature",
                "parent": main_name,
                "name": f"{therm.get('title')} dewpoint temperature",
                "value": therm.get("DEW"),
            }
        )
    return entities


class CannotConnect(Exception):
    """Error to indicate connection failure."""


class UnauthorizedError(Exception):
    """Error to indicate authorization failure."""


class InvalidIDError(Exception):
    """Error to indicate invalid system ID."""


class LogoutNeededError(Exception):
    """Error to indicate session logout is required."""
