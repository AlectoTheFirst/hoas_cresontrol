"""
Fan platform for CresControl.

Simplified fan implementation for basic speed control.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up CresControl fan based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    http_client = data["http_client"]
    device_info = data["device_info"]
    
    # Create simplified fan entity
    fan_entity = CresControlFan(coordinator, http_client, device_info)
    async_add_entities([fan_entity])


class CresControlFan(CoordinatorEntity, FanEntity):
    """Simplified CresControl fan entity."""

    def __init__(self, coordinator, http_client, device_info: Dict[str, Any]) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        self._client = http_client
        self._device_info = device_info
        self._attr_name = "CresControl Fan"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_fan"
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        self._attr_speed_count = 100  # Support 0-100% speed control

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information to link this entity with the device."""
        return self._device_info

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        if not self.coordinator.data:
            return False
            
        enabled = self.coordinator.data.get("fan:enabled")
        if enabled is None:
            return False
            
        # Simple state parsing
        try:
            if isinstance(enabled, bool):
                return enabled
            elif isinstance(enabled, str):
                return enabled.lower() in ("true", "1", "on", "enabled")
            elif isinstance(enabled, (int, float)):
                return bool(enabled)
        except (TypeError, ValueError):
            pass
            
        return False

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        if not self.coordinator.data:
            return 0
            
        if not self.is_on:
            return 0
            
        # Get duty cycle or default to 0
        duty_cycle = self.coordinator.data.get("fan:duty-cycle", 0)
        try:
            if isinstance(duty_cycle, str):
                duty_cycle = float(duty_cycle)
            return max(0, min(100, int(round(duty_cycle))))
        except (ValueError, TypeError):
            return 0

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan with optional speed setting."""
        if percentage is None:
            percentage = 50  # Default to 50% speed
            
        try:
            await self._client.set_value("fan:enabled", True)
            if percentage > 0:
                await self._client.set_value("fan:duty-cycle", percentage)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on fan: %s", err)
            raise HomeAssistantError("Failed to turn on fan") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        try:
            await self._client.set_value("fan:enabled", False)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off fan: %s", err)
            raise HomeAssistantError("Failed to turn off fan") from err

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if not (0 <= percentage <= 100):
            return
            
        try:
            if percentage == 0:
                await self._client.set_value("fan:enabled", False)
            else:
                await self._client.set_value("fan:enabled", True)
                await self._client.set_value("fan:duty-cycle", percentage)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set fan percentage: %s", err)
            raise HomeAssistantError("Failed to set fan percentage") from err