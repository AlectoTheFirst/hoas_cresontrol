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
    REVOLUTIONS_PER_MINUTE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


# Core sensor definitions - reduced to essential parameters only
CORE_SENSORS = [
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
    {
        "key": "fan:rpm",
        "name": "Fan RPM",
        "unit": REVOLUTIONS_PER_MINUTE,
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:fan",
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
            
            # Default: return the value as-is if no specific validation
            return value
            
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Value validation failed for %s: %s (error: %s)", 
                          self._key, value, err)
            return None
