"""
Number platform for CresControl.

Analog outputs on the CresControl can be controlled via floating point
values representing volts. This module exposes each output as a number
entity. Users can set the voltage within a specified range and the
integration writes the value back to the device. The range is
conservative (0–10 V) because the CresControl supports a variety of
output drivers; adjust these bounds if your particular setup requires
different values.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.number import NumberEntity
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


# Define analog outputs as number entities. Each definition contains the
# parameter key and a human readable name. Modify min/max if needed.
NUMBER_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "out-a:voltage",
        "name": "Out A Voltage",
        "icon": "mdi:knob",
        "entity_category": EntityCategory.CONFIG,
    },
    {
        "key": "out-b:voltage",
        "name": "Out B Voltage",
        "icon": "mdi:knob",
        "entity_category": EntityCategory.CONFIG,
    },
    {
        "key": "out-c:voltage",
        "name": "Out C Voltage",
        "icon": "mdi:knob",
        "entity_category": EntityCategory.CONFIG,
    },
    {
        "key": "out-d:voltage",
        "name": "Out D Voltage",
        "icon": "mdi:knob",
        "entity_category": EntityCategory.CONFIG,
    },
    {
        "key": "out-e:voltage",
        "name": "Out E Voltage",
        "icon": "mdi:knob",
        "entity_category": EntityCategory.CONFIG,
    },
    {
        "key": "out-f:voltage",
        "name": "Out F Voltage",
        "icon": "mdi:knob",
        "entity_category": EntityCategory.CONFIG,
    },
    # PWM duty cycle controls for outputs A-B (only A-B support PWM)
    {
        "key": "out-a:duty-cycle",
        "name": "Out A Duty Cycle",
        "icon": "mdi:pulse",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 100.0,
        "step": 0.1,
        "unit": "%",
    },
    {
        "key": "out-b:duty-cycle",
        "name": "Out B Duty Cycle",
        "icon": "mdi:pulse",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 100.0,
        "step": 0.1,
        "unit": "%",
    },
    # PWM frequency controls for outputs A-B
    {
        "key": "out-a:pwm-frequency",
        "name": "Out A PWM Frequency",
        "icon": "mdi:sine-wave",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 1000.0,
        "step": 1.0,
        "unit": "Hz",
    },
    {
        "key": "out-b:pwm-frequency",
        "name": "Out B PWM Frequency",
        "icon": "mdi:sine-wave",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 1000.0,
        "step": 1.0,
        "unit": "Hz",
    },
    # PWM duty cycle controls for power rail switches
    {
        "key": "switch-12v:duty-cycle",
        "name": "12V Switch Duty Cycle",
        "icon": "mdi:pulse",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 100.0,
        "step": 0.1,
        "unit": "%",
    },
    {
        "key": "switch-24v-a:duty-cycle",
        "name": "24V Switch A Duty Cycle",
        "icon": "mdi:pulse",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 100.0,
        "step": 0.1,
        "unit": "%",
    },
    {
        "key": "switch-24v-b:duty-cycle",
        "name": "24V Switch B Duty Cycle",
        "icon": "mdi:pulse",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 100.0,
        "step": 0.1,
        "unit": "%",
    },
    # PWM frequency controls for power rail switches
    {
        "key": "switch-12v:pwm-frequency",
        "name": "12V Switch PWM Frequency",
        "icon": "mdi:sine-wave",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 1000.0,
        "step": 1.0,
        "unit": "Hz",
    },
    {
        "key": "switch-24v-a:pwm-frequency",
        "name": "24V Switch A PWM Frequency",
        "icon": "mdi:sine-wave",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 1000.0,
        "step": 1.0,
        "unit": "Hz",
    },
    {
        "key": "switch-24v-b:pwm-frequency",
        "name": "24V Switch B PWM Frequency",
        "icon": "mdi:sine-wave",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 1000.0,
        "step": 1.0,
        "unit": "Hz",
    },
    # Environmental sensor calibration offset controls
    {
        "key": "env:temperature-offset",
        "name": "Temperature Calibration Offset",
        "icon": "mdi:thermometer-lines",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.1,
        "unit": "°C",
    },
    {
        "key": "env:humidity-offset",
        "name": "Humidity Calibration Offset",
        "icon": "mdi:water-percent",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -20.0,
        "max_value": 20.0,
        "step": 0.1,
        "unit": "%",
    },
    {
        "key": "env:co2-offset",
        "name": "CO2 Calibration Offset",
        "icon": "mdi:molecule-co2",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -500.0,
        "max_value": 500.0,
        "step": 1.0,
        "unit": "ppm",
    },
    {
        "key": "env:vpd-offset",
        "name": "VPD Calibration Offset",
        "icon": "mdi:gauge",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -1.0,
        "max_value": 1.0,
        "step": 0.01,
        "unit": "kPa",
    },
    # Environmental sensor calibration factor controls
    {
        "key": "env:temperature-factor",
        "name": "Temperature Calibration Factor",
        "icon": "mdi:thermometer-lines",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.5,
        "max_value": 2.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "env:humidity-factor",
        "name": "Humidity Calibration Factor",
        "icon": "mdi:water-percent",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.5,
        "max_value": 2.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "env:co2-factor",
        "name": "CO2 Calibration Factor",
        "icon": "mdi:molecule-co2",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.5,
        "max_value": 2.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "env:vpd-factor",
        "name": "VPD Calibration Factor",
        "icon": "mdi:gauge",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.5,
        "max_value": 2.0,
        "step": 0.01,
        "unit": None,
    },
    # Environmental threshold controls
    {
        "key": "env:temperature-threshold-min",
        "name": "Temperature Minimum Threshold",
        "icon": "mdi:thermometer-low",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 50.0,
        "step": 0.1,
        "unit": "°C",
    },
    {
        "key": "env:temperature-threshold-max",
        "name": "Temperature Maximum Threshold",
        "icon": "mdi:thermometer-high",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 60.0,
        "step": 0.1,
        "unit": "°C",
    },
    {
        "key": "env:humidity-threshold-min",
        "name": "Humidity Minimum Threshold",
        "icon": "mdi:water-minus",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 90.0,
        "step": 1.0,
        "unit": "%",
    },
    {
        "key": "env:humidity-threshold-max",
        "name": "Humidity Maximum Threshold",
        "icon": "mdi:water-plus",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 10.0,
        "max_value": 100.0,
        "step": 1.0,
        "unit": "%",
    },
    {
        "key": "env:co2-threshold-min",
        "name": "CO2 Minimum Threshold",
        "icon": "mdi:molecule-co2",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 200.0,
        "max_value": 2000.0,
        "step": 10.0,
        "unit": "ppm",
    },
    {
        "key": "env:co2-threshold-max",
        "name": "CO2 Maximum Threshold",
        "icon": "mdi:molecule-co2",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 500.0,
        "max_value": 5000.0,
        "step": 10.0,
        "unit": "ppm",
    },
    {
        "key": "env:vpd-threshold-min",
        "name": "VPD Minimum Threshold",
        "icon": "mdi:gauge-low",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 3.0,
        "step": 0.01,
        "unit": "kPa",
    },
    {
        "key": "env:vpd-threshold-max",
        "name": "VPD Maximum Threshold",
        "icon": "mdi:gauge-full",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.5,
        "max_value": 5.0,
        "step": 0.01,
        "unit": "kPa",
    },
    # Input calibration parameters (from crescontrol-0.2 analysis)
    {
        "key": "in-a:calib-offset",
        "name": "Input A Calibration Offset",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "in-a:calib-factor",
        "name": "Input A Calibration Factor",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.1,
        "max_value": 10.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "in-b:calib-offset",
        "name": "Input B Calibration Offset",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "in-b:calib-factor",
        "name": "Input B Calibration Factor",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.1,
        "max_value": 10.0,
        "step": 0.01,
        "unit": None,
    },
    # Output calibration parameters (from crescontrol-0.2 analysis)
    {
        "key": "out-a:calib-offset",
        "name": "Output A Calibration Offset",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-a:calib-factor",
        "name": "Output A Calibration Factor",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.1,
        "max_value": 10.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "out-b:calib-offset",
        "name": "Output B Calibration Offset",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-b:calib-factor",
        "name": "Output B Calibration Factor",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.1,
        "max_value": 10.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "out-c:calib-offset",
        "name": "Output C Calibration Offset",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-c:calib-factor",
        "name": "Output C Calibration Factor",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.1,
        "max_value": 10.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "out-d:calib-offset",
        "name": "Output D Calibration Offset",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-d:calib-factor",
        "name": "Output D Calibration Factor",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.1,
        "max_value": 10.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "out-e:calib-offset",
        "name": "Output E Calibration Offset",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-e:calib-factor",
        "name": "Output E Calibration Factor",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.1,
        "max_value": 10.0,
        "step": 0.01,
        "unit": None,
    },
    {
        "key": "out-f:calib-offset",
        "name": "Output F Calibration Offset",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": -10.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-f:calib-factor",
        "name": "Output F Calibration Factor",
        "icon": "mdi:tune-vertical",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.1,
        "max_value": 10.0,
        "step": 0.01,
        "unit": None,
    },
    # Output threshold parameters (from crescontrol-0.2 analysis)
    {
        "key": "out-a:threshold",
        "name": "Output A Threshold",
        "icon": "mdi:compare-horizontal",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-b:threshold",
        "name": "Output B Threshold",
        "icon": "mdi:compare-horizontal",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-c:threshold",
        "name": "Output C Threshold",
        "icon": "mdi:compare-horizontal",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-d:threshold",
        "name": "Output D Threshold",
        "icon": "mdi:compare-horizontal",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-e:threshold",
        "name": "Output E Threshold",
        "icon": "mdi:compare-horizontal",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
    },
    {
        "key": "out-f:threshold",
        "name": "Output F Threshold",
        "icon": "mdi:compare-horizontal",
        "entity_category": EntityCategory.CONFIG,
        "min_value": 0.0,
        "max_value": 10.0,
        "step": 0.01,
        "unit": "V",
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
        for definition in NUMBER_DEFINITIONS
    ]
    async_add_entities(entities)


class CresControlNumber(CoordinatorEntity, NumberEntity):
    """Enhanced representation of a CresControl analog output voltage with error handling."""

    def __init__(self, coordinator, client, device_info: Dict[str, Any], definition: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._client = client
        self._device_info = device_info
        self._key: str = definition["key"]
        self._attr_name = f"CresControl {definition['name']}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._key}"
        
        # Use definition values if provided, otherwise conservative voltage defaults
        self._attr_native_min_value = definition.get("min_value", 0.0)
        self._attr_native_max_value = definition.get("max_value", 10.0)
        self._attr_native_step = definition.get("step", 0.01)
        
        # Set unit of measurement from definition or default to volts
        unit = definition.get("unit")
        if unit == "%":
            from homeassistant.const import PERCENTAGE
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif unit == "Hz":
            from homeassistant.const import UnitOfFrequency
            self._attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
        elif unit == "°C":
            from homeassistant.const import UnitOfTemperature
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif unit == "kPa":
            from homeassistant.const import UnitOfPressure
            self._attr_native_unit_of_measurement = UnitOfPressure.KPA
        elif unit == "ppm":
            from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION
            self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
        elif unit is None:
            # No unit of measurement (for calibration factors)
            self._attr_native_unit_of_measurement = None
        else:
            # Default to volts for voltage parameters
            from homeassistant.const import UnitOfElectricPotential
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            
        self._attr_icon = definition.get("icon")
        self._attr_entity_category = definition.get("entity_category")
        
        # Enhanced error handling and state preservation
        self._last_known_value: Optional[float] = None
        self._last_successful_update: Optional[datetime] = None
        self._last_value_change: Optional[datetime] = None
        self._consecutive_failures = 0
        self._grace_period_start: Optional[datetime] = None
        self._last_command_time: Optional[datetime] = None
        self._last_command_success = True
        self._last_set_value: Optional[float] = None

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
                            "Number %s in grace period (%.1fs elapsed)",
                            self._attr_name, grace_elapsed.total_seconds()
                        )
                        return True
                    else:
                        _LOGGER.debug("Number %s grace period expired", self._attr_name)
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
    def native_value(self) -> float | None:
        """Return the current voltage value with enhanced error handling."""
        current_value = self.coordinator.data.get(self._key) if self.coordinator.data else None
        
        if current_value is not None:
            # Parse and validate the current value
            parsed_value = self._parse_value_safely(current_value)
            
            if parsed_value is not None:
                # Update state tracking on successful value retrieval
                if parsed_value != self._last_known_value:
                    self._last_value_change = dt_util.utcnow()
                    _LOGGER.debug(
                        "Number %s value changed from %s to %s",
                        self._attr_name, self._last_known_value, parsed_value
                    )
                
                self._last_known_value = parsed_value
                self._last_successful_update = dt_util.utcnow()
                self._consecutive_failures = 0
                return parsed_value
        
        # Current value is None or invalid - handle gracefully
        self._consecutive_failures += 1
        
        # Try to preserve last known value during temporary outages
        if self._should_preserve_last_value():
            _LOGGER.debug(
                "Number %s preserving last known value %s (failures: %d)",
                self._attr_name, self._last_known_value, self._consecutive_failures
            )
            return self._last_known_value
        
        # Log degraded state
        if self._consecutive_failures <= 3:  # Avoid log spam
            _LOGGER.debug(
                "Number %s value unavailable (failures: %d)",
                self._attr_name, self._consecutive_failures
            )
        
        return None

    def _parse_value_safely(self, value: Any) -> Optional[float]:
        """Safely parse the numeric value with proper error handling."""
        if value is None:
            return None
            
        try:
            if isinstance(value, (int, float)):
                parsed = float(value)
            elif isinstance(value, str):
                # Handle empty or whitespace-only strings
                value = value.strip()
                if not value:
                    return None
                parsed = float(value)
            else:
                _LOGGER.debug(
                    "Number %s unsupported value type %s: %s",
                    self._attr_name, type(value), value
                )
                return None
                
            # Validate reasonable bounds for voltage values
            if not (-50.0 <= parsed <= 50.0):  # Reasonable voltage range
                _LOGGER.warning(
                    "Number %s voltage value %s outside expected range",
                    self._attr_name, parsed
                )
                # Don't return None, but log the warning
                
            return parsed
            
        except (TypeError, ValueError, OverflowError) as err:
            _LOGGER.debug(
                "Number %s failed to parse value '%s': %s",
                self._attr_name, value, err
            )
            return None

    def _should_preserve_last_value(self) -> bool:
        """Determine if the last known value should be preserved."""
        # No last value to preserve
        if self._last_known_value is None or self._last_successful_update is None:
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

    async def async_set_native_value(self, value: float) -> None:
        """Set a new voltage value on the CresControl with enhanced error handling."""
        _LOGGER.debug("Number %s attempting to set value to %s", self._attr_name, value)
        
        # Validate and clamp value within allowed range
        original_value = value
        if value < self._attr_native_min_value:
            value = self._attr_native_min_value
            _LOGGER.debug(
                "Number %s clamping value from %s to minimum %s",
                self._attr_name, original_value, value
            )
        elif value > self._attr_native_max_value:
            value = self._attr_native_max_value
            _LOGGER.debug(
                "Number %s clamping value from %s to maximum %s",
                self._attr_name, original_value, value
            )
        
        # Record command attempt time
        self._last_command_time = dt_util.utcnow()
        self._last_set_value = value
        
        # Check if device is available for commands
        if not self.available:
            error_msg = f"Number {self._attr_name} unavailable for setting value"
            _LOGGER.warning(error_msg)
            raise HomeAssistantError(error_msg)
        
        # Perform the operation with error handling
        max_attempts = 3
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                _LOGGER.debug(
                    "Number %s set value attempt %d/%d: %s",
                    self._attr_name, attempt + 1, max_attempts, value
                )
                
                # Send the command
                await self._client.set_value(self._key, value)
                
                # Trigger immediate refresh to verify the change
                await self.coordinator.async_request_refresh()
                
                # Mark command as successful
                self._last_command_success = True
                
                _LOGGER.debug("Number %s set value successful: %s", self._attr_name, value)
                return
                
            except CresControlNetworkError as err:
                last_exception = err
                _LOGGER.debug(
                    "Number %s set value network error on attempt %d: %s",
                    self._attr_name, attempt + 1, err
                )
                
                # Wait before retry (except on last attempt)
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Progressive delay
                    
            except CresControlDeviceError as err:
                last_exception = err
                _LOGGER.debug(
                    "Number %s set value device error on attempt %d: %s",
                    self._attr_name, attempt + 1, err
                )
                
                # Device errors might not benefit from immediate retry
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))  # Longer delay for device errors
                    
            except CresControlError as err:
                last_exception = err
                _LOGGER.debug(
                    "Number %s set value error on attempt %d: %s",
                    self._attr_name, attempt + 1, err
                )
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    
            except Exception as err:
                last_exception = err
                _LOGGER.error(
                    "Number %s set value unexpected error on attempt %d: %s",
                    self._attr_name, attempt + 1, err
                )
                break  # Don't retry on unexpected errors
        
        # All attempts failed
        self._last_command_success = False
        error_msg = (
            f"Failed to set value {value} for number {self._attr_name} after "
            f"{max_attempts} attempts: {last_exception}"
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
                "preserving_state": self._should_preserve_last_value(),
            })
        
        # Add command status info
        if self._last_command_time:
            attributes.update({
                "last_command_time": self._last_command_time.isoformat(),
                "last_command_success": self._last_command_success,
                "last_set_value": self._last_set_value,
            })
            
        # Add coordinator health info if available
        if hasattr(self.coordinator, 'health_tracker'):
            health_info = self.coordinator.health_tracker.get_status_info()
            attributes.update({
                "device_status": health_info.get("status", "unknown"),
                "coordinator_success_rate": f"{health_info.get('success_rate', 0):.2%}",
            })
            
        return attributes
