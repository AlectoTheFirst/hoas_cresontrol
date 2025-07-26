"""
Switch platform for CresControl.

This module defines boolean switch entities corresponding to the fan and
various power rails on the CresControl. Each entity exposes the state of
the underlying parameter and allows toggling it on or off. When the user
changes the state in Home Assistant, a write operation is issued via the
client and followed by a refresh of all entities.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    ENTITY_UNAVAILABLE_THRESHOLD,
    STATE_PRESERVATION_DURATION,
    AVAILABILITY_GRACE_PERIOD,
    DEVICE_STATUS_ONLINE,
    DEVICE_STATUS_DEGRADED,
    DEVICE_STATUS_OFFLINE,
)
from .api import CresControlError, CresControlNetworkError, CresControlDeviceError


_LOGGER = logging.getLogger(__name__)


# Define the CresControl switch parameters. Additional switches can be added
# here to expose further boolean parameters as needed.
SWITCH_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "fan:enabled",
        "name": "Fan",
        "icon": "mdi:fan",
        "entity_category": None,  # Primary control
    },
    {
        "key": "switch-12v:enabled",
        "name": "12V Switch",
        "icon": "mdi:electric-switch",
        "entity_category": None,  # Primary control
    },
    {
        "key": "switch-24v-a:enabled",
        "name": "24V Switch A",
        "icon": "mdi:electric-switch",
        "entity_category": None,  # Primary control
    },
    {
        "key": "switch-24v-b:enabled",
        "name": "24V Switch B",
        "icon": "mdi:electric-switch",
        "entity_category": None,  # Primary control
    },
    # Expose enable flags for all analog outputs so they can be turned on/off
    {
        "key": "out-a:enabled",
        "name": "Out A Enabled",
        "icon": "mdi:tune",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    {
        "key": "out-b:enabled",
        "name": "Out B Enabled",
        "icon": "mdi:tune",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    {
        "key": "out-c:enabled",
        "name": "Out C Enabled",
        "icon": "mdi:tune",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    {
        "key": "out-d:enabled",
        "name": "Out D Enabled",
        "icon": "mdi:tune",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    {
        "key": "out-e:enabled",
        "name": "Out E Enabled",
        "icon": "mdi:tune",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    {
        "key": "out-f:enabled",
        "name": "Out F Enabled",
        "icon": "mdi:tune",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    # PWM enable switches for outputs A-B (only A-B support PWM)
    {
        "key": "out-a:pwm-enabled",
        "name": "Out A PWM Enabled",
        "icon": "mdi:toggle-switch",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    {
        "key": "out-b:pwm-enabled",
        "name": "Out B PWM Enabled",
        "icon": "mdi:toggle-switch",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    # PWM enable switches for power rail switches
    {
        "key": "switch-12v:pwm-enabled",
        "name": "12V Switch PWM Enabled",
        "icon": "mdi:toggle-switch",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    {
        "key": "switch-24v-a:pwm-enabled",
        "name": "24V Switch A PWM Enabled",
        "icon": "mdi:toggle-switch",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
    },
    {
        "key": "switch-24v-b:pwm-enabled",
        "name": "24V Switch B PWM Enabled",
        "icon": "mdi:toggle-switch",
        "entity_category": EntityCategory.CONFIG,  # Configuration setting
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
    client = data["client"]
    device_info = data["device_info"]
    entities = [
        CresControlSwitch(coordinator, client, device_info, definition)
        for definition in SWITCH_DEFINITIONS
    ]
    async_add_entities(entities)


class CresControlSwitch(CoordinatorEntity, SwitchEntity):
    """Enhanced representation of a CresControl switch entity with error handling."""

    def __init__(self, coordinator, client, device_info: Dict[str, Any], definition: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._client = client
        self._device_info = device_info
        self._key: str = definition["key"]
        self._attr_name = f"CresControl {definition['name']}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._key}"
        self._attr_icon = definition.get("icon")
        self._attr_entity_category = definition.get("entity_category")
        
        # Enhanced error handling and state preservation
        self._last_known_state: Optional[bool] = None
        self._last_successful_update: Optional[datetime] = None
        self._last_state_change: Optional[datetime] = None
        self._consecutive_failures = 0
        self._grace_period_start: Optional[datetime] = None
        self._last_command_time: Optional[datetime] = None
        self._last_command_success = True

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information to link this entity with the device."""
        return self._device_info

    @property
    def available(self) -> bool:
        """Return if entity is available based on coordinator health and grace period."""
        # Always available if coordinator has recent data
        if self.coordinator.last_update_success:
            # Check coordinator health if available
            if hasattr(self.coordinator, 'health_tracker'):
                coordinator_status = self.coordinator.health_tracker.current_status
                
                # Entity is available if coordinator is online or degraded
                if coordinator_status in [DEVICE_STATUS_ONLINE, DEVICE_STATUS_DEGRADED]:
                    # Reset grace period on successful connection
                    self._grace_period_start = None
                    return True
                
                # Start grace period if coordinator goes offline
                if coordinator_status == DEVICE_STATUS_OFFLINE:
                    if self._grace_period_start is None:
                        self._grace_period_start = dt_util.utcnow()
                        _LOGGER.debug("Starting availability grace period for %s", self._attr_name)
                    
                    # Check if still within grace period
                    grace_elapsed = dt_util.utcnow() - self._grace_period_start
                    if grace_elapsed <= AVAILABILITY_GRACE_PERIOD:
                        _LOGGER.debug(
                            "Switch %s in grace period (%.1fs elapsed)",
                            self._attr_name, grace_elapsed.total_seconds()
                        )
                        return True
                    else:
                        _LOGGER.debug("Switch %s grace period expired", self._attr_name)
                        return False
            
            # Default to available if no health tracker
            return True
        
        # Check how long since last successful update
        if self.coordinator.last_update_success_time:
            time_since_success = dt_util.utcnow() - self.coordinator.last_update_success_time
            return time_since_success <= ENTITY_UNAVAILABLE_THRESHOLD
            
        # No successful updates yet
        return False

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on with enhanced error handling."""
        current_value = self.coordinator.data.get(self._key) if self.coordinator.data else None
        
        if current_value is not None:
            # Parse the current state
            parsed_state = self._parse_state_safely(current_value)
            
            if parsed_state is not None:
                # Update state tracking on successful state retrieval
                if parsed_state != self._last_known_state:
                    self._last_state_change = dt_util.utcnow()
                    _LOGGER.debug(
                        "Switch %s state changed from %s to %s",
                        self._attr_name, self._last_known_state, parsed_state
                    )
                
                self._last_known_state = parsed_state
                self._last_successful_update = dt_util.utcnow()
                self._consecutive_failures = 0
                return parsed_state
        
        # Current value is None or invalid - handle gracefully
        self._consecutive_failures += 1
        
        # Try to preserve last known state during temporary outages
        if self._should_preserve_last_state():
            _LOGGER.debug(
                "Switch %s preserving last known state %s (failures: %d)",
                self._attr_name, self._last_known_state, self._consecutive_failures
            )
            return self._last_known_state
        
        # Log degraded state
        if self._consecutive_failures <= 3:  # Avoid log spam
            _LOGGER.debug(
                "Switch %s state unavailable (failures: %d)",
                self._attr_name, self._consecutive_failures
            )
        
        return None

    def _parse_state_safely(self, value: Any) -> Optional[bool]:
        """Safely parse the switch state with proper error handling."""
        if value is None:
            return None
            
        try:
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                # Handle various string representations of boolean values
                value_lower = value.strip().lower()
                if value_lower in ("true", "t", "1", "on", "yes", "enabled"):
                    return True
                elif value_lower in ("false", "f", "0", "off", "no", "disabled"):
                    return False
                else:
                    _LOGGER.debug(
                        "Switch %s unknown string state '%s'",
                        self._attr_name, value
                    )
                    return None
            elif isinstance(value, (int, float)):
                # Treat non-zero numeric values as True
                return bool(value)
            else:
                _LOGGER.debug(
                    "Switch %s unsupported state type %s: %s",
                    self._attr_name, type(value), value
                )
                return None
                
        except (TypeError, ValueError) as err:
            _LOGGER.debug(
                "Switch %s failed to parse state '%s': %s",
                self._attr_name, value, err
            )
            return None

    def _should_preserve_last_state(self) -> bool:
        """Determine if the last known state should be preserved."""
        # No last state to preserve
        if self._last_known_state is None or self._last_successful_update is None:
            return False
            
        # Check if within preservation window
        time_since_last_success = dt_util.utcnow() - self._last_successful_update
        if time_since_last_success > STATE_PRESERVATION_DURATION:
            return False
            
        # Don't preserve if too many consecutive failures
        if self._consecutive_failures > 5:
            return False
            
        # Check coordinator health for context
        if hasattr(self.coordinator, 'health_tracker'):
            coordinator_status = self.coordinator.health_tracker.current_status
            # Only preserve during degraded or temporary offline states
            return coordinator_status in [DEVICE_STATUS_DEGRADED, DEVICE_STATUS_OFFLINE]
            
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on with enhanced error handling."""
        await self._async_set_state(True, "turn on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off with enhanced error handling."""
        await self._async_set_state(False, "turn off")

    async def _async_set_state(self, target_state: bool, operation: str) -> None:
        """Set switch state with comprehensive error handling and retry logic."""
        _LOGGER.debug("Switch %s attempting to %s", self._attr_name, operation)
        
        # Record command attempt time
        self._last_command_time = dt_util.utcnow()
        
        # Check if device is available for commands
        if not self.available:
            error_msg = f"Switch {self._attr_name} unavailable for {operation}"
            _LOGGER.warning(error_msg)
            raise HomeAssistantError(error_msg)
        
        # Perform the operation with error handling
        max_attempts = 3
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                _LOGGER.debug(
                    "Switch %s %s attempt %d/%d",
                    self._attr_name, operation, attempt + 1, max_attempts
                )
                
                # Send the command
                await self._client.set_value(self._key, target_state)
                
                # Trigger immediate refresh to verify the change
                await self.coordinator.async_request_refresh()
                
                # Mark command as successful
                self._last_command_success = True
                
                _LOGGER.debug("Switch %s %s successful", self._attr_name, operation)
                return
                
            except CresControlNetworkError as err:
                last_exception = err
                _LOGGER.debug(
                    "Switch %s %s network error on attempt %d: %s",
                    self._attr_name, operation, attempt + 1, err
                )
                
                # Wait before retry (except on last attempt)
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Progressive delay
                    
            except CresControlDeviceError as err:
                last_exception = err
                _LOGGER.debug(
                    "Switch %s %s device error on attempt %d: %s",
                    self._attr_name, operation, attempt + 1, err
                )
                
                # Device errors might not benefit from immediate retry
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))  # Longer delay for device errors
                    
            except CresControlError as err:
                last_exception = err
                _LOGGER.debug(
                    "Switch %s %s error on attempt %d: %s",
                    self._attr_name, operation, attempt + 1, err
                )
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    
            except Exception as err:
                last_exception = err
                _LOGGER.error(
                    "Switch %s %s unexpected error on attempt %d: %s",
                    self._attr_name, operation, attempt + 1, err
                )
                break  # Don't retry on unexpected errors
        
        # All attempts failed
        self._last_command_success = False
        error_msg = (
            f"Failed to {operation} switch {self._attr_name} after {max_attempts} attempts: "
            f"{last_exception}"
        )
        
        _LOGGER.error(error_msg)
        raise HomeAssistantError(error_msg) from last_exception

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for diagnostics."""
        attributes = {}
        
        # Add error handling diagnostics if in degraded state
        if self._consecutive_failures > 0:
            attributes.update({
                "consecutive_failures": self._consecutive_failures,
                "last_successful_update": (
                    self._last_successful_update.isoformat()
                    if self._last_successful_update else None
                ),
                "preserving_state": self._should_preserve_last_state(),
            })
        
        # Add command status info
        if self._last_command_time:
            attributes.update({
                "last_command_time": self._last_command_time.isoformat(),
                "last_command_success": self._last_command_success,
            })
            
        # Add coordinator health info if available
        if hasattr(self.coordinator, 'health_tracker'):
            health_info = self.coordinator.health_tracker.get_status_info()
            attributes.update({
                "device_status": health_info.get("status", "unknown"),
                "coordinator_success_rate": f"{health_info.get('success_rate', 0):.2%}",
            })
            
        return attributes
