"""
Fan platform for CresControl.

This module defines a fan entity representing the CresControl device's fan
control functionality. The fan entity supports percentage-based speed control,
on/off functionality, and PWM duty cycle management while maintaining
enhanced error handling and security features.

The fan entity provides:
- Percentage-based speed control (0-100%)
- On/off control independent of speed setting
- Minimum duty cycle enforcement for startup reliability
- Speed preset support (off, low, medium, high, maximum)
- Integration with device health monitoring
- Proper state preservation during connection issues
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    FAN_PARAM_ENABLED,
    FAN_PARAM_DUTY_CYCLE,
    FAN_PARAM_DUTY_CYCLE_MIN,
    FAN_PARAM_RPM,
    FAN_DUTY_CYCLE_MIN,
    FAN_DUTY_CYCLE_MAX,
    FAN_DUTY_CYCLE_DEFAULT_MIN,
    FAN_DUTY_CYCLE_TOLERANCE,
    FAN_SPEED_OFF,
    FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM,
    FAN_SPEED_HIGH,
    FAN_SPEED_MAXIMUM,
    FAN_ICON,
    FAN_ICON_OFF,
    ENTITY_UNAVAILABLE_THRESHOLD,
    STATE_PRESERVATION_DURATION,
    AVAILABILITY_GRACE_PERIOD,
    DEVICE_STATUS_ONLINE,
    DEVICE_STATUS_DEGRADED,
    DEVICE_STATUS_OFFLINE,
)
from .api import CresControlError, CresControlNetworkError, CresControlDeviceError


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up CresControl fan based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_info = data["device_info"]
    
    # Create fan entity
    fan_entity = CresControlFan(coordinator, device_info)
    async_add_entities([fan_entity])
    
    _LOGGER.debug("CresControl fan entity %s added", fan_entity.name)


class CresControlFan(CoordinatorEntity, FanEntity):
    """Enhanced CresControl fan entity with comprehensive speed control and error handling."""

    def __init__(self, coordinator, device_info: Dict[str, Any]) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        self._device_info = device_info
        
        # Use a friendly name
        self._attr_name = "CresControl Fan"
        # Unique ID composed of the config entry ID and fan identifier
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_fan"
        
        # Configure supported features
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        
        # Speed settings and presets
        self._attr_speed_count = 100  # Support 0-100% speed control
        self._speed_presets = {
            "off": FAN_SPEED_OFF,
            "low": FAN_SPEED_LOW,
            "medium": FAN_SPEED_MEDIUM,
            "high": FAN_SPEED_HIGH,
            "maximum": FAN_SPEED_MAXIMUM,
        }
        
        # Enhanced error handling and state preservation
        self._last_known_enabled: Optional[bool] = None
        self._last_known_percentage: Optional[int] = None
        self._last_successful_update: Optional[datetime] = None
        self._consecutive_failures = 0
        self._grace_period_start: Optional[datetime] = None
        self._pending_speed_change: Optional[float] = None
        self._last_duty_cycle_min: Optional[float] = None

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
                            "Fan %s in grace period (%.1fs elapsed)",
                            self._attr_name, grace_elapsed.total_seconds()
                        )
                        return True
                    else:
                        _LOGGER.debug("Fan %s grace period expired", self._attr_name)
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
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        current_data = self._get_current_fan_data()
        
        if current_data is None:
            # Use preserved state during outages
            if self._should_preserve_last_state():
                return self._last_known_enabled if self._last_known_enabled is not None else False
            return False
        
        enabled = current_data.get("enabled", False)
        duty_cycle = current_data.get("duty_cycle", 0)
        
        # Fan is considered "on" if enabled and has non-zero duty cycle
        is_on = bool(enabled and duty_cycle > FAN_DUTY_CYCLE_TOLERANCE)
        
        # Update preserved state on successful read
        self._last_known_enabled = is_on
        self._last_successful_update = dt_util.utcnow()
        self._consecutive_failures = 0
        
        return is_on

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        current_data = self._get_current_fan_data()
        
        if current_data is None:
            # Use preserved state during outages
            if self._should_preserve_last_state():
                return self._last_known_percentage
            return 0
        
        enabled = current_data.get("enabled", False)
        duty_cycle = current_data.get("duty_cycle", 0)
        
        # Return 0 if fan is disabled
        if not enabled:
            percentage = 0
        else:
            # Ensure duty cycle is within valid range
            percentage = max(0, min(100, int(round(duty_cycle))))
        
        # Update preserved state on successful read
        self._last_known_percentage = percentage
        self._last_successful_update = dt_util.utcnow()
        self._consecutive_failures = 0
        
        return percentage

    @property
    def icon(self) -> str:
        """Return the icon for the fan."""
        if self.is_on:
            return FAN_ICON
        return FAN_ICON_OFF

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for diagnostics."""
        attributes = {}
        
        # Add current fan data if available
        current_data = self._get_current_fan_data()
        if current_data:
            attributes.update({
                "duty_cycle": current_data.get("duty_cycle", 0),
                "duty_cycle_min": current_data.get("duty_cycle_min", 0),
                "rpm": current_data.get("rpm", 0),
                "raw_enabled": current_data.get("enabled", False),
            })
        
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
        
        # Add pending changes if any
        if self._pending_speed_change is not None:
            attributes["pending_speed_change"] = self._pending_speed_change
            
        # Add coordinator health info if available
        if hasattr(self.coordinator, 'health_tracker'):
            health_info = self.coordinator.health_tracker.get_status_info()
            attributes.update({
                "device_status": health_info.get("status", "unknown"),
                "coordinator_success_rate": f"{health_info.get('success_rate', 0):.2%}",
            })
            
        return attributes

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan with optional speed setting."""
        if preset_mode is not None:
            percentage = self._speed_presets.get(preset_mode.lower())
            if percentage is None:
                _LOGGER.warning("Unknown preset mode: %s", preset_mode)
                return
        
        # If no percentage specified, use minimum duty cycle for reliable startup
        if percentage is None:
            try:
                min_duty_cycle = await self._get_minimum_duty_cycle()
                percentage = max(FAN_SPEED_LOW, min_duty_cycle)
            except CresControlError:
                # Fallback to default minimum if we can't get the device setting
                percentage = FAN_SPEED_LOW
        
        _LOGGER.debug("Turning on fan with percentage: %d%%", percentage)
        
        try:
            self._pending_speed_change = percentage
            
            # Use the API client's fan speed method for atomic operation
            await self.coordinator.client.set_fan_speed(percentage, enable=True)
            
            # Trigger immediate coordinator refresh to update state
            await self.coordinator.async_request_refresh()
            
            self._pending_speed_change = None
            _LOGGER.debug("Fan turned on successfully at %d%%", percentage)
            
        except CresControlError as err:
            self._pending_speed_change = None
            _LOGGER.error("Failed to turn on fan: %s", err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        _LOGGER.debug("Turning off fan")
        
        try:
            self._pending_speed_change = 0
            
            # Use the API client's fan enabled method for safe shutdown
            await self.coordinator.client.set_fan_enabled(False)
            
            # Trigger immediate coordinator refresh to update state
            await self.coordinator.async_request_refresh()
            
            self._pending_speed_change = None
            _LOGGER.debug("Fan turned off successfully")
            
        except CresControlError as err:
            self._pending_speed_change = None
            _LOGGER.error("Failed to turn off fan: %s", err)
            raise

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if not (0 <= percentage <= 100):
            _LOGGER.error("Invalid percentage: %d. Must be between 0 and 100", percentage)
            return
        
        _LOGGER.debug("Setting fan percentage to: %d%%", percentage)
        
        try:
            self._pending_speed_change = percentage
            
            if percentage == 0:
                # Turn off the fan completely
                await self.coordinator.client.set_fan_enabled(False)
            else:
                # Set the speed and enable the fan
                await self.coordinator.client.set_fan_speed(percentage, enable=True)
            
            # Trigger immediate coordinator refresh to update state
            await self.coordinator.async_request_refresh()
            
            self._pending_speed_change = None
            _LOGGER.debug("Fan percentage set successfully to %d%%", percentage)
            
        except CresControlError as err:
            self._pending_speed_change = None
            _LOGGER.error("Failed to set fan percentage: %s", err)
            raise

    def _get_current_fan_data(self) -> Optional[Dict[str, Any]]:
        """Get current fan data from coordinator with error handling."""
        if not self.coordinator.data:
            self._consecutive_failures += 1
            return None
        
        try:
            # Extract fan parameters from coordinator data
            enabled_raw = self.coordinator.data.get(FAN_PARAM_ENABLED)
            duty_cycle_raw = self.coordinator.data.get(FAN_PARAM_DUTY_CYCLE)
            duty_cycle_min_raw = self.coordinator.data.get(FAN_PARAM_DUTY_CYCLE_MIN)
            rpm_raw = self.coordinator.data.get(FAN_PARAM_RPM)
            
            # Parse enabled state
            if enabled_raw in ("1", 1, "true", True, "on", "enabled"):
                enabled = True
            elif enabled_raw in ("0", 0, "false", False, "off", "disabled"):
                enabled = False
            else:
                enabled = False
                if enabled_raw is not None:
                    _LOGGER.debug("Unexpected fan enabled value: %s", enabled_raw)
            
            # Parse duty cycle
            try:
                duty_cycle = float(duty_cycle_raw) if duty_cycle_raw is not None else 0.0
                duty_cycle = max(FAN_DUTY_CYCLE_MIN, min(FAN_DUTY_CYCLE_MAX, duty_cycle))
            except (ValueError, TypeError):
                duty_cycle = 0.0
                if duty_cycle_raw is not None:
                    _LOGGER.debug("Invalid fan duty cycle value: %s", duty_cycle_raw)
            
            # Parse minimum duty cycle
            try:
                duty_cycle_min = float(duty_cycle_min_raw) if duty_cycle_min_raw is not None else FAN_DUTY_CYCLE_DEFAULT_MIN
                duty_cycle_min = max(FAN_DUTY_CYCLE_MIN, min(FAN_DUTY_CYCLE_MAX, duty_cycle_min))
                self._last_duty_cycle_min = duty_cycle_min
            except (ValueError, TypeError):
                duty_cycle_min = self._last_duty_cycle_min or FAN_DUTY_CYCLE_DEFAULT_MIN
                if duty_cycle_min_raw is not None:
                    _LOGGER.debug("Invalid fan minimum duty cycle value: %s", duty_cycle_min_raw)
            
            # Parse RPM
            try:
                rpm = int(float(rpm_raw)) if rpm_raw is not None else 0
                rpm = max(0, rpm)  # RPM cannot be negative
            except (ValueError, TypeError):
                rpm = 0
                if rpm_raw is not None:
                    _LOGGER.debug("Invalid fan RPM value: %s", rpm_raw)
            
            return {
                "enabled": enabled,
                "duty_cycle": duty_cycle,
                "duty_cycle_min": duty_cycle_min,
                "rpm": rpm,
            }
            
        except Exception as err:
            self._consecutive_failures += 1
            _LOGGER.debug("Failed to parse fan data: %s", err)
            return None

    def _should_preserve_last_state(self) -> bool:
        """Determine if the last known state should be preserved."""
        # No last state to preserve
        if (self._last_known_enabled is None and 
            self._last_known_percentage is None and
            self._last_successful_update is None):
            return False
            
        # Check if within preservation window
        if self._last_successful_update:
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

    async def _get_minimum_duty_cycle(self) -> float:
        """Get the minimum duty cycle setting for fan startup reliability."""
        try:
            return await self.coordinator.client.get_fan_duty_cycle_min()
        except CresControlError as err:
            _LOGGER.debug("Failed to get minimum duty cycle, using default: %s", err)
            return FAN_DUTY_CYCLE_DEFAULT_MIN