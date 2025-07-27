"""
Simplified WebSocket client for CresControl devices.

This module provides a working WebSocket client that connects to CresControl devices
and handles real-time data updates in the parameter::value format.

Based on successful testing against real device at 192.168.105.15:81.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Set
import aiohttp
from aiohttp import ClientSession, WSMsgType

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class CresControlWebSocketError(Exception):
    """WebSocket-related errors."""
    pass


class CresControlWebSocketClient:
    """Simplified WebSocket client for real-time communication with CresControl devices."""
    
    def __init__(
        self,
        host: str,
        session: ClientSession,
        port: int = 81,
        path: str = "/websocket",
        timeout: int = 30,
    ) -> None:
        """Initialize the WebSocket client.
        
        Parameters
        ----------
        host: str
            The IP address or hostname of the CresControl device.
        session: ClientSession
            A shared aiohttp session provided by Home Assistant.
        port: int
            WebSocket port (default: 81 - confirmed working).
        path: str
            WebSocket endpoint path (default: "/websocket" - confirmed working).
        timeout: int
            Connection timeout in seconds (default: 30).
        """
        self._host = host
        self._port = port
        self._path = path
        self._session = session
        self._timeout = timeout
        self._ws_url = f"ws://{host}:{port}{path}"
        
        # Connection state
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._connected = False
        self._connection_task: Optional[asyncio.Task] = None
        self._should_reconnect = True
        
        # Data handling
        self._data_handlers: Set[Callable] = set()
        self._last_data: Dict[str, str] = {}
        
        # Statistics
        self._messages_received = 0
        self._messages_sent = 0
        self._connection_time: Optional[datetime] = None
        
        _LOGGER.debug("WebSocket client initialized for %s", self._ws_url)
    
    async def connect(self) -> bool:
        """Connect to the WebSocket server.
        
        Returns
        -------
        bool
            True if connection successful, False otherwise.
        """
        if self._websocket and not self._websocket.closed:
            _LOGGER.debug("WebSocket already connected to %s", self._ws_url)
            return True
            
        _LOGGER.info("Connecting to WebSocket at %s", self._ws_url)
        
        try:
            # Use the working configuration from the test
            self._websocket = await self._session.ws_connect(
                self._ws_url,
                timeout=self._timeout,
                heartbeat=30
            )
            
            self._connected = True
            self._connection_time = dt_util.utcnow()
            
            _LOGGER.info("WebSocket connected successfully to %s", self._ws_url)
            
            # Start message handling task
            self._connection_task = asyncio.create_task(self._handle_messages())
            
            # Subscribe to initial parameters for real-time updates
            await self._subscribe_to_updates()
            
            return True
            
        except Exception as err:
            self._connected = False
            error_msg = f"Failed to connect to WebSocket: {err}"
            _LOGGER.error(error_msg)
            raise CresControlWebSocketError(error_msg) from err
    
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        _LOGGER.info("Disconnecting from WebSocket at %s", self._ws_url)
        self._should_reconnect = False
        
        # Cancel message handling task
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            self._connection_task = None
        
        # Close WebSocket connection
        if self._websocket and not self._websocket.closed:
            try:
                await self._websocket.close()
            except Exception as err:
                _LOGGER.warning("Error closing WebSocket: %s", err)
        
        self._websocket = None
        self._connected = False
        self._connection_time = None
        
        _LOGGER.info("WebSocket disconnected from %s", self._ws_url)
    
    async def send_command(self, command: str) -> None:
        """Send a command to the WebSocket server.
        
        Parameters
        ----------
        command: str
            Command string to send (e.g., "in-a:voltage").
            
        Raises
        ------
        CresControlWebSocketError
            If WebSocket is not connected or command fails.
        """
        if not self._websocket or self._websocket.closed:
            raise CresControlWebSocketError("WebSocket not connected")
        
        try:
            await self._websocket.send_str(command)
            self._messages_sent += 1
            
            _LOGGER.debug("WebSocket command sent: %s", command)
            
        except Exception as err:
            error_msg = f"Failed to send WebSocket command: {err}"
            _LOGGER.error(error_msg)
            raise CresControlWebSocketError(error_msg) from err
    
    async def _subscribe_to_updates(self) -> None:
        """Subscribe to data updates by sending initial parameter requests."""
        if not self._websocket or self._websocket.closed:
            return
            
        try:
            # Send commands for core parameters based on successful testing
            # These parameters are confirmed to work with the real device
            initial_commands = [
                # Voltage inputs
                'in-a:voltage',      # ✅ Confirmed working
                'in-b:voltage',      # Test if available
                
                # Fan monitoring
                'fan:enabled',       # ✅ Confirmed working  
                'fan:duty-cycle',    # ✅ Confirmed working
                'fan:rpm',           # Fan RPM monitoring
                
                # Output controls
                'out-a:enabled',     # ✅ Confirmed working
                'out-a:voltage',     # ✅ Confirmed working
                'out-b:enabled',     # ✅ Confirmed working
                'out-b:voltage',     # ✅ Confirmed working
                'out-c:enabled',     # Likely working (same pattern)
                'out-c:voltage',     # Likely working (same pattern)
                'out-d:enabled',     # Likely working (same pattern)
                'out-d:voltage',     # Likely working (same pattern)
                'out-e:enabled',     # Likely working (same pattern)
                'out-e:voltage',     # Likely working (same pattern)
                'out-f:enabled',     # Likely working (same pattern)
                'out-f:voltage',     # Likely working (same pattern)
                
                # Extension-based sensors (CO2 and climate sensors)
                'extension:co2-2006:co2-concentration',    # CO2 concentration
                'extension:co2-2006:temperature',          # CO2 sensor temperature
                'extension:climate-2011:temperature',      # Air temperature
                'extension:climate-2011:humidity',         # Humidity
                'extension:climate-2011:vpd',              # Vapor Pressure Deficit
                
                # Note: switch parameters may return error responses on some devices
                # 'switch-12v:enabled', 'switch-24v-a:enabled', 'switch-24v-b:enabled'
            ]
            
            for cmd in initial_commands:
                try:
                    await self.send_command(cmd)
                    # Small delay to avoid overwhelming the device
                    await asyncio.sleep(0.1)
                except Exception as e:
                    _LOGGER.debug("Failed to send initial command %s: %s", cmd, e)
                    continue
            
            _LOGGER.debug("Sent %d initial parameter requests", len(initial_commands))
            
        except Exception as e:
            _LOGGER.warning("Failed to subscribe to updates: %s", e)
            # Don't raise error - subscription failure shouldn't prevent connection
    
    def add_data_handler(self, handler: Callable[[Dict[str, str]], None]) -> None:
        """Add a handler for data updates.
        
        Parameters
        ----------
        handler: Callable
            Function to call when data updates are received.
            Should accept a dict with parameter names as keys and values as strings.
        """
        self._data_handlers.add(handler)
        _LOGGER.debug("Added WebSocket data handler")
    
    def remove_data_handler(self, handler: Callable) -> None:
        """Remove a data handler.
        
        Parameters
        ----------
        handler: Callable
            Handler function to remove.
        """
        self._data_handlers.discard(handler)
        _LOGGER.debug("Removed WebSocket data handler")
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and self._websocket is not None and not self._websocket.closed
    
    @property
    def last_data(self) -> Dict[str, str]:
        """Get the last received data."""
        return self._last_data.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics.
        
        Returns
        -------
        Dict[str, Any]
            Statistics about the WebSocket connection.
        """
        return {
            "connected": self.is_connected,
            "host": self._host,
            "port": self._port,
            "path": self._path,
            "url": self._ws_url,
            "messages_received": self._messages_received,
            "messages_sent": self._messages_sent,
            "connection_time": (
                self._connection_time.isoformat()
                if self._connection_time else None
            ),
            "uptime_seconds": (
                (dt_util.utcnow() - self._connection_time).total_seconds()
                if self._connection_time else 0
            ),
            "data_handlers": len(self._data_handlers),
            "last_data_count": len(self._last_data),
        }
    
    async def _handle_messages(self) -> None:
        """Handle incoming WebSocket messages."""
        _LOGGER.debug("Starting WebSocket message handler")
        
        try:
            async for msg in self._websocket:
                if msg.type == WSMsgType.TEXT:
                    try:
                        await self._process_message(msg.data)
                        self._messages_received += 1
                        
                    except Exception as err:
                        _LOGGER.warning("Error processing WebSocket message: %s", err)
                        
                elif msg.type == WSMsgType.ERROR:
                    error_msg = f"WebSocket error: {self._websocket.exception()}"
                    _LOGGER.error(error_msg)
                    break
                    
                elif msg.type == WSMsgType.CLOSE:
                    _LOGGER.info("WebSocket connection closed by server")
                    break
                    
        except Exception as err:
            _LOGGER.error("Error in WebSocket message handler: %s", err)
        
        finally:
            self._connected = False
            _LOGGER.debug("WebSocket message handler stopped")
    
    async def _process_message(self, message: str) -> None:
        """Process a CresControl WebSocket message in format 'parameter::value'.
        
        Parameters
        ----------
        message: str
            Raw message text from WebSocket.
        """
        try:
            # CresControl WebSocket uses format: "parameter::value"
            if "::" in message:
                parts = message.split("::", 1)
                if len(parts) == 2:
                    param, value = parts
                    param = param.strip()
                    value = value.strip()
                    
                    # Skip error responses
                    if value.startswith('{"error"'):
                        _LOGGER.debug("Skipping error response for %s: %s", param, value)
                        return
                    
                    # Update last data
                    self._last_data[param] = value
                    
                    # Notify data handlers
                    data_update = {param: value}
                    for handler in self._data_handlers:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(data_update)
                            else:
                                handler(data_update)
                        except Exception as err:
                            _LOGGER.error("Error in WebSocket data handler: %s", err)
                    
                    _LOGGER.debug("Processed WebSocket data update: %s = %s", param, value)
            else:
                _LOGGER.debug("Received WebSocket message without delimiter: %s", message)
                
        except Exception as err:
            _LOGGER.error("Error processing CresControl WebSocket message: %s", err)