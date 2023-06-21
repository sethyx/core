"""External module."""
import json
import logging
import re

import aiohttp

_LOGGER = logging.getLogger(__name__)

AUTH_URL = "http://www.enzoldhazam.hu"
LIST_URL = "https://www.enzoldhazam.hu/Ax?action=iconList"
DEVICE_POLL_URL = "https://www.enzoldhazam.hu/Ax?action=iconByID&serial="
CONTROL_URL = "http://www.enzoldhazam.hu/Ax"
LOGOUT_URL = "http://www.enzoldhazam.hu/logout"


class IconClient:
    """Class to handle iCON client connections."""

    def __init__(self, session: aiohttp.ClientSession, email, password, xid) -> None:
        """Initialize client."""
        self.session = session
        self.email = email
        self.password = password
        self.xid = xid
        self.logged_in = False

    async def logout(self) -> None:
        """Logout from API endpoint."""
        async with self.session.get(LOGOUT_URL) as resp:
            self.logged_in = False
            await resp.text()

    async def login(self) -> None:
        """Login on API endpoint."""
        async with self.session.get(AUTH_URL) as resp:
            _LOGGER.info("Login step 1 - %s", resp.status)
            html_data = await resp.text()
            # _LOGGER.info(html_data)
        token_pos = html_data.find("token")
        sub_data = html_data[token_pos : token_pos + 100]
        token = re.findall(r"\d+", sub_data)
        if len(token) < 1:
            # most likely stuck session, logout
            await self.logout()
            raise LogoutNeededError
        _LOGGER.debug("Token: %s", token)

        form_data = aiohttp.FormData()
        form_data.add_field("username", self.email)
        form_data.add_field("password", self.password)
        form_data.add_field("token", token)
        async with self.session.post(AUTH_URL, data=form_data) as resp:
            #  this will be a 302
            data = await resp.text()
            _LOGGER.info("Login step 2 - %s", resp.status)

        async with self.session.get(LIST_URL) as resp:
            _LOGGER.info("Login step 3 - %s", resp.status)
            if resp.status == 200:
                data = await resp.text()
                _LOGGER.debug(data)
                try:
                    json_data = json.loads(data)
                except json.decoder.JSONDecodeError as exc:
                    _LOGGER.warning(
                        "Non-JSON, most likely not logged in: %s", exc_info=exc
                    )
                    raise UnauthorizedError from exc
                icon_match = _get_icon_match_from_login(json_data, self.xid)
                if not icon_match:
                    self.logged_in = False
                    raise InvalidIDError
                _LOGGER.info("ICON ID %s found in response", self.xid)
                online = _get_online_from_login(json_data, self.xid)
                _LOGGER.info("ICON connected: %s", online)
                self.logged_in = True
                return
            self.logged_in = False
            raise CannotConnect

    async def poll_api(self):
        """Get all devices."""

        _LOGGER.info("Polling NGBS")

        async with self.session.get(f"{DEVICE_POLL_URL}{self.xid}") as resp:
            _LOGGER.info("Poll response code: %s", resp.status)
            data = await resp.text()
            _LOGGER.debug(data)
            try:
                json_data = json.loads(data)
                # _LOGGER.info(json_data)
                if json_data.get("code") in ["401", "403"]:
                    _LOGGER.warning("Auth expired, logging out and in")
                    self.logged_in = False
                    await self.login()
                    return False
                return _generate_devices(json_data)

            except json.decoder.JSONDecodeError as exc:
                _LOGGER.warning("Non-JSON, most likely not logged in: %s", exc_info=exc)
                self.logged_in = False
                await self.login()
                return False

    async def set_hc_mode(self, xtid, h_c: str):
        """Set heating/cooling mode."""
        form_data = aiohttp.FormData()
        form_data.add_field("action", "setIcon")
        form_data.add_field("attr", "HC")
        form_data.add_field("icon", self.xid)
        form_data.add_field("value", 1 if h_c == "cool" else 0)
        _LOGGER.info("Control HC mode: %s %s %s", self.xid, xtid, h_c)
        async with self.session.post(CONTROL_URL, data=form_data) as resp:
            result = resp.status
            if result == 200:
                data = await resp.text()
                json_data = json.loads(data)
                _LOGGER.info(json_data)
                return _verify_set_response(json_data)
            return False

    async def set_ce_mode(self, xtid, c_e: str):
        """Set temperature of thermostat."""
        form_data = aiohttp.FormData()
        form_data.add_field("action", "setThermostat")
        form_data.add_field("attr", "CE")
        form_data.add_field("icon", self.xid)
        form_data.add_field("thermostat", xtid)
        form_data.add_field("value", 1 if c_e == "eco" else 0)
        _LOGGER.info("Control CE mode: %s %s %s", self.xid, xtid, c_e)
        async with self.session.post(CONTROL_URL, data=form_data) as resp:
            result = resp.status
            if result == 200:
                data = await resp.text()
                json_data = json.loads(data)
                _LOGGER.info(json_data)
                return _verify_set_response(json_data)
            return False

    async def set_temperature(self, xtid, temp: int):
        """Set temperature of thermostat."""
        form_data = aiohttp.FormData()
        form_data.add_field("action", "setThermostat")
        form_data.add_field("attr", "REQ")
        form_data.add_field("icon", self.xid)
        form_data.add_field("thermostat", xtid)
        form_data.add_field("value", temp)
        _LOGGER.info("Control thermostat temp: %s %s %s", self.xid, xtid, temp)
        async with self.session.post(CONTROL_URL, data=form_data) as resp:
            result = resp.status
            if result == 200:
                data = await resp.text()
                json_data = json.loads(data)
                _LOGGER.info(json_data)
                return _verify_set_response(json_data)
            return False


def _generate_devices(data) -> list:
    devices = []
    online = data.get("ICON").get(
        "ONLINE"
    )  # can be both a bool and an int... great code NGBS
    if not (online):
        devices.append(
            {
                "type": "binary_sensor",
                "id": "connection",
                "name": "System connected",
                "is_on": False,
            }
        )
        _LOGGER.debug(devices)
        return devices
    # main device
    master_name = data.get("ICON").get("HC_MASTERICON")
    # add sensors
    devices.append(
        {
            "type": "sensor",
            "id": "wtemp",
            "name": "Water temperature",
            "value": data.get("ICON").get("WTEMP"),
        }
    )
    # add binary sensors
    devices.append(
        {
            "type": "binary_sensor",
            "id": "pump",
            "name": "Water pump",
            "is_on": data.get("ICON").get("PUMP") > 0,
        }
    )
    devices.append(
        {
            "type": "binary_sensor",
            "id": "connection",
            "name": "System connected",
            "is_on": data.get("ICON").get("ONLINE") > 0,
        }
    )
    devices.append(
        {
            "type": "sensor",
            "id": "valve_state",
            "name": "Valve state",
            "value": data.get("ICON").get("AO"),
        }
    )
    # add thermostats
    for therm in data.get("ICON").get("DP"):
        hc_controller = therm.get("title") == master_name
        if therm.get("CE"):
            preset_mode = "eco"
        else:
            preset_mode = "comfort"
        if therm.get("HC"):
            hvac_mode = "cool"
        else:
            hvac_mode = "heat"
        if therm.get("OUT"):
            hvac_action = "cooling" if therm.get("HC") else "heating"
        else:
            hvac_action = "idle"
        devices.append(
            {
                "type": "climate",
                "id": therm.get("ID"),
                "name": therm.get("title"),
                "current_temperature": therm.get("TEMP"),
                "current_humidity": therm.get("RH"),
                "target_temperature": therm.get("REQ"),
                "target_temperature_max": therm.get("TMAX"),
                "target_temperature_min": therm.get("TMIN"),
                "preset_mode": preset_mode,
                "hvac_action": hvac_action,
                "hvac_mode": hvac_mode,
                "hc_controller": hc_controller,
            }
        )
        devices.append(
            {
                "type": "sensor",
                "id": "_".join([therm.get("ID"), "humidity"]),
                "name": " ".join([therm.get("title"), "humidity"]),
                "value": therm.get("RH"),
            }
        )
        devices.append(
            {
                "type": "sensor",
                "id": "_".join([therm.get("ID"), "temperature"]),
                "name": " ".join([therm.get("title"), "temperature"]),
                "value": therm.get("TEMP"),
            }
        )
        devices.append(
            {
                "type": "sensor",
                "id": "_".join([therm.get("ID"), "dewpoint_temperature"]),
                "name": " ".join([therm.get("title"), "dewpoint temperature"]),
                "value": therm.get("DEW"),
            }
        )
    _LOGGER.debug(devices)
    return devices


def _get_icon_match_from_login(data: dict, xid: str) -> bool:
    return xid in data["ICONS"]


def _get_online_from_login(data: dict, xid: str) -> bool:
    return data["ICONS"][xid]["ONLINE"] == 1


def _verify_set_response(data: dict) -> bool:
    return data["WRITE"]["status"] == 1


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class UnauthorizedError(Exception):
    """Error to indicate we cannot authorize."""


class InvalidIDError(Exception):
    """Error to indicate we cannot find a system ID."""


class LogoutNeededError(Exception):
    """Error to indicate we need to logout the session."""
