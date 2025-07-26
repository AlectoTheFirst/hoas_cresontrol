"""
Number platform for CresControl.

Simplified number implementation for voltage control.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


# Core number definitions - reduced to essential voltage controls only
CORE_NUMBERS = [
    {
        "key": "out-a:voltage",
        "name": "Output A Voltage",
        "icon": "mdi:knob",
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
    },
    {
        "key": "out-b:voltage",
        "name": "Output B Voltage",
        "icon": "mdi:knob",
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
    },
    {
        "key": "out-c:voltage",
        "name": "Output C Voltage",
        "icon": "mdi:knob",
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
    },
    {
        "key": "out-d:voltage",
        "name": "Output D Voltage",
        "icon": "mdi:knob",
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
    },
    {
        "key": "out-e:voltage",
        "name": "Output E Voltage",
        "icon": "mdi:knob",
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
    },
    {
        "key": "out-f:voltage",
        "name": "Output F Voltage",
        "icon": "mdi:knob",
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up CresControl number entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]
    device_info = data["device_info"]
    entities = [
        CresControlNumber(coordinator, client, device_info, definition)
        for definition in CORE_NUMBERS
    ]
    async_add_entities(entities)


class CresControlNumber(CoordinatorEntity, NumberEntity):
    """Simplified CresControl number entity for voltage control."""

    def __init__(self, coordinator, client, device_info: Dict[str, Any], definition: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._client = client
        self._device_info = device_info
        self._key: str = definition["key"]
        self._attr_name = f"CresControl {definition['name']}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._key}"
        self._attr_native_min_value = definition.get("min_value", 0.0)
        self._attr_native_max_value = definition.get("max_value", 10.0)
        self._attr_native_step = definition.get("step", 0.01)
        self._attr_icon = definition.get("icon")
        
        # Default to volts for voltage parameters
        from homeassistant.const import UnitOfElectricPotential
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information to link this entity with the device."""
        return self._device_info

    @property
    def native_value(self) -> float | None:
        """Return the current voltage value."""
        if not self.coordinator.data:
            return None
            
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
            
        # Simple value parsing
        try:
            if isinstance(raw_value, (int, float)):
                return float(raw_value)
            elif isinstance(raw_value, str):
                raw_value = raw_value.strip()
                if not raw_value:
                    return None
                return float(raw_value)
        except (ValueError, TypeError):
            _LOGGER.debug("Failed to parse number value for %s: %s", self._key, raw_value)
            
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set a new voltage value on the CresControl."""
        # Clamp value within allowed range
        if value < self._attr_native_min_value:
            value = self._attr_native_min_value
        elif value > self._attr_native_max_value:
            value = self._attr_native_max_value
        
        try:
            await self._client.set_value(self._key, value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set value for %s: %s", self._attr_name, err)
            raise HomeAssistantError(f"Failed to set {self._attr_name}") from err

