"""External module."""
import logging

import aiohttp

BASE_URL = "http://HOST/api"
_LOGGER = logging.getLogger(__name__)


async def get_devices(host: str, session: aiohttp.ClientSession):
    """Get all devices."""
    url = BASE_URL.replace("HOST", host)
    async with session.get(f"{url}/devices") as resp:
        dev_dict = await resp.json()
        devices = dev_dict.get("devices")
        return devices


async def control_device(
    session: aiohttp.ClientSession, host: str, xtype: str, xid, cmd: str
):
    """Control a specific device."""
    url = BASE_URL.replace("HOST", host)
    form_data = aiohttp.FormData()
    form_data.add_field("device", xid)
    form_data.add_field("type", xtype)
    form_data.add_field("cmd", cmd)
    _LOGGER.info("Control device: %s %s %s %s", host, xtype, xid, cmd)
    async with session.post(f"{url}/biactrl", data=form_data) as resp:
        result = resp.status
        txt = await resp.text()
        _LOGGER.info("Resp: %s %s", result, txt)
        return result == 200
