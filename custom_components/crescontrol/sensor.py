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
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        if not self.coordinator.data:
            return None
            
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
            
        # Simple value parsing
        try:
            if isinstance(raw_value, str):
                raw_value = raw_value.strip()
                if not raw_value:
                    return None
                    
                # Try to convert to float or int
                if "." in raw_value:
                    return float(raw_value)
                else:
                    return int(raw_value)
            else:
                return raw_value
                
        except (ValueError, TypeError):
            _LOGGER.debug("Failed to parse sensor value for %s: %s", self._key, raw_value)
            return None
