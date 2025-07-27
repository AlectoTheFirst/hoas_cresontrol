"""
Sensor platform for CresControl.

Simplified sensor implementation focusing on core parameters only.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfTemperature,
    REVOLUTIONS_PER_MINUTE,
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


# Core sensor definitions - including CO2 and climate sensors
CORE_SENSORS = [
    # Voltage inputs
    {
        "key": "in-a:voltage",
        "name": "Input A Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:lightning-bolt",
    },
    {
        "key": "in-b:voltage", 
        "name": "Input B Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:lightning-bolt",
    },
    
    # Fan monitoring
    {
        "key": "fan:rpm",
        "name": "Fan RPM",
        "unit": REVOLUTIONS_PER_MINUTE,
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:fan",
    },
    
    # Climate sensor - Temperature
    {
        "key": "extension:climate-2011:temperature",
        "name": "Climate Temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer",
    },
    
    # Climate sensor - Humidity
    {
        "key": "extension:climate-2011:humidity",
        "name": "Climate Humidity",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-percent",
    },
    
    # CO2 sensor - CO2 Concentration
    {
        "key": "extension:co2-2006:co2-concentration",
        "name": "CO2 Concentration",
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:molecule-co2",
    },
    
    # CO2 sensor - Temperature
    {
        "key": "extension:co2-2006:temperature",
        "name": "CO2 Temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer",
    },
    
    # Climate sensor extension
    {
        "key": "extension:climate-2011:temperature",
        "name": "Air Temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer",
    },
    {
        "key": "extension:climate-2011:humidity",
        "name": "Humidity",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-percent",
    },
    {
        "key": "extension:climate-2011:vpd",
        "name": "Vapor Pressure Deficit (VPD)",
        "unit": "kPa",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-percent",
    },
    
    # RS485 sensor data - CO2
    {
        "key": "rs485:response:103",
        "name": "CO2 Level",
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:molecule-co2",
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up CresControl sensors based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info = data["device_info"]
    
    # Create core sensor entities only
    entities = [
        CresControlSensor(coordinator, device_info, definition) 
        for definition in CORE_SENSORS
    ]
    async_add_entities(entities)


class CresControlSensor(CoordinatorEntity, SensorEntity):
    """Simplified CresControl sensor entity."""

    def __init__(self, coordinator, device_info: Dict[str, Any], definition: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._device_info = device_info
        self._key: str = definition["key"]
        self._attr_name = f"CresControl {definition['name']}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._key}"
        self._attr_native_unit_of_measurement = definition.get("unit")
        self._attr_device_class = definition.get("device_class")
        self._attr_state_class = definition.get("state_class")
        self._attr_icon = definition.get("icon")

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information to link this entity with the device."""
        return self._device_info
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for diagnostics."""
        attributes = {}
        
        # Add data source information for diagnostics
        if hasattr(self.coordinator, 'get_connection_status'):
            connection_status = self.coordinator.get_connection_status()
            attributes.update({
                "data_source": "websocket" if connection_status.get("using_websocket_data") else "http",
                "websocket_connected": connection_status.get("websocket_connected", False),
                "last_update_source": "websocket" if connection_status.get("using_websocket_data") else "http_polling"
            })
        
        # Add raw value for debugging
        if self.coordinator.data:
            raw_value = self.coordinator.data.get(self._key)
            if raw_value is not None:
                attributes["raw_value"] = str(raw_value)
        
        return attributes

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor with enhanced error handling and validation."""
        if not self.coordinator.data:
            return None
        
        # Handle RS485 response sensors differently
        if self._key.startswith("rs485:response:"):
            # Get the RS485 response data
            rs485_response = self.coordinator.data.get("rs485:response")
            if rs485_response is None:
                return None
            
            # Parse and validate the RS485 response
            return self._validate_sensor_value(rs485_response)
        
        # Handle regular sensors
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
            
        # Enhanced value parsing with error response handling
        try:
            if isinstance(raw_value, str):
                raw_value = raw_value.strip()
                if not raw_value:
                    return None
                
                # Handle JSON error responses gracefully (especially for fan:rpm)
                if raw_value.startswith('{"error"'):
                    _LOGGER.debug("Received error response for %s: %s", self._key, raw_value)
                    # For fan RPM, return 0 when fan is not connected/responding
                    if self._key == "fan:rpm":
                        return 0
                    return None
                
                # Handle other error indicators
                if raw_value.lower() in ['error', 'n/a', 'unavailable', 'unknown']:
                    _LOGGER.debug("Received error indicator for %s: %s", self._key, raw_value)
                    return None
                
                # Parse numeric values with validation
                parsed_value = self._parse_numeric_value(raw_value)
                if parsed_value is not None:
                    return self._validate_sensor_value(parsed_value)
                
                # If not numeric, return the string value
                return raw_value
                
            else:
                # Handle non-string values
                if isinstance(raw_value, (int, float)):
                    return self._validate_sensor_value(raw_value)
                return raw_value
                
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Failed to parse sensor value for %s: %s (error: %s)", 
                          self._key, raw_value, err)
            return None
    
    def _parse_numeric_value(self, value_str: str) -> Any:
        """Parse a string value to numeric type with proper handling.
        
        Args:
            value_str: String value to parse
            
        Returns:
            Parsed numeric value or None if parsing fails
        """
        try:
            # Try to convert to float first (handles both int and float strings)
            if "." in value_str or "e" in value_str.lower():
                return float(value_str)
            else:
                # For integer strings, try int first for better type accuracy
                try:
                    return int(value_str)
                except ValueError:
                    # Fallback to float if int parsing fails
                    return float(value_str)
        except (ValueError, TypeError):
            return None
    
    def _parse_rs485_response(self, response_str: str) -> dict:
        """Parse RS485 response string to extract sensor parameters.
        
        Format: "[address:param=value;param=value;...:checksum]"
        Example: "[5:100=25.93;101=57.72;102=.;103=0:133]"
        
        Args:
            response_str: Raw RS485 response string
            
        Returns:
            Dict mapping parameter IDs to values, or empty dict if parsing fails
        """
        import re
        
        if not isinstance(response_str, str):
            return {}
        
        # Remove quotes if present
        if response_str.startswith('"') and response_str.endswith('"'):
            response_str = response_str[1:-1]
        
        # Pattern: [address:param=value;param=value;...:checksum]
        pattern = r'\[(\d+):(.*?):(\d+)\]'
        match = re.match(pattern, response_str)
        
        if not match:
            return {}
        
        params_str = match.group(2)
        params = {}
        
        # Parse parameters: param=value;param=value
        for param_pair in params_str.split(';'):
            if '=' in param_pair:
                param_id_str, value_str = param_pair.split('=', 1)
                
                try:
                    param_id = int(param_id_str)
                    
                    # Handle different value types
                    if value_str == '.':
                        value = None
                    else:
                        try:
                            # Try to convert to float
                            value = float(value_str)
                        except ValueError:
                            # Keep as string if not numeric
                            value = value_str
                    
                    params[param_id] = value
                    
                except ValueError:
                    # Skip invalid parameter IDs
                    continue
        
        return params

    def _validate_sensor_value(self, value: Any) -> Any:
        """Validate sensor value based on sensor type and apply reasonable bounds.
        
        Args:
            value: Parsed numeric value
            
        Returns:
            Validated value or None if validation fails
        """
        if value is None:
            return None
        
        try:
            # Voltage sensors validation
            if self._key in ["in-a:voltage", "in-b:voltage"]:
                if isinstance(value, (int, float)):
                    # Reasonable voltage range: -15V to +15V
                    if -15.0 <= value <= 15.0:
                        return round(float(value), 2)  # Round to 2 decimal places
                    else:
                        _LOGGER.warning("Voltage value %s out of range for %s", value, self._key)
                        return None
            
            # Fan RPM validation
            elif self._key == "fan:rpm":
                if isinstance(value, (int, float)):
                    # Reasonable RPM range: 0 to 10000 RPM
                    if 0 <= value <= 10000:
                        return int(value)  # RPM should be integer
                    else:
                        _LOGGER.warning("RPM value %s out of range for %s", value, self._key)
                        return None
            
            # RS485 sensor data validation
            elif self._key.startswith("rs485:response:"):
                # Extract parameter ID from key (e.g., "rs485:response:100" -> 100)
                param_id = self._key.split(":")[-1]
                
                # Parse RS485 response data
                parsed_data = self._parse_rs485_response(value)
                if parsed_data and param_id.isdigit():
                    param_value = parsed_data.get(int(param_id))
                    
                    if param_value is None:
                        return None
                    
                    # Validate based on parameter type
                    if param_id == "100":  # Temperature
                        if isinstance(param_value, (int, float)) and -40.0 <= param_value <= 80.0:
                            return round(float(param_value), 1)
                    elif param_id == "101":  # Humidity
                        if isinstance(param_value, (int, float)) and 0.0 <= param_value <= 100.0:
                            return round(float(param_value), 1)
                    elif param_id == "103":  # CO2
                        if isinstance(param_value, (int, float)) and 0 <= param_value <= 10000:
                            return int(param_value)
                
                return None
            
            # Extension-based CO2 concentration validation
            elif self._key == "extension:co2-2006:co2-concentration":
                if isinstance(value, (int, float)):
                    # CO2 range: 0 to 10000 ppm
                    if 0 <= value <= 10000:
                        return int(value)
                elif isinstance(value, str):
                    try:
                        co2_value = float(value)
                        if 0 <= co2_value <= 10000:
                            return int(co2_value)
                    except ValueError:
                        pass
                _LOGGER.debug("Could not parse CO2 concentration value: %s", value)
                return None
            
            # Extension-based temperature sensors validation
            elif self._key in ["extension:co2-2006:temperature", "extension:climate-2011:temperature"]:
                if isinstance(value, (int, float)):
                    # Temperature range: -40°C to +80°C
                    if -40.0 <= value <= 80.0:
                        return round(float(value), 1)
                elif isinstance(value, str):
                    try:
                        temp_value = float(value)
                        if -40.0 <= temp_value <= 80.0:
                            return round(temp_value, 1)
                    except ValueError:
                        pass
                _LOGGER.debug("Could not parse temperature value: %s", value)
                return None
            
            # Extension-based humidity validation
            elif self._key == "extension:climate-2011:humidity":
                if isinstance(value, (int, float)):
                    # Humidity range: 0% to 100%
                    if 0.0 <= value <= 100.0:
                        return round(float(value), 1)
                elif isinstance(value, str):
                    try:
                        hum_value = float(value)
                        if 0.0 <= hum_value <= 100.0:
                            return round(hum_value, 1)
                    except ValueError:
                        pass
                _LOGGER.debug("Could not parse humidity value: %s", value)
                return None
            
            # Extension-based VPD validation
            elif self._key == "extension:climate-2011:vpd":
                if isinstance(value, (int, float)):
                    # VPD range: 0 to 10 kPa (reasonable range for plants)
                    if 0.0 <= value <= 10.0:
                        return round(float(value), 2)
                elif isinstance(value, str):
                    try:
                        vpd_value = float(value)
                        if 0.0 <= vpd_value <= 10.0:
                            return round(vpd_value, 2)
                    except ValueError:
                        pass
                _LOGGER.debug("Could not parse VPD value: %s", value)
                return None
            
            # Default: return the value as-is if no specific validation
            return value
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Value validation failed for %s: %s (error: %s)", 
                          self._key, value, err)
            return None
