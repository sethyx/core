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


async def _logout(session: aiohttp.ClientSession) -> None:
    async with session.get("http://www.enzoldhazam.hu/logout") as resp:
        await resp.text()


async def login(
    session: aiohttp.ClientSession, email: str, password: str, xid: str
) -> int:
    """Login on API endpoint."""
    async with session.get("http://www.enzoldhazam.hu") as resp:
        _LOGGER.info("Login step 1 - %s", resp.status)
        html_data = await resp.text()
        # _LOGGER.info(html_data)
        token_pos = html_data.find("token")
        sub_data = html_data[token_pos : token_pos + 100]
        token = re.findall(r"\d+", sub_data)
        if len(token) < 1:
            # most likely stuck session, logout
            await _logout(session)
            return 500
        _LOGGER.info("Token: %s", token)

        form_data = aiohttp.FormData()
        form_data.add_field("username", email)
        form_data.add_field("password", password)
        form_data.add_field("token", token)
        async with session.post(AUTH_URL, data=form_data) as resp:
            #  this will be a 302
            data = await resp.text()
            _LOGGER.info("Login step 2 - %s", resp.status)
            _LOGGER.info(data)

        async with session.get(LIST_URL) as resp:
            _LOGGER.info("Login step 3 - %s", resp.status)
            if resp.status == 200:
                data = await resp.text()
                _LOGGER.info(data)
                json_data = json.loads(data)
                # _LOGGER.info(json_data)
                icon_match = _get_icon_match_from_login(json_data, xid)
                if not icon_match:
                    return 404
                _LOGGER.info("ICON ID %s found in response", xid)
                online = _get_online_from_login(json_data, xid)
                if not online:
                    return 503
                _LOGGER.info("ICON is online")
                return 200
            return 500


async def poll_api(session: aiohttp.ClientSession, email: str, password: str, xid: str):
    """Get all devices."""
    _LOGGER.info("Polling NGBS")
    async with session.get(f"{DEVICE_POLL_URL}{xid}") as resp:
        _LOGGER.info("Poll response code: %s", resp.status)
        data = await resp.text()
        _LOGGER.info(data)
        try:
            json_data = json.loads(data)
            # _LOGGER.info(json_data)
            return _generate_devices(json_data)
        except json.decoder.JSONDecodeError as exc:
            _LOGGER.warning("Non-JSON, most likely not logged in: %s", exc_info=exc)
            await login(session, email, password, xid)
            return False


def _generate_devices(data) -> list:
    devices = []
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
    return devices


def _get_icon_match_from_login(data: dict, xid: str) -> bool:
    return xid in data["ICONS"]


def _get_online_from_login(data: dict, xid: str) -> bool:
    return data["ICONS"][xid]["ONLINE"] == 1


def _verify_set_response(data: dict) -> bool:
    return data["WRITE"]["status"] == 1


async def set_hc_mode(session: aiohttp.ClientSession, xid: str, xtid, h_c: str):
    """Set heating/cooling mode."""
    form_data = aiohttp.FormData()
    form_data.add_field("action", "setIcon")
    form_data.add_field("attr", "HC")
    form_data.add_field("icon", xid)
    form_data.add_field("value", 1 if h_c == "cool" else 0)
    _LOGGER.info("Control HC mode: %s %s %s", xid, xtid, h_c)
    async with session.post(CONTROL_URL, data=form_data) as resp:
        result = resp.status
        if result == 200:
            data = await resp.text()
            json_data = json.loads(data)
            _LOGGER.info(json_data)
            return _verify_set_response(json_data)
        return False


async def set_ce_mode(session: aiohttp.ClientSession, xid: str, xtid, c_e: str):
    """Set temperature of thermostat."""
    form_data = aiohttp.FormData()
    form_data.add_field("action", "setThermostat")
    form_data.add_field("attr", "CE")
    form_data.add_field("icon", xid)
    form_data.add_field("thermostat", xtid)
    form_data.add_field("value", 1 if c_e == "eco" else 0)
    _LOGGER.info("Control CE mode: %s %s %s", xid, xtid, c_e)
    async with session.post(CONTROL_URL, data=form_data) as resp:
        result = resp.status
        if result == 200:
            data = await resp.text()
            json_data = json.loads(data)
            _LOGGER.info(json_data)
            return _verify_set_response(json_data)
        return False


async def set_temperature(session: aiohttp.ClientSession, xid: str, xtid, temp: int):
    """Set temperature of thermostat."""
    form_data = aiohttp.FormData()
    form_data.add_field("action", "setThermostat")
    form_data.add_field("attr", "REQ")
    form_data.add_field("icon", xid)
    form_data.add_field("thermostat", xtid)
    form_data.add_field("value", temp)
    _LOGGER.info("Control thermostat temp: %s %s %s", xid, xtid, temp)
    async with session.post(CONTROL_URL, data=form_data) as resp:
        result = resp.status
        if result == 200:
            data = await resp.text()
            json_data = json.loads(data)
            _LOGGER.info(json_data)
            return _verify_set_response(json_data)
        return False
