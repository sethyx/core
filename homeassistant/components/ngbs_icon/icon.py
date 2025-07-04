"""iCon module for the iCON integration."""

import asyncio
import json
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.components.climate.const import PRESET_COMFORT, PRESET_ECO
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE, Platform, UnitOfTemperature
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class IconClient:
    """Class to handle iCON client connections."""

    def __init__(self, host: str, system_id: str, port: int = 7992, timeout: int = 2):
        """Initialize the local API client."""
        self._host = host
        self._port = port
        self._system_id = system_id
        self._timeout = timeout
    
    def set_coordinator(self, coordinator: DataUpdateCoordinator) -> None:
        """Set the coordinator instance to allow for immediate refreshes."""
        self._coordinator = coordinator

    async def _async_request(self, command: dict[str, Any]) -> dict[str, Any]:
        """Sends a request to the NGBS controller and returns the response."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout
            )
        except asyncio.TimeoutError as err:
            raise IconApiConnectionError("Connection timed out") from err
        except OSError as err:
            raise IconApiConnectionError(f"Connection failed: {err}") from err

        response_bytes = b""
        try:
            full_command = command | {"SYSID": self._system_id}
            _LOGGER.debug("Sending command: %s", full_command)
            writer.write(json.dumps(full_command).encode('utf-8'))
            await writer.drain()

            try:
                response_bytes = await asyncio.wait_for(reader.read(-1), timeout=2.0)
            except asyncio.TimeoutError as err:
                raise IconApiConnectionError("Read timed out waiting for response") from err

        except Exception as err:
            raise IconApiClientError(f"An error occurred during communication: {err}") from err
        finally:
            # Ensure the writer is always closed at the very end.
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()

        if not response_bytes:
            _LOGGER.warning("Received empty response from controller")
            return {}

        response_str = response_bytes.decode('utf-8')
        try:
            data = json.loads(response_str)
            if data.get("ERR") == 1:
                raise IconApiCommandError("Controller returned an error")
            return data
        except json.JSONDecodeError as err:
            raise IconApiProtocolError(f"Failed to decode JSON response: {response_str}") from err

    def _parse_state_data(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parses the raw state from the controller, focusing only on ICON1 thermostats and valves.
        """
        entities = []
        _LOGGER.debug("Response: %s", state)
        cfg = state.get('CFG')
        if 'DP' not in state or not cfg:
            _LOGGER.error("Response missing 'DP' or 'CFG', cannot parse state.")
            return entities

        # --- NEW: Identify the master thermostat for HVAC control ---
        # The value is "H1.1", so we slice it to get the ID "1.1"
        master_thermostat_id = (cfg.get('HCMASTER') or "")[1:]
        if not master_thermostat_id:
            _LOGGER.warning("HCMASTER not found in config, HVAC mode control will be disabled.")
        
        system_name = 'iCON system'

        # --- NEW: Create global system entities (Pump, Temp, Valve) ---
        entities.append({
            "type": Platform.BINARY_SENSOR, "id": "icon_pump", "name": f"{system_name} Water Pump", "parent": system_name,
            "is_on": state.get("PUMP") == 1, "device_class": BinarySensorDeviceClass.RUNNING
        })
        entities.append({
            "type": Platform.SENSOR, "id": "icon_water_temp", "name": f"{system_name} Water Temperature", "parent": system_name,
            "value": state.get("WTEMP"), "device_class": SensorDeviceClass.TEMPERATURE, "unit_of_measurement": UnitOfTemperature.CELSIUS
        })
        entities.append({
            "type": Platform.SENSOR, "id": "icon1_valve", "name": f"{system_name} Mixing Valve", "parent": system_name,
            "value": cfg.get('ICON1', {}).get('STATUS', {}).get('AO'), "unit_of_measurement": PERCENTAGE
        })

        for icon_key in ['ICON1', 'ICON2']:
            icon_data = cfg.get(icon_key, {})
            relay_configs = icon_data.get('RELAY', {})
            status_data = icon_data.get('STATUS', {})
            icon_id = icon_key[-1] # '1' or '2'

            if not relay_configs or not status_data:
                continue
            
            for i in range(10): # R0 to R9
                relay_id = f"R{i}"
                config = relay_configs.get(relay_id)
                if not config:
                    continue
                
                func_name = config.get('FUNC', '').strip()
                # Ignore unconfigured relays
                if not func_name or func_name.startswith(f"R{icon_id}."):
                    continue
                
                entities.append({
                    "type": Platform.BINARY_SENSOR,
                    "id": f"{icon_key.lower()}_relay_{i}",
                    "name": func_name, # Use the function name from config
                    "parent": icon_key, # Group under ICON1 or ICON2 device
                    "is_on": status_data.get(relay_id) == 1,
                    "device_class": BinarySensorDeviceClass.RUNNING, # As requested
                })

        controller_is_cooling = state.get('HC') == 1

        for thermostat_id, therm in state['DP'].items():
            # --- NEW: Filter to only include thermostats from ICON1 ---

            if not therm.get('ON') or not therm.get('LIVE'):
                continue

            main_name = therm.get("NAME", f"Thermostat {thermostat_id}")

            is_master_controller = (thermostat_id == master_thermostat_id)

            hvac_mode = HVACMode.COOL if controller_is_cooling else HVACMode.HEAT
            hvac_action = HVACAction.IDLE
            if therm.get("OUT") == 1:
                hvac_action = HVACAction.COOLING if controller_is_cooling else HVACAction.HEATING

            is_thermostat_eco = therm.get("CE") == 1
            preset_mode = PRESET_ECO if is_thermostat_eco else PRESET_COMFORT

            if is_thermostat_eco:
                target_temp = therm.get('ECOC') if controller_is_cooling else therm.get('ECOH')
            else:
                target_temp = therm.get('XAC') if controller_is_cooling else therm.get('XAH')

            entities.append({
                "type": Platform.CLIMATE, "id": thermostat_id, "name": f"{main_name} thermostat", "parent": main_name,
                "current_temperature": therm.get("TEMP"), "current_humidity": therm.get("RH"), "target_temperature": target_temp,
                "preset_mode": preset_mode, "hvac_mode": hvac_mode, "hvac_action": hvac_action,
                "hc_controller": is_master_controller  # Add the master controller attribute
            })

            # Create thermostat-specific sensors
            entities.append({
                "type": Platform.SENSOR, "id": f"{thermostat_id}_temperature", "name": f"{main_name} temperature", "parent": main_name,
                "value": therm.get("TEMP"), "device_class": SensorDeviceClass.TEMPERATURE, "unit_of_measurement": UnitOfTemperature.CELSIUS
            })
            entities.append({
                "type": Platform.SENSOR, "id": f"{thermostat_id}_humidity", "name": f"{main_name} humidity", "parent": main_name,
                "value": therm.get("RH"), "device_class": SensorDeviceClass.HUMIDITY, "unit_of_measurement": PERCENTAGE
            })
            entities.append({
                "type": Platform.SENSOR, "id": f"{thermostat_id}_dewpoint_temperature", "name": f"{main_name} dewpoint temperature", "parent": main_name,
                "value": therm.get("DEW"), "device_class": SensorDeviceClass.TEMPERATURE, "unit_of_measurement": UnitOfTemperature.CELSIUS
            })
            entities.append({
                "type": Platform.BINARY_SENSOR, "id": f"{thermostat_id}_hvac_request", "name": f"{main_name} HVAC request", "parent": main_name,
                "is_on": therm.get("OUT") == 1, "device_class": BinarySensorDeviceClass.RUNNING
            })

        return entities

    async def _refresh_coordinator(self):
        """Triggers a coordinator refresh after a delay."""
        if self._coordinator:
            await asyncio.sleep(2)
            await self._coordinator.async_request_refresh()

    async def async_get_data(self) -> list[dict[str, Any]]:
        """Fetch and parse data from the controller using the correct command."""
        state_data = await self._async_request({"RELOAD": ""})
        return self._parse_state_data(state_data)

    async def async_set_temperature(self, thermostat_id: str, temperature: float):
        """Set the target temperature for a specific thermostat."""
        await self._async_request({'DP': {thermostat_id: {'SP': temperature}}})
        await self._refresh_coordinator()
        return True

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set the system-wide HVAC mode (Heating/Cooling)."""
        is_cooling = 1 if hvac_mode == HVACMode.COOL else 0
        await self._async_request({'HC': is_cooling})
        await self._refresh_coordinator()
        return True

    async def async_set_preset_mode(self, thermostat_id: str, preset_mode: str):
        """Set the preset mode for a specific thermostat."""
        is_eco = 1 if preset_mode == PRESET_ECO else 0
        await self._async_request({'DP': {thermostat_id: {'CE': is_eco}}})
        await self._refresh_coordinator()
        return True

class IconApiClientError(Exception):
    """Base exception for iCON API client errors."""

class IconApiConnectionError(IconApiClientError):
    """Exception for connection errors."""

class IconApiProtocolError(IconApiClientError):
    """Exception for protocol-level errors (e.g., malformed JSON)."""

class IconApiCommandError(IconApiClientError):
    """Exception for command-specific errors returned by the controller."""

