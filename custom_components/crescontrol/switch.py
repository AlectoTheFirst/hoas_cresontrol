"""
Switch platform for CresControl.

Simplified switch implementation focusing on core controls only.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


# Core switch definitions - only parameters confirmed to exist on device
CORE_SWITCHES = [
    {
        "key": "fan:enabled",
        "name": "Fan",
        "icon": "mdi:fan",
    },
    {
        "key": "out-a:enabled",
        "name": "Output A Enabled",
        "icon": "mdi:tune",
    },
    {
        "key": "out-b:enabled",
        "name": "Output B Enabled",
        "icon": "mdi:tune",
    },
    {
        "key": "out-c:enabled",
        "name": "Output C Enabled",
        "icon": "mdi:tune",
    },
    {
        "key": "out-d:enabled",
        "name": "Output D Enabled",
        "icon": "mdi:tune",
    },
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up CresControl switches based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    http_client = data["http_client"]
    device_info = data["device_info"]
    entities = [
        CresControlSwitch(coordinator, http_client, device_info, definition)
        for definition in CORE_SWITCHES
    ]
    async_add_entities(entities)


class CresControlSwitch(CoordinatorEntity, SwitchEntity):
    """Simplified CresControl switch entity."""

    def __init__(self, coordinator, client, device_info: Dict[str, Any], definition: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._client = client
        self._device_info = device_info
        self._key: str = definition["key"]
        self._attr_name = f"CresControl {definition['name']}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._key}"
        self._attr_icon = definition.get("icon")

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information to link this entity with the device."""
        return self._device_info

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if not self.coordinator.data:
            return None
            
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
            
        # Simple state parsing
        try:
            if isinstance(raw_value, bool):
                return raw_value
            elif isinstance(raw_value, str):
                value_lower = raw_value.strip().lower()
                if value_lower in ("true", "1", "on", "enabled"):
                    return True
                elif value_lower in ("false", "0", "off", "disabled"):
                    return False
            elif isinstance(raw_value, (int, float)):
                return bool(raw_value)
        except (TypeError, ValueError):
            _LOGGER.debug("Failed to parse switch state for %s: %s", self._key, raw_value)
            
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            # Use "1" for on state as confirmed by WebSocket testing
            await self._client.set_value(self._key, "1")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on switch %s: %s", self._attr_name, err)
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            # Use "0" for off state as confirmed by WebSocket testing
            await self._client.set_value(self._key, "0")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off switch %s: %s", self._attr_name, err)
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}") from err
