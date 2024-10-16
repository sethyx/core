"""iCon module for the iCON integration."""

import json
import logging
import re

import aiohttp

_LOGGER = logging.getLogger(__name__)

AUTH_URL = "http://www.enzoldhazam.hu"
LIST_URL = f"{AUTH_URL}/Ax?action=iconList"
DEVICE_POLL_URL = f"{AUTH_URL}/Ax?action=iconByID&serial="
CONTROL_URL = f"{AUTH_URL}/Ax"
LOGOUT_URL = f"{AUTH_URL}/logout"


class IconClient:
    """Class to handle iCON client connections."""

    def __init__(
        self, session: aiohttp.ClientSession, email: str, password: str, xid: str
    ) -> None:
        """Initialize client."""
        self.session = session
        self.email = email
        self.password = password
        self.xid = xid
        self.logged_in = False

    async def _get_token(self, html_data: str) -> str:
        """Extract token from HTML."""
        token_match = re.search(r"token.*?(\d+)", html_data)
        if not token_match:
            raise LogoutNeededError("Token not found, logout required.")
        return token_match.group(1)

    async def _perform_login(self, token: str) -> None:
        """Complete the login process."""
        form_data = aiohttp.FormData()
        form_data.add_field("username", self.email)
        form_data.add_field("password", self.password)
        form_data.add_field("token", token)
        async with self.session.post(AUTH_URL, data=form_data) as resp:
            if resp.status not in [200, 302]:
                raise UnauthorizedError("Login failed.")
        await self._fetch_icon_list()

    async def _fetch_icon_list(self) -> None:
        """Fetch the list of icons after login."""
        async with self.session.get(LIST_URL) as resp:
            _LOGGER.debug("List Response: %d - %s", resp.status, await resp.text())
            if resp.status != 200:
                raise CannotConnect(f"Failed to fetch system list: {resp.status}")
            json_data = json.loads(await resp.text())
            if not _get_icon_match_from_login(json_data, self.xid):
                raise InvalidIDError(f"ICON ID {self.xid} not found.")
            self.logged_in = True
            _LOGGER.info("Login successful: ICON %s connected", self.xid)

    async def login(self) -> None:
        """Login to API."""
        async with self.session.get(AUTH_URL) as resp:
            _LOGGER.info("Login step 1 - %s", resp.status)
            token = await self._get_token(await resp.text())
            _LOGGER.info("Token: %s", token)
        await self._perform_login(token)

    async def logout(self) -> None:
        """Logout from API endpoint."""
        async with self.session.get(LOGOUT_URL) as resp:
            self.logged_in = False
            await resp.text()

    async def poll_api(self) -> list:
        """Poll the API for device data."""
        _LOGGER.info("Polling NGBS")
        async with self.session.get(f"{DEVICE_POLL_URL}{self.xid}") as resp:
            if resp.status != 200:
                _LOGGER.warning("Poll failed: %s", resp.status)
                await self.login()
                return []
            return _generate_entities(json.loads(await resp.text()))

    async def set_mode(
        self, xtid: str | None, mode: str | None, attr: str, value: int | None
    ) -> bool:
        """Set device mode."""
        form_data = aiohttp.FormData(
            {
                "action": "setThermostat" if attr != "HC" else "setIcon",
                "attr": attr,
                "icon": self.xid,
                "thermostat": xtid if attr != "HC" else None,
                "value": value,
            }
        )
        async with self.session.post(CONTROL_URL, data=form_data) as resp:
            if resp.status == 200:
                json_data = json.loads(await resp.text())
                return _verify_set_response(json_data)
        return False

    async def set_hc_mode(self, xtid: str | None, mode: str | None) -> bool:
        """Set heating/cooling mode."""
        return await self.set_mode(xtid, mode, "HC", 1 if mode == "cool" else 0)

    async def set_ce_mode(self, xtid: str | None, mode: str | None) -> bool:
        """Set energy-saving (eco) mode."""
        return await self.set_mode(xtid, mode, "CE", 1 if mode == "eco" else 0)

    async def set_temperature(self, xtid: str | None, temp: int | None) -> bool:
        """Set the thermostat temperature."""
        return await self.set_mode(xtid, "temp", "REQ", temp)


def _generate_entities(data: dict) -> list:
    """Generate device data from API response."""
    entities = []
    online = data.get("ICON", {}).get("ONLINE", False)

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

    master_name = data["ICON"].get("HC_MASTERICON")
    entities.append(
        {
            "type": "sensor",
            "id": "icon_system_wtemp",
            "parent": "iCon system",
            "name": "Water temperature",
            "value": data["ICON"].get("WTEMP"),
        }
    )
    entities.append(
        {
            "type": "binary_sensor",
            "id": "icon_system_pump",
            "parent": "iCon system",
            "name": "Water pump",
            "is_on": data["ICON"].get("PUMP") > 0,
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
            "value": data["ICON"].get("AO"),
        }
    )

    for therm in data["ICON"].get("DP", []):
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


def _get_icon_match_from_login(data: dict, xid: str) -> bool:
    """Check if icon ID matches login data."""
    return xid in data["ICONS"]


def _verify_set_response(data: dict) -> bool:
    """Verify the success of set command."""
    return data.get("WRITE", {}).get("status") == 1


class CannotConnect(Exception):
    """Error to indicate connection failure."""


class UnauthorizedError(Exception):
    """Error to indicate authorization failure."""


class InvalidIDError(Exception):
    """Error to indicate invalid system ID."""


class LogoutNeededError(Exception):
    """Error to indicate session logout is required."""
