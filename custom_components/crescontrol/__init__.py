"""
Home Assistant integration for CresControl controllers.

This integration exposes the CresControl device to Home Assistant by
providing sensors, switches and numeric controls for the analog outputs,
fan and auxiliary switches. Communication with the device is done via
HTTP requests to its built‑in API. Configuration is performed via a
config flow which asks only for the device hostname or IP address.

After a successful setup, the integration uses a DataUpdateCoordinator
to poll the device at regular intervals (default every 10 seconds).
Entities subscribe to the coordinator to receive updates without
performing their own HTTP requests. When a user changes a state from
Home Assistant, the integration writes the corresponding parameter to
the device and triggers an immediate refresh to reflect the new state.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .api import CresControlClient, CresControlError, CresControlNetworkError, CresControlDeviceError
from .websocket_client import CresControlWebSocketClient, CresControlWebSocketError
from .hybrid_coordinator import CresControlHybridCoordinator
from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL,
    CONF_WEBSOCKET_ENABLED,
    CONF_WEBSOCKET_PORT,
    CONF_WEBSOCKET_PATH,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DEFAULT_WEBSOCKET_ENABLED,
    DEFAULT_WEBSOCKET_PORT,
    DEFAULT_WEBSOCKET_PATH,
    RETRY_MAX_ATTEMPTS,
    RETRY_INITIAL_DELAY,
    RETRY_BACKOFF_MULTIPLIER,
    RETRY_MAX_DELAY,
    RETRY_JITTER_MAX,
    HEALTH_FAILURE_THRESHOLD,
    HEALTH_RECOVERY_THRESHOLD,
    HEALTH_DEGRADED_UPDATE_INTERVAL,
    ERROR_PATTERN_WINDOW,
    ERROR_PATTERN_THRESHOLD,
    ERROR_RECOVERY_COOLDOWN,
    DEVICE_STATUS_ONLINE,
    DEVICE_STATUS_OFFLINE,
    DEVICE_STATUS_DEGRADED,
    DEVICE_STATUS_UNKNOWN,
    ERROR_SEVERITY_LOW,
    ERROR_SEVERITY_MEDIUM,
    ERROR_SEVERITY_HIGH,
    ERROR_SEVERITY_CRITICAL,
    WEBSOCKET_STATUS_CONNECTED,
    WEBSOCKET_STATUS_DISCONNECTED,
    WEBSOCKET_FALLBACK_TO_HTTP,
)


_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number", "fan"]


class CresControlHealthTracker:
    """Track device health and connection patterns."""
    
    def __init__(self) -> None:
        """Initialize health tracker."""
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.total_failures = 0
        self.total_requests = 0
        self.last_success_time: Optional[datetime] = None
        self.last_failure_time: Optional[datetime] = None
        self.error_history: list[tuple[datetime, str]] = []
        self.current_status = DEVICE_STATUS_UNKNOWN
        
    def record_success(self) -> None:
        """Record a successful operation."""
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.total_requests += 1
        self.last_success_time = dt_util.utcnow()
        
        # Update status based on recovery threshold
        if (self.current_status != DEVICE_STATUS_ONLINE and
            self.consecutive_successes >= HEALTH_RECOVERY_THRESHOLD):
            _LOGGER.info("CresControl device recovered, marking as online")
            self.current_status = DEVICE_STATUS_ONLINE
    
    def record_failure(self, error_type: str) -> None:
        """Record a failed operation."""
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_requests += 1
        self.last_failure_time = dt_util.utcnow()
        
        # Add to error history for pattern analysis
        self.error_history.append((dt_util.utcnow(), error_type))
        self._cleanup_old_errors()
        
        # Update status based on failure threshold
        if (self.current_status != DEVICE_STATUS_OFFLINE and
            self.consecutive_failures >= HEALTH_FAILURE_THRESHOLD):
            _LOGGER.warning(
                "CresControl device marked as offline after %d consecutive failures",
                self.consecutive_failures
            )
            self.current_status = DEVICE_STATUS_OFFLINE
        elif self.consecutive_failures > 1 and self.current_status == DEVICE_STATUS_ONLINE:
            _LOGGER.info("CresControl device experiencing issues, marking as degraded")
            self.current_status = DEVICE_STATUS_DEGRADED
    
    def _cleanup_old_errors(self) -> None:
        """Remove errors outside the tracking window."""
        cutoff_time = dt_util.utcnow() - ERROR_PATTERN_WINDOW
        self.error_history = [
            (timestamp, error_type)
            for timestamp, error_type in self.error_history
            if timestamp > cutoff_time
        ]
    
    def get_error_pattern_severity(self) -> str:
        """Analyze error patterns and return severity level."""
        self._cleanup_old_errors()
        recent_errors = len(self.error_history)
        
        if recent_errors >= ERROR_PATTERN_THRESHOLD:
            if self.consecutive_failures >= HEALTH_FAILURE_THRESHOLD:
                return ERROR_SEVERITY_CRITICAL
            return ERROR_SEVERITY_HIGH
        elif recent_errors >= ERROR_PATTERN_THRESHOLD // 2:
            return ERROR_SEVERITY_MEDIUM
        elif recent_errors > 0:
            return ERROR_SEVERITY_LOW
        return ERROR_SEVERITY_LOW
    
    def should_use_degraded_polling(self) -> bool:
        """Determine if degraded polling should be used."""
        return (self.current_status in [DEVICE_STATUS_DEGRADED, DEVICE_STATUS_OFFLINE] or
                self.get_error_pattern_severity() in [ERROR_SEVERITY_HIGH, ERROR_SEVERITY_CRITICAL])
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get comprehensive status information."""
        return {
            "status": self.current_status,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_failures": self.total_failures,
            "total_requests": self.total_requests,
            "success_rate": (self.total_requests - self.total_failures) / max(self.total_requests, 1),
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "recent_errors": len(self.error_history),
            "error_severity": self.get_error_pattern_severity(),
        }


class CresControlCoordinator(DataUpdateCoordinator):
    """Enhanced coordinator with error recovery, health monitoring, and WebSocket support."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        client: CresControlClient,
        host: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="CresControl data",
            update_method=self._async_update_data,
            update_interval=update_interval,
        )
    
    def _setup_websocket_handlers(self) -> None:
        """Set up WebSocket handlers for real-time updates."""
        if not self.client.websocket_enabled:
            return
            
        # Add data handler for WebSocket updates
        self.client.add_websocket_data_handler(self._handle_websocket_data)
        
        _LOGGER.debug("WebSocket handlers configured for coordinator")
    
    async def _handle_websocket_data(self, data: Dict[str, Any]) -> None:
        """Handle incoming WebSocket data updates.
        
        Parameters
        ----------
        data: Dict[str, Any]
            WebSocket data update from the device.
        """
        if not data:
            return
            
        _LOGGER.debug("Received WebSocket data update: %s", data)
        
        # Update internal state
        self._websocket_last_data_time = dt_util.utcnow()
        self._websocket_connected = True
        
        # Process the data and update coordinator
        processed_data = self._process_websocket_data(data)
        if processed_data:
            # Store the data and notify listeners
            self._cached_data = processed_data
            self._last_successful_data_time = dt_util.utcnow()
            
            # Update health tracker for WebSocket success
            self.health_tracker.record_success()
            
            # Notify all listeners asynchronously
            self.async_set_updated_data(processed_data)
    
    def _process_websocket_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process WebSocket data into the expected format.
        
        Parameters
        ----------
        data: Dict[str, Any]
            Raw WebSocket data from device.
            
        Returns
        -------
        Optional[Dict[str, Any]]
            Processed data in coordinator format, or None if invalid.
        """
        # The WebSocket data should already be in the same format as HTTP responses
        # since both come from the same device API
        if isinstance(data, dict):
            return data
            
        _LOGGER.warning("Invalid WebSocket data format: %s", type(data))
        return None
    
    async def _ensure_websocket_subscription(self) -> None:
        """Ensure WebSocket subscription is active."""
        if not self._websocket_enabled or not self.client.websocket_connected:
            return
            
        if self._websocket_subscription_active:
            return
            
        try:
            # Use the device's subscription API to get real-time updates
            await self.client.send_websocket_command("subscription:subscribe")
            self._websocket_subscription_active = True
            _LOGGER.info("WebSocket subscription activated for %s", self.host)
            
        except Exception as err:
            _LOGGER.warning("Failed to activate WebSocket subscription: %s", err)
            self._websocket_subscription_active = False
    
    async def _disable_websocket_subscription(self) -> None:
        """Disable WebSocket subscription."""
        if not self._websocket_subscription_active:
            return
            
        try:
            await self.client.send_websocket_command("subscription:unsubscribe")
            self._websocket_subscription_active = False
            _LOGGER.debug("WebSocket subscription deactivated for %s", self.host)
            
        except Exception as err:
            _LOGGER.warning("Failed to deactivate WebSocket subscription: %s", err)
    
    def _should_use_websocket_data(self) -> bool:
        """Determine if we should rely on WebSocket data instead of HTTP polling.
        
        Returns
        -------
        bool
            True if WebSocket data is recent and reliable.
        """
        if not self._websocket_enabled or not self._websocket_connected:
            return False
            
        if not self._websocket_last_data_time:
            return False
            
        # Consider WebSocket data recent if it's within 2x the normal update interval
        max_age = self._base_update_interval * 2
        age = dt_util.utcnow() - self._websocket_last_data_time
        
        return age <= max_age
    
    def _get_adaptive_update_interval(self) -> timedelta:
        """Get adaptive update interval based on WebSocket connectivity.
        
        Returns
        -------
        timedelta
            Appropriate update interval based on current state.
        """
        if self._websocket_enabled and self._websocket_connected and self._should_use_websocket_data():
            # Reduce HTTP polling frequency when WebSocket is working
            return self._base_update_interval * 3
        
        return self._base_update_interval
        
    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from CresControl with enhanced error handling and WebSocket integration."""
        # Try to setup WebSocket if enabled and not connected
        if self._websocket_enabled and not self.client.websocket_connected:
            try:
                await self.client.enable_websocket()
                await self._ensure_websocket_subscription()
                _LOGGER.info("WebSocket enabled for %s", self.host)
            except Exception as err:
                _LOGGER.warning("Failed to enable WebSocket for %s: %s", self.host, err)
                if not WEBSOCKET_FALLBACK_TO_HTTP:
                    raise
        
        # Update polling interval based on WebSocket status
        adaptive_interval = self._get_adaptive_update_interval()
        if self.update_interval != adaptive_interval:
            self.update_interval = adaptive_interval
            _LOGGER.debug("Adjusted update interval to %s based on WebSocket status", adaptive_interval)
        
        # If WebSocket is providing recent data, we can skip HTTP polling
        if self._should_use_websocket_data() and self._cached_data:
            _LOGGER.debug("Using recent WebSocket data instead of HTTP polling")
            return self._cached_data
        from .const import (
            PWM_PARAM_OUT_A_ENABLED, PWM_PARAM_OUT_B_ENABLED,
            PWM_PARAM_OUT_A_DUTY_CYCLE, PWM_PARAM_OUT_B_DUTY_CYCLE,
            PWM_PARAM_OUT_A_FREQUENCY, PWM_PARAM_OUT_B_FREQUENCY,
            PWM_PARAM_SWITCH_12V_ENABLED, PWM_PARAM_SWITCH_24V_A_ENABLED, PWM_PARAM_SWITCH_24V_B_ENABLED,
            PWM_PARAM_SWITCH_12V_DUTY_CYCLE, PWM_PARAM_SWITCH_24V_A_DUTY_CYCLE, PWM_PARAM_SWITCH_24V_B_DUTY_CYCLE,
            PWM_PARAM_SWITCH_12V_FREQUENCY, PWM_PARAM_SWITCH_24V_A_FREQUENCY, PWM_PARAM_SWITCH_24V_B_FREQUENCY,
        )
        
        commands = [
            # Analog inputs
            "in-a:voltage",
            "in-b:voltage",
            # Fan comprehensive data
            "fan:enabled",
            "fan:duty-cycle",
            "fan:duty-cycle-min",
            "fan:rpm",
            # Auxiliary switches (12 V, 24 V A/B) - basic state
            "switch-12v:enabled",
            "switch-24v-a:enabled",
            "switch-24v-b:enabled",
            # PWM parameters for switches
            PWM_PARAM_SWITCH_12V_ENABLED, PWM_PARAM_SWITCH_12V_DUTY_CYCLE, PWM_PARAM_SWITCH_12V_FREQUENCY,
            PWM_PARAM_SWITCH_24V_A_ENABLED, PWM_PARAM_SWITCH_24V_A_DUTY_CYCLE, PWM_PARAM_SWITCH_24V_A_FREQUENCY,
            PWM_PARAM_SWITCH_24V_B_ENABLED, PWM_PARAM_SWITCH_24V_B_DUTY_CYCLE, PWM_PARAM_SWITCH_24V_B_FREQUENCY,
            # Analog outputs state and voltage (A–F)
            "out-a:enabled", "out-a:voltage",
            "out-b:enabled", "out-b:voltage",
            "out-c:enabled", "out-c:voltage",
            "out-d:enabled", "out-d:voltage",
            "out-e:enabled", "out-e:voltage",
            "out-f:enabled", "out-f:voltage",
            # PWM parameters for outputs A-B (only A-B support PWM)
            PWM_PARAM_OUT_A_ENABLED, PWM_PARAM_OUT_A_DUTY_CYCLE, PWM_PARAM_OUT_A_FREQUENCY,
            PWM_PARAM_OUT_B_ENABLED, PWM_PARAM_OUT_B_DUTY_CYCLE, PWM_PARAM_OUT_B_FREQUENCY,
        ]
        
        # Attempt to fetch data with retry logic
        last_exception = None
        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                _LOGGER.debug(
                    "CresControl HTTP data fetch attempt %d/%d for %s",
                    attempt + 1, RETRY_MAX_ATTEMPTS, self.host
                )
                
                data = await self.client.send_commands(commands)
                
                # Success - update health tracking
                self.health_tracker.record_success()
                self._cached_data = data
                self._last_successful_data_time = dt_util.utcnow()
                
                # Restore normal polling if we were in degraded mode
                if self.health_tracker.current_status in [DEVICE_STATUS_DEGRADED, DEVICE_STATUS_OFFLINE]:
                    await self._restore_normal_polling()
                
                _LOGGER.debug("CresControl data fetch successful on attempt %d", attempt + 1)
                return data
                
            except CresControlNetworkError as err:
                last_exception = err
                error_type = "network"
                self.health_tracker.record_failure(error_type)
                
                _LOGGER.debug(
                    "CresControl network error on attempt %d/%d: %s",
                    attempt + 1, RETRY_MAX_ATTEMPTS, err
                )
                
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    await self._wait_with_backoff(attempt)
                    
            except CresControlDeviceError as err:
                last_exception = err
                error_type = "device"
                self.health_tracker.record_failure(error_type)
                
                _LOGGER.debug(
                    "CresControl device error on attempt %d/%d: %s",
                    attempt + 1, RETRY_MAX_ATTEMPTS, err
                )
                
                # Device errors might not benefit from immediate retry
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    await self._wait_with_backoff(attempt, multiplier=1.5)
                    
            except Exception as err:
                last_exception = err
                error_type = "unknown"
                self.health_tracker.record_failure(error_type)
                
                _LOGGER.debug(
                    "CresControl unexpected error on attempt %d/%d: %s",
                    attempt + 1, RETRY_MAX_ATTEMPTS, err
                )
                
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    await self._wait_with_backoff(attempt)
        
        # All attempts failed - handle graceful degradation
        await self._handle_persistent_failure(last_exception)
        
        # Try to return cached data if available and recent
        if self._should_use_cached_data():
            _LOGGER.info(
                "CresControl using cached data due to communication failure with %s",
                self.host
            )
            return self._cached_data
        
        # No usable cached data - raise the last exception
        severity = self.health_tracker.get_error_pattern_severity()
        error_msg = (
            f"Error communicating with CresControl at {self.host} after "
            f"{RETRY_MAX_ATTEMPTS} attempts (severity: {severity}): {last_exception}"
        )
        
        _LOGGER.error(error_msg)
        raise UpdateFailed(error_msg) from last_exception
    
    async def _wait_with_backoff(self, attempt: int, multiplier: float = None) -> None:
        """Wait with exponential backoff and jitter."""
        if multiplier is None:
            multiplier = RETRY_BACKOFF_MULTIPLIER
            
        delay = min(
            RETRY_INITIAL_DELAY * (multiplier ** attempt),
            RETRY_MAX_DELAY
        )
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, RETRY_JITTER_MAX * delay)
        total_delay = delay + jitter
        
        _LOGGER.debug(
            "CresControl waiting %.2f seconds before retry (base: %.2f, jitter: %.2f)",
            total_delay, delay, jitter
        )
        
        await asyncio.sleep(total_delay)
    
    async def _handle_persistent_failure(self, last_exception: Exception) -> None:
        """Handle persistent communication failures."""
        # Switch to degraded polling if not already
        if not self.health_tracker.should_use_degraded_polling():
            await self._switch_to_degraded_polling()
        
        # Log appropriate message based on error pattern
        severity = self.health_tracker.get_error_pattern_severity()
        
        if severity == ERROR_SEVERITY_CRITICAL:
            _LOGGER.error(
                "CresControl critical communication issues with %s - device may be offline",
                self.host
            )
        elif severity == ERROR_SEVERITY_HIGH:
            _LOGGER.warning(
                "CresControl persistent communication issues with %s - using degraded mode",
                self.host
            )
        else:
            _LOGGER.info(
                "CresControl temporary communication issue with %s",
                self.host
            )
    
    async def _switch_to_degraded_polling(self) -> None:
        """Switch to degraded polling mode."""
        if self.update_interval != HEALTH_DEGRADED_UPDATE_INTERVAL:
            _LOGGER.info(
                "CresControl switching to degraded polling mode (interval: %s)",
                HEALTH_DEGRADED_UPDATE_INTERVAL
            )
            self.update_interval = HEALTH_DEGRADED_UPDATE_INTERVAL
    
    async def _restore_normal_polling(self) -> None:
        """Restore normal polling interval."""
        if self.update_interval != self._base_update_interval:
            _LOGGER.info(
                "CresControl restoring normal polling mode (interval: %s)",
                self._base_update_interval
            )
            self.update_interval = self._base_update_interval
    
    def _should_use_cached_data(self) -> bool:
        """Determine if cached data should be used."""
        if not self._cached_data or not self._last_successful_data_time:
            return False
        
        # Use cached data if it's relatively recent
        cache_age = dt_util.utcnow() - self._last_successful_data_time
        max_cache_age = timedelta(minutes=5)  # Allow 5 minutes of cached data
        
        return cache_age <= max_cache_age
    
    def get_health_info(self) -> Dict[str, Any]:
        """Get comprehensive health information for diagnostics."""
        health_info = {
            **self.health_tracker.get_status_info(),
            "host": self.host,
            "update_interval": self.update_interval.total_seconds(),
            "base_update_interval": self._base_update_interval.total_seconds(),
            "using_cached_data": self._should_use_cached_data(),
            "last_successful_data": (
                self._last_successful_data_time.isoformat()
                if self._last_successful_data_time else None
            ),
            "degraded_polling": self.health_tracker.should_use_degraded_polling(),
        }
        
        # Add WebSocket-specific health information
        if self._websocket_enabled:
            websocket_info = {
                "websocket_enabled": self._websocket_enabled,
                "websocket_connected": self._websocket_connected,
                "websocket_subscription_active": self._websocket_subscription_active,
                "websocket_last_data": (
                    self._websocket_last_data_time.isoformat()
                    if self._websocket_last_data_time else None
                ),
                "using_websocket_data": self._should_use_websocket_data(),
                "adaptive_polling": self.update_interval != self._base_update_interval,
            }
            health_info.update(websocket_info)
            
            # Include client WebSocket status if available
            if self.client.websocket_enabled:
                health_info["websocket_client_status"] = self.client.get_websocket_status()
        
        return health_info

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and clean up WebSocket connections."""
        if self._websocket_enabled and self.client.websocket_connected:
            try:
                await self._disable_websocket_subscription()
                await self.client.disable_websocket()
                _LOGGER.debug("WebSocket connections closed for %s", self.host)
            except Exception as err:
                _LOGGER.warning("Error during WebSocket cleanup: %s", err)


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the CresControl integration from YAML (deprecated).

    This integration is intended to be configured via the UI. If a user
    specifies configuration in configuration.yaml, it will be ignored.
    """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CresControl from a config entry created via the UI."""
    host = entry.data["host"]
    # Get the configured update interval, falling back to default for backward compatibility
    update_interval_seconds = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS)
    update_interval = timedelta(seconds=update_interval_seconds)
    
    # Get WebSocket configuration, falling back to defaults for backward compatibility
    websocket_enabled = entry.data.get(CONF_WEBSOCKET_ENABLED, DEFAULT_WEBSOCKET_ENABLED)
    websocket_port = entry.data.get(CONF_WEBSOCKET_PORT, DEFAULT_WEBSOCKET_PORT)
    websocket_path = entry.data.get(CONF_WEBSOCKET_PATH, DEFAULT_WEBSOCKET_PATH)
    
    session = async_get_clientsession(hass)
    
    # Create HTTP client for fallback communication
    http_client = CresControlClient(host, session)
    
    # Create WebSocket client for real-time data (if enabled)
    websocket_client = None
    if websocket_enabled:
        websocket_client = CresControlWebSocketClient(
            host=host,
            session=session,
            port=websocket_port,
            path=websocket_path
        )
    
    # Create hybrid coordinator that prioritizes WebSocket with HTTP fallback
    if websocket_client:
        coordinator = CresControlHybridCoordinator(
            hass=hass,
            http_client=http_client,
            websocket_client=websocket_client,
            host=host,
            update_interval=update_interval,
        )
    else:
        # Fall back to HTTP-only coordinator for backward compatibility
        coordinator = CresControlCoordinator(
            hass=hass,
            client=http_client,
            host=host,
            update_interval=update_interval,
        )

    try:
        # Perform initial refresh with enhanced error handling
        _LOGGER.info("Performing initial connection test for CresControl at %s", host)
        await coordinator.async_config_entry_first_refresh()
        
        # Log initial health status
        health_info = coordinator.get_health_info()
        _LOGGER.info(
            "CresControl initial setup successful for %s (status: %s)",
            host, health_info["status"]
        )
        
    except ConfigEntryNotReady:
        # Re-raise ConfigEntryNotReady to indicate to Home Assistant that
        # the setup should be retried. This exception is thrown when the
        # coordinator fails its first refresh.
        _LOGGER.warning("CresControl setup not ready for %s, will retry", host)
        raise
    except Exception as err:
        # Any other exception means we could not communicate with the device.
        health_info = coordinator.get_health_info()
        error_severity = coordinator.health_tracker.get_error_pattern_severity()
        
        error_msg = (
            f"Unable to connect to CresControl at {host} (severity: {error_severity}): {err}"
        )
        
        _LOGGER.error(error_msg)
        raise ConfigEntryNotReady(error_msg) from err

    # Create device registry entry
    device_registry = dr.async_get(hass)
    device_info = {
        "identifiers": {(DOMAIN, host)},
        "name": f"CresControl ({host})",
        "manufacturer": "Crescience",
        "model": "CresControl Cannabis Grow Controller",
        "configuration_url": f"http://{host}",
    }
    
    # Register the device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **device_info
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "http_client": http_client,
        "websocket_client": websocket_client,
        "coordinator": coordinator,
        "device_info": device_info,
    }

    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a CresControl config entry."""
    # Shutdown coordinator and clean up WebSocket connections
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
        if coordinator and hasattr(coordinator, 'async_shutdown'):
            await coordinator.async_shutdown()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
