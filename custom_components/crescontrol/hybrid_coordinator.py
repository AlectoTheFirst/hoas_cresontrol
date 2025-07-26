"""
Simplified hybrid coordinator for CresControl devices.

This coordinator prioritizes WebSocket data for real-time updates and falls back
to HTTP polling when WebSocket is unavailable. It integrates with the WebSocket
client implemented in websocket_client.py and provides basic error handling.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import CresControlClient, CresControlError
from .websocket_client import CresControlWebSocketClient, CresControlWebSocketError

_LOGGER = logging.getLogger(__name__)


class CresControlHybridCoordinator(DataUpdateCoordinator):
    """Hybrid coordinator using WebSocket data with HTTP fallback."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        http_client: CresControlClient,
        websocket_client: CresControlWebSocketClient,
        host: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the hybrid coordinator.
        
        Parameters
        ----------
        hass: HomeAssistant
            Home Assistant instance.
        http_client: CresControlClient
            HTTP client for fallback communication.
        websocket_client: CresControlWebSocketClient
            WebSocket client for real-time data.
        host: str
            Device host address.
        update_interval: timedelta
            Base update interval for HTTP polling.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"CresControl {host}",
            update_method=self._async_update_data,
            update_interval=update_interval,
        )
        
        self.http_client = http_client
        self.websocket_client = websocket_client
        self.host = host
        self._base_update_interval = update_interval
        
        # WebSocket state tracking
        self._websocket_connected = False
        self._websocket_last_data_time: Optional[datetime] = None
        self._websocket_data: Dict[str, Any] = {}
        
        # HTTP fallback state
        self._http_last_data_time: Optional[datetime] = None
        self._http_data: Dict[str, Any] = {}
        
        # Setup WebSocket data handler
        self.websocket_client.add_data_handler(self._handle_websocket_data)
        
        _LOGGER.info("Hybrid coordinator initialized for %s", host)
    
    def _handle_websocket_data(self, data: Dict[str, str]) -> None:
        """Handle incoming WebSocket data updates.
        
        This method is called by the WebSocket client when new data arrives.
        It updates the coordinator's data and notifies all listeners.
        
        Parameters
        ----------
        data: Dict[str, str]
            WebSocket data update in parameter:value format.
        """
        if not data:
            return
        
        _LOGGER.debug("Received WebSocket data: %s", data)
        
        # Update WebSocket state
        self._websocket_connected = True
        self._websocket_last_data_time = dt_util.utcnow()
        
        # Merge new data with existing WebSocket data
        self._websocket_data.update(data)
        
        # Create combined data from WebSocket and HTTP sources
        combined_data = self._get_combined_data()
        
        # Notify all listeners of the update
        self.async_set_updated_data(combined_data)
        
        _LOGGER.debug("WebSocket data processed and listeners notified")
    
    def _get_combined_data(self) -> Dict[str, Any]:
        """Get combined data from WebSocket and HTTP sources.
        
        WebSocket data takes priority over HTTP data when available.
        
        Returns
        -------
        Dict[str, Any]
            Combined data with WebSocket data taking priority.
        """
        # Start with HTTP data as base
        combined_data = self._http_data.copy()
        
        # Overlay WebSocket data (takes priority)
        combined_data.update(self._websocket_data)
        
        return combined_data
    
    def _should_use_websocket_data(self) -> bool:
        """Determine if WebSocket data is recent and should be prioritized.
        
        Returns
        -------
        bool
            True if WebSocket data is recent and reliable.
        """
        if not self._websocket_connected or not self._websocket_last_data_time:
            return False
        
        # Consider WebSocket data recent if it's within 2x the update interval
        max_age = self._base_update_interval * 2
        age = dt_util.utcnow() - self._websocket_last_data_time
        
        return age <= max_age
    
    def _get_adaptive_update_interval(self) -> timedelta:
        """Get adaptive update interval based on WebSocket connectivity.
        
        When WebSocket is providing recent data, reduce HTTP polling frequency.
        
        Returns
        -------
        timedelta
            Appropriate update interval based on current state.
        """
        if self._should_use_websocket_data():
            # Reduce HTTP polling when WebSocket is active
            return self._base_update_interval * 3
        else:
            # Use normal interval when WebSocket is not available
            return self._base_update_interval
    
    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data using hybrid approach: WebSocket priority with HTTP fallback.
        
        Returns
        -------
        Dict[str, Any]
            Combined data from WebSocket and HTTP sources.
            
        Raises
        ------
        UpdateFailed
            If both WebSocket and HTTP communication fail.
        """
        # Try to connect WebSocket if not connected
        if not self.websocket_client.is_connected:
            try:
                await self.websocket_client.connect()
                self._websocket_connected = True
                _LOGGER.info("WebSocket connected for %s", self.host)
            except CresControlWebSocketError as err:
                _LOGGER.warning("WebSocket connection failed for %s: %s", self.host, err)
                self._websocket_connected = False
        
        # Adjust HTTP polling interval based on WebSocket status
        adaptive_interval = self._get_adaptive_update_interval()
        if self.update_interval != adaptive_interval:
            self.update_interval = adaptive_interval
            _LOGGER.debug("Adjusted HTTP polling interval to %s", adaptive_interval)
        
        # If WebSocket data is recent, we can skip HTTP polling
        if self._should_use_websocket_data():
            _LOGGER.debug("Using recent WebSocket data, skipping HTTP poll")
            return self._get_combined_data()
        
        # Perform HTTP polling as fallback
        try:
            _LOGGER.debug("Performing HTTP data fetch for %s", self.host)
            
            # Core parameters that are confirmed to work
            commands = [
                'in-a:voltage',      # Analog inputs
                'fan:enabled',       # Fan control
                'fan:duty-cycle',    # Fan speed
                'out-a:enabled',     # Output states
                'out-a:voltage',     # Output voltages
                'out-b:enabled',
                'out-b:voltage',
                'out-c:enabled',
                'out-c:voltage',
                'out-d:enabled',
                'out-d:voltage',
                # Add more parameters as needed
            ]
            
            http_data = await self.http_client.send_commands(commands)
            
            # Update HTTP state
            self._http_last_data_time = dt_util.utcnow()
            self._http_data = http_data
            
            _LOGGER.debug("HTTP data fetch successful: %d parameters", len(http_data))
            
            # Return combined data (WebSocket + HTTP)
            return self._get_combined_data()
            
        except CresControlError as err:
            # HTTP failed - check if we have any recent data to fall back to
            if self._has_recent_data():
                _LOGGER.warning(
                    "HTTP polling failed for %s, using cached data: %s", 
                    self.host, err
                )
                return self._get_combined_data()
            
            # No recent data available
            error_msg = f"Both WebSocket and HTTP communication failed for {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise UpdateFailed(error_msg) from err
    
    def _has_recent_data(self) -> bool:
        """Check if we have recent data from any source.
        
        Returns
        -------
        bool
            True if we have data from WebSocket or HTTP within reasonable time.
        """
        now = dt_util.utcnow()
        max_age = timedelta(minutes=5)  # Allow 5 minutes of stale data
        
        # Check WebSocket data age
        if (self._websocket_last_data_time and 
            (now - self._websocket_last_data_time) <= max_age):
            return True
        
        # Check HTTP data age
        if (self._http_last_data_time and 
            (now - self._http_last_data_time) <= max_age):
            return True
        
        return False
    
    async def async_set_value(self, parameter: str, value: Any) -> None:
        """Set a parameter value using HTTP client.
        
        Control commands are always sent via HTTP for reliability.
        
        Parameters
        ----------
        parameter: str
            Parameter name to set.
        value: Any
            Value to set.
        """
        try:
            _LOGGER.debug("Setting %s = %s via HTTP", parameter, value)
            await self.http_client.set_value(parameter, value)
            
            # Trigger immediate refresh to get updated state
            await self.async_request_refresh()
            
        except CresControlError as err:
            error_msg = f"Failed to set {parameter} = {value}: {err}"
            _LOGGER.error(error_msg)
            raise UpdateFailed(error_msg) from err
    
    async def async_get_value(self, parameter: str) -> Any:
        """Get a parameter value, preferring WebSocket data.
        
        Parameters
        ----------
        parameter: str
            Parameter name to get.
            
        Returns
        -------
        Any
            Parameter value from WebSocket or HTTP data.
        """
        # Check WebSocket data first
        if parameter in self._websocket_data and self._should_use_websocket_data():
            return self._websocket_data[parameter]
        
        # Fall back to HTTP data
        if parameter in self._http_data:
            return self._http_data[parameter]
        
        # Not found in cached data - try direct HTTP request
        try:
            return await self.http_client.get_value(parameter)
        except CresControlError as err:
            _LOGGER.warning("Failed to get %s: %s", parameter, err)
            return None
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status information.
        
        Returns
        -------
        Dict[str, Any]
            Status information for diagnostics.
        """
        return {
            "host": self.host,
            "websocket_connected": self._websocket_connected,
            "websocket_last_data": (
                self._websocket_last_data_time.isoformat()
                if self._websocket_last_data_time else None
            ),
            "http_last_data": (
                self._http_last_data_time.isoformat()
                if self._http_last_data_time else None
            ),
            "websocket_parameters": len(self._websocket_data),
            "http_parameters": len(self._http_data),
            "using_websocket_data": self._should_use_websocket_data(),
            "update_interval": self.update_interval.total_seconds(),
            "base_update_interval": self._base_update_interval.total_seconds(),
        }
    
    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and clean up connections."""
        _LOGGER.info("Shutting down hybrid coordinator for %s", self.host)
        
        # Disconnect WebSocket
        try:
            await self.websocket_client.disconnect()
        except Exception as err:
            _LOGGER.warning("Error disconnecting WebSocket: %s", err)
        
        _LOGGER.info("Hybrid coordinator shutdown complete for %s", self.host)