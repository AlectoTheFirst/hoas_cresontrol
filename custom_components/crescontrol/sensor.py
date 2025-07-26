"""
Sensor platform for CresControl.

This module defines sensors representing the analog inputs (voltage readings)
and the fan RPM of a CresControl device. These sensors rely on the
DataUpdateCoordinator defined in ``__init__.py`` to fetch their values
periodically. The raw string values returned by the device are cast to
appropriate numeric types by the ``native_value`` property.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.const import (
    UnitOfElectricPotential,
    REVOLUTIONS_PER_MINUTE,
    UnitOfTemperature,
    PERCENTAGE,
    UnitOfPressure,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ENTITY_UNAVAILABLE_THRESHOLD,
    STATE_PRESERVATION_DURATION,
    AVAILABILITY_GRACE_PERIOD,
    DEVICE_STATUS_ONLINE,
    DEVICE_STATUS_DEGRADED,
    DEVICE_STATUS_OFFLINE,
)


_LOGGER = logging.getLogger(__name__)


# Define the sensors we want to expose. Each entry maps a CresControl
# parameter to a set of entity attributes. Additional sensors can be added
# here without modifying the rest of the integration.
SENSOR_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "in-a:voltage",
        "name": "In A Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:lightning-bolt",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "in-b:voltage",
        "name": "In B Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:lightning-bolt",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "fan:rpm",
        "name": "Fan RPM",
        "unit": REVOLUTIONS_PER_MINUTE,
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:fan",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    # Environmental sensors for crescontrol-0.2 parity
    {
        "key": "env:temperature",
        "name": "Temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer",
        "entity_category": None,
    },
    {
        "key": "env:humidity",
        "name": "Humidity",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-percent",
        "entity_category": None,
    },
    {
        "key": "env:vpd",
        "name": "VPD (Vapor Pressure Deficit)",
        "unit": UnitOfPressure.KPA,
        "device_class": None,  # No standard device class for VPD
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:gauge",
        "entity_category": None,
    },
    {
        "key": "env:co2",
        "name": "CO2 Concentration",
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:molecule-co2",
        "entity_category": None,
    },
]

# System diagnostic sensors for CresControl device monitoring
SYSTEM_SENSOR_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "type",
        "name": "Device Type",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:chip",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:cpu-id",
        "name": "CPU ID",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:memory",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:reset-cause",
        "name": "Reset Cause",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:restart",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:frequency",
        "name": "System Frequency",
        "unit": "MHz",
        "device_class": SensorDeviceClass.FREQUENCY,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sine-wave",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:heap:size",
        "name": "Heap Size",
        "unit": "bytes",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:heap:free",
        "name": "Free Heap",
        "unit": "bytes",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:heap:largest-block",
        "name": "Largest Heap Block",
        "unit": "bytes",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:heap:watermark",
        "name": "Heap Watermark",
        "unit": "bytes",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:debugging-enabled",
        "name": "Debugging Enabled",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:bug",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:rescue-mode",
        "name": "Rescue Mode",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:lifebuoy",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:serial:enabled",
        "name": "Serial Enabled",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:serial-port",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "system:serial:baudrate",
        "name": "Serial Baudrate",
        "unit": "bps",
        "device_class": SensorDeviceClass.DATA_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:speedometer",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
]

# Diagnostic sensors for connection health monitoring
DIAGNOSTIC_SENSOR_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "connection_status",
        "name": "Connection Status",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:connection",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "success_rate",
        "name": "Success Rate",
        "unit": "%",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:percent",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "consecutive_failures",
        "name": "Consecutive Failures",
        "unit": None,
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:alert-octagon",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "network_timeout_multiplier",
        "name": "Network Timeout Multiplier",
        "unit": None,
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:timer",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "last_error_type",
        "name": "Last Error Type",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:alert",
        "entity_category": EntityCategory.DIAGNOSTIC,
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
    
    # Create regular sensor entities
    entities = [
        CresControlSensor(coordinator, device_info, definition) for definition in SENSOR_DEFINITIONS
    ]
    
    # Add system diagnostic sensor entities
    system_entities = [
        CresControlSensor(coordinator, device_info, definition)
        for definition in SYSTEM_SENSOR_DEFINITIONS
    ]
    
    # Add diagnostic sensor entities for connection health monitoring
    diagnostic_entities = [
        CresControlDiagnosticSensor(coordinator, device_info, definition)
        for definition in DIAGNOSTIC_SENSOR_DEFINITIONS
    ]
    
    entities.extend(system_entities)
    entities.extend(diagnostic_entities)
    async_add_entities(entities)


class CresControlSensor(CoordinatorEntity, SensorEntity):
    """Enhanced representation of a CresControl sensor entity with error handling."""

    def __init__(self, coordinator, device_info: Dict[str, Any], definition: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._device_info = device_info
        self._key: str = definition["key"]
        # Use a friendly name prefixed with the integration name
        self._attr_name = f"CresControl {definition['name']}"
        # Unique ID composed of the config entry ID and parameter key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._key}"
        self._attr_native_unit_of_measurement = definition.get("unit")
        self._attr_device_class = definition.get("device_class")
        self._attr_state_class = definition.get("state_class")
        self._attr_icon = definition.get("icon")
        self._attr_entity_category = definition.get("entity_category")
        
        # Enhanced error handling and state preservation
        self._last_known_value: Any = None
        self._last_successful_update: Optional[datetime] = None
        self._last_value_change: Optional[datetime] = None
        self._consecutive_failures = 0
        self._grace_period_start: Optional[datetime] = None

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
                            "Entity %s in grace period (%.1fs elapsed)",
                            self._attr_name, grace_elapsed.total_seconds()
                        )
                        return True
                    else:
                        _LOGGER.debug("Entity %s grace period expired", self._attr_name)
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
    def native_value(self) -> Any:
        """Return the native value of the sensor with enhanced error handling."""
        current_value = self.coordinator.data.get(self._key) if self.coordinator.data else None
        
        if current_value is not None:
            # Parse and validate the current value
            parsed_value = self._parse_value_safely(current_value)
            
            if parsed_value is not None:
                # Update state tracking on successful value retrieval
                if parsed_value != self._last_known_value:
                    self._last_value_change = dt_util.utcnow()
                    _LOGGER.debug(
                        "Sensor %s value changed from %s to %s",
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
                "Sensor %s preserving last known value %s (failures: %d)",
                self._attr_name, self._last_known_value, self._consecutive_failures
            )
            return self._last_known_value
        
        # Log degraded state
        if self._consecutive_failures <= 3:  # Avoid log spam
            _LOGGER.debug(
                "Sensor %s value unavailable (failures: %d)",
                self._attr_name, self._consecutive_failures
            )
        
        return None

    def _parse_value_safely(self, value: Any) -> Any:
        """Safely parse the sensor value with proper error handling."""
        if value is None:
            return None
            
        # Convert string values to appropriate numeric types
        try:
            if isinstance(value, str):
                # Handle empty or whitespace-only strings
                value = value.strip()
                if not value:
                    return None
                    
                # Try to cast to float or int based on content
                if "." in value:
                    parsed = float(value)
                    # Validate reasonable bounds for sensor values
                    if self._attr_device_class == SensorDeviceClass.VOLTAGE:
                        if not (-50.0 <= parsed <= 50.0):  # Reasonable voltage range
                            _LOGGER.warning(
                                "Sensor %s voltage value %s outside expected range",
                                self._attr_name, parsed
                            )
                    elif self._attr_device_class == SensorDeviceClass.TEMPERATURE:
                        if not (-50.0 <= parsed <= 100.0):  # Reasonable temperature range for grow environments
                            _LOGGER.warning(
                                "Sensor %s temperature value %s outside expected range (-50°C to 100°C)",
                                self._attr_name, parsed
                            )
                    elif self._attr_device_class == SensorDeviceClass.HUMIDITY:
                        if not (0.0 <= parsed <= 100.0):  # Humidity percentage range
                            _LOGGER.warning(
                                "Sensor %s humidity value %s outside expected range (0% to 100%)",
                                self._attr_name, parsed
                            )
                    elif self._attr_device_class == SensorDeviceClass.CO2:
                        if not (0.0 <= parsed <= 10000.0):  # Reasonable CO2 range in ppm
                            _LOGGER.warning(
                                "Sensor %s CO2 value %s outside expected range (0 to 10000 ppm)",
                                self._attr_name, parsed
                            )
                    elif "vpd" in self._key.lower():
                        if not (0.0 <= parsed <= 10.0):  # Reasonable VPD range in kPa
                            _LOGGER.warning(
                                "Sensor %s VPD value %s outside expected range (0 to 10 kPa)",
                                self._attr_name, parsed
                            )
                    return parsed
                else:
                    parsed = int(value)
                    # Validate reasonable bounds for RPM
                    if "rpm" in self._key.lower():
                        if not (0 <= parsed <= 10000):  # Reasonable RPM range
                            _LOGGER.warning(
                                "Sensor %s RPM value %s outside expected range",
                                self._attr_name, parsed
                            )
                    return parsed
            else:
                # Value is already numeric or other type
                return value
                
        except (TypeError, ValueError, OverflowError) as err:
            _LOGGER.debug(
                "Sensor %s failed to parse value '%s': %s",
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
            
        # Add coordinator health info if available
        if hasattr(self.coordinator, 'health_tracker'):
            health_info = self.coordinator.health_tracker.get_status_info()
            attributes.update({
                "device_status": health_info.get("status", "unknown"),
                "coordinator_success_rate": f"{health_info.get('success_rate', 0):.2%}",
            })
            
        return attributes


class CresControlDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor for CresControl connection health monitoring."""

    def __init__(self, coordinator, device_info: Dict[str, Any], definition: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._device_info = device_info
        self._key: str = definition["key"]
        # Use a friendly name prefixed with the integration name
        self._attr_name = f"CresControl {definition['name']}"
        # Unique ID composed of the config entry ID and parameter key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_diag_{self._key}"
        self._attr_native_unit_of_measurement = definition.get("unit")
        self._attr_device_class = definition.get("device_class")
        self._attr_state_class = definition.get("state_class")
        self._attr_icon = definition.get("icon")
        self._attr_entity_category = definition.get("entity_category")
        
        # Always available for diagnostic purposes
        self._attr_available = True

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information to link this entity with the device."""
        return self._device_info

    @property
    def available(self) -> bool:
        """Diagnostic sensors are always available to report health status."""
        return True

    @property
    def native_value(self) -> Any:
        """Return the diagnostic value based on the sensor key."""
        # Get health information from coordinator if available
        if hasattr(self.coordinator, 'get_health_info'):
            health_info = self.coordinator.get_health_info()
        else:
            health_info = {}
            
        # Get network status from client if available
        network_status = {}
        if hasattr(self.coordinator, 'client') and hasattr(self.coordinator.client, 'get_network_status'):
            try:
                network_status = self.coordinator.client.get_network_status()
            except Exception:
                pass  # Silently handle errors for diagnostic sensors
        
        # Return appropriate value based on sensor key
        if self._key == "connection_status":
            return health_info.get("status", "unknown")
            
        elif self._key == "success_rate":
            success_rate = health_info.get("success_rate", 0)
            return round(success_rate * 100, 2)  # Convert to percentage
            
        elif self._key == "consecutive_failures":
            return health_info.get("consecutive_failures", 0)
            
        elif self._key == "network_timeout_multiplier":
            return network_status.get("timeout_multiplier", 1.0)
            
        elif self._key == "last_error_type":
            # Get the most recent error type from error history
            if hasattr(self.coordinator, 'health_tracker'):
                error_history = self.coordinator.health_tracker.error_history
                if error_history:
                    return error_history[-1][1]  # Return the error type of the most recent error
            return "none"
            
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return comprehensive diagnostic information."""
        attributes = {}
        
        # Add coordinator health info if available
        if hasattr(self.coordinator, 'get_health_info'):
            health_info = self.coordinator.get_health_info()
            attributes.update({
                "health_info": health_info,
                "last_update_success": self.coordinator.last_update_success,
                "update_interval": health_info.get("update_interval", "unknown"),
                "degraded_polling": health_info.get("degraded_polling", False),
            })
            
        # Add network status if available
        if hasattr(self.coordinator, 'client') and hasattr(self.coordinator.client, 'get_network_status'):
            try:
                network_status = self.coordinator.client.get_network_status()
                attributes.update({
                    "network_status": network_status,
                    "base_timeout": network_status.get("base_timeout", "unknown"),
                    "current_timeout": network_status.get("current_timeout", "unknown"),
                })
            except Exception:
                pass  # Silently handle errors for diagnostic sensors
                
        # Add coordinator timing info
        if hasattr(self.coordinator, 'last_update_success_time') and self.coordinator.last_update_success_time:
            time_since_success = dt_util.utcnow() - self.coordinator.last_update_success_time
            attributes["time_since_last_success"] = f"{time_since_success.total_seconds():.1f}s"
            
        return attributes
