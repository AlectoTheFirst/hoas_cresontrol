"""
Async client for interacting with CresControl devices.

The CresControl firmware exposes a simple command interface via HTTP. Each
request contains one or more commands separated by semicolons and returns
a response where each command result is delimited by double colons. This
client abstracts away the request/response semantics and exposes methods
for sending arbitrary commands as well as reading and writing specific
parameters.

Example usage:

>>> session = async_get_clientsession(hass)
>>> client = CresControlClient("192.168.1.10", session)
>>> result = await client.get_value("in-a:voltage")
>>> await client.set_value("out-a:voltage", 4.2)

Note: The CresControl API currently does not require authentication. Should
future firmware introduce authentication or tokens, this client can be
extended accordingly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Union, Optional, Callable, Set
import re
import ipaddress

from aiohttp import ClientSession, ClientTimeout, ClientError, ServerTimeoutError, TCPConnector, WSMsgType
import aiohttp
from homeassistant.util import dt as dt_util


_LOGGER = logging.getLogger(__name__)


class CresControlError(Exception):
    """Base exception for CresControl API errors."""
    pass

class CresControlNetworkError(CresControlError):
    """Network-related errors (timeout, connection failed, etc.)."""
    pass

class CresControlDeviceError(CresControlError):
    """Device-related errors (invalid response, device unavailable, etc.)."""
    pass

class CresControlValidationError(CresControlError):
    """Input validation errors (invalid host, parameters, etc.)."""
    pass

class CresControlWebSocketError(CresControlError):
    """WebSocket-related errors (connection failed, protocol error, etc.)."""
    pass

class CresControlWebSocketAuthError(CresControlWebSocketError):
    """WebSocket authentication errors."""
    pass

class CresControlWebSocketProtocolError(CresControlWebSocketError):
    """WebSocket protocol errors (invalid message format, etc.)."""
    pass

class CresControlNetworkMonitor:
    """Monitor network health and connection patterns."""
    
    def __init__(self) -> None:
        """Initialize network monitor."""
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.total_requests = 0
        self.total_timeouts = 0
        self.last_request_time: Optional[datetime] = None
        self.last_failure_time: Optional[datetime] = None
        self.current_timeout_multiplier = 1.0
        self.connection_degraded = False
        
    def record_request_start(self) -> None:
        """Record the start of a request."""
        self.total_requests += 1
        self.last_request_time = dt_util.utcnow()
        
    def record_success(self, response_time: float) -> None:
        """Record a successful request."""
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        
        # Gradually reduce timeout multiplier on successful requests
        if self.current_timeout_multiplier > 1.0:
            self.current_timeout_multiplier = max(1.0, self.current_timeout_multiplier * 0.9)
            
        # Mark connection as healthy if it was degraded
        if self.connection_degraded and self.consecutive_successes >= 3:
            self.connection_degraded = False
            
    def record_failure(self, is_timeout: bool = False) -> None:
        """Record a failed request."""
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        self.last_failure_time = dt_util.utcnow()
        
        if is_timeout:
            self.total_timeouts += 1
            # Increase timeout multiplier for subsequent requests
            self.current_timeout_multiplier = min(3.0, self.current_timeout_multiplier * 1.2)
            
        # Mark connection as degraded after multiple failures
        if self.consecutive_failures >= 2:
            self.connection_degraded = True
            
    def get_adaptive_timeout(self, base_timeout: int) -> int:
        """Get adaptive timeout based on connection health."""
        adaptive_timeout = int(base_timeout * self.current_timeout_multiplier)
        return min(adaptive_timeout, base_timeout * 3)  # Cap at 3x base timeout
        
    def should_use_conservative_approach(self) -> bool:
        """Determine if conservative network approach should be used."""
        return self.connection_degraded or self.consecutive_failures > 0
        
    def get_status_info(self) -> Dict[str, Any]:
        """Get network monitoring status information."""
        return {
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_requests": self.total_requests,
            "total_timeouts": self.total_timeouts,
            "timeout_multiplier": self.current_timeout_multiplier,
            "connection_degraded": self.connection_degraded,
            "last_request": self.last_request_time.isoformat() if self.last_request_time else None,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


class CresControlClient:
    """Enhanced asynchronous wrapper around the CresControl HTTP API with WebSocket support and network resilience."""

    def __init__(
        self,
        host: str,
        session: ClientSession,
        timeout: int = 30,
        websocket_enabled: bool = True,
        websocket_port: int = 81,
        websocket_path: str = "/websocket"
    ) -> None:
        """Initialize the client.

        Parameters
        ----------
        host: str
            The IP address or hostname of the CresControl device. The protocol
            and port are implied (http on port 80). Do not include a scheme.
        session: ClientSession
            A shared aiohttp session provided by Home Assistant. Do not close
            this session from within the integration as it is owned by HA.
        timeout: int
            Request timeout in seconds (default: 30).
        websocket_enabled: bool
            Whether to enable WebSocket connectivity (default: False).
        websocket_port: int
            WebSocket port number (default: 8080).
        websocket_path: str
            WebSocket endpoint path (default: "/ws").
        
        Raises
        ------
        CresControlValidationError
            If the host format is invalid.
        """
        self._validate_host(host)
        self._base_url: str = f"http://{host}:80"
        self._session: ClientSession = session
        self._base_timeout: int = timeout
        self._timeout: ClientTimeout = ClientTimeout(total=timeout)
        self._host: str = host
        self._network_monitor = CresControlNetworkMonitor()
        
        # Connection optimization settings
        self._connection_pool_configured = False
        
        # WebSocket configuration
        self._websocket_enabled = websocket_enabled
        self._websocket_port = websocket_port
        self._websocket_path = websocket_path
        self._websocket_client: Optional[CresControlWebSocketClient] = None
        self._websocket_data_handlers: Set[Callable] = set()
        
        # Initialize WebSocket client if enabled
        if self._websocket_enabled:
            self._websocket_client = CresControlWebSocketClient(
                host=host,
                session=session,
                port=websocket_port,
                path=websocket_path,
                timeout=timeout
            )
            self._setup_websocket_handlers()

    async def send_commands(self, commands: Union[str, Iterable[str]]) -> Dict[str, Any]:
        """Send one or more commands to the CresControl and return the results with enhanced error handling.

        When a list is passed, the commands are joined using semicolons as
        specified by the CresControl API. The API always echoes the command
        followed by "::" and the resulting value. For write operations, the
        command will include the assignment and the response will echo this as
        well. This method extracts the parameter names and corresponding values
        into a dictionary.

        Parameters
        ----------
        commands: Union[str, Iterable[str]]
            A single command string or an iterable of command strings.

        Returns
        -------
        Dict[str, Any]
            A mapping from parameter names to their returned values. If a
            response does not contain a value for a given command, it will
            default to None.

        Raises
        ------
        CresControlValidationError
            If the commands contain invalid characters or formats.
        CresControlNetworkError
            If the underlying HTTP request fails or times out.
        CresControlDeviceError
            If the device returns an invalid response.
        """

        # Validate and build the query string
        if isinstance(commands, str):
            # Validate single command
            if '=' in commands:
                param, _ = commands.split('=', 1)
                self._validate_parameter(param.strip())
            else:
                self._validate_parameter(commands.strip())
            query = commands
        else:
            # Validate all commands in the iterable
            validated_commands = []
            for cmd in commands:
                if not isinstance(cmd, str):
                    raise CresControlValidationError("All commands must be strings")
                if '=' in cmd:
                    param, _ = cmd.split('=', 1)
                    self._validate_parameter(param.strip())
                else:
                    self._validate_parameter(cmd.strip())
                validated_commands.append(cmd)
            query = ";".join(validated_commands)

        # Validate query length
        if len(query) > 2000:  # Reasonable limit
            raise CresControlValidationError("Command query too long")

        url = f"{self._base_url}/command"
        self._validate_url(url)
        params = {"query": query}

        # Record request start for monitoring
        self._network_monitor.record_request_start()
        request_start_time = dt_util.utcnow()

        # Use adaptive timeout based on connection health
        adaptive_timeout = self._network_monitor.get_adaptive_timeout(self._base_timeout)
        timeout = ClientTimeout(total=adaptive_timeout)

        _LOGGER.debug(
            "Sending CresControl command(s) to %s (timeout: %ds): %s",
            self._base_url, adaptive_timeout, query
        )

        try:
            # Optimize connection if needed
            await self._ensure_connection_optimized()
            
            async with self._session.get(url, params=params, timeout=timeout) as resp:
                resp.raise_for_status()
                text = await resp.text()
                
            # Calculate response time and record success
            response_time = (dt_util.utcnow() - request_start_time).total_seconds()
            self._network_monitor.record_success(response_time)
            
            _LOGGER.debug(
                "CresControl response received in %.2fs: %s",
                response_time, text[:100] + "..." if len(text) > 100 else text
            )
            
        except ServerTimeoutError as err:
            self._network_monitor.record_failure(is_timeout=True)
            error_msg = f"Request timeout after {adaptive_timeout}s: {err}"
            _LOGGER.warning("CresControl timeout for %s: %s", self._base_url, error_msg)
            raise CresControlNetworkError(error_msg) from err
            
        except ClientError as err:
            self._network_monitor.record_failure()
            error_msg = f"Network error: {err}"
            _LOGGER.warning("CresControl network error for %s: %s", self._base_url, error_msg)
            raise CresControlNetworkError(error_msg) from err
            
        except Exception as err:
            self._network_monitor.record_failure()
            error_msg = f"Device error: {err}"
            _LOGGER.error("CresControl unexpected error for %s: %s", self._base_url, error_msg)
            raise CresControlDeviceError(error_msg) from err

        return self._parse_response_safely(text)

    async def _ensure_connection_optimized(self) -> None:
        """Ensure connection pool is optimized for current network conditions."""
        if self._connection_pool_configured:
            return
            
        # Note: We don't modify the session since it's owned by Home Assistant
        # but we can optimize our usage patterns
        self._connection_pool_configured = True
        
        if self._network_monitor.should_use_conservative_approach():
            _LOGGER.debug("CresControl using conservative network approach for %s", self._host)

    async def test_connection(self) -> bool:
        """Test connection to the device with a lightweight request.
        
        Returns
        -------
        bool
            True if connection test succeeds, False otherwise.
        """
        try:
            # Use a simple read command for connection testing
            await self.get_value("in-a:voltage")
            return True
        except CresControlError:
            return False
        except Exception:
            return False

    def get_network_status(self) -> Dict[str, Any]:
        """Get current network status and monitoring information.
        
        Returns
        -------
        Dict[str, Any]
            Network status information including connection health metrics.
        """
        return {
            "host": self._host,
            "base_timeout": self._base_timeout,
            "current_timeout": self._network_monitor.get_adaptive_timeout(self._base_timeout),
            **self._network_monitor.get_status_info(),
        }

    async def get_value(self, parameter: str) -> Any:
        """Read a single parameter from the CresControl.

        The parameter name should correspond exactly to one of the entries in
        the command reference. The raw value returned by the controller is
        returned as a string. It is up to the caller to convert this into the
        appropriate type (float, int, bool, etc.).

        Parameters
        ----------
        parameter: str
            The name of the parameter to read.

        Returns
        -------
        Any
            The raw value returned by the CresControl, or None if the
            parameter was not present in the response.
            
        Raises
        ------
        CresControlValidationError
            If the parameter name is invalid.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        self._validate_parameter(parameter)
        res = await self.send_commands([parameter])
        return res.get(parameter)

    async def set_value(self, parameter: str, value: Any) -> Any:
        """Write a value to a CresControl parameter.

        The value will be converted to the appropriate string representation.
        Boolean values are converted to "true"/"false" per the API
        specification. Numeric values are passed as is. Strings are passed
        unchanged after validation and sanitization.

        Parameters
        ----------
        parameter: str
            The name of the parameter to write.
        value: Any
            The value to assign to the parameter.

        Returns
        -------
        Any
            The value returned by the CresControl for the given parameter after
            assignment, or None if not returned.
            
        Raises
        ------
        CresControlValidationError
            If the parameter name or value is invalid.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        self._validate_parameter(parameter)
        val_str = self._validate_value(value)
        command = f"{parameter}={val_str}"
        res = await self.send_commands([command])
        # The response key may contain the assignment; strip it for lookup
        return res.get(parameter)

    def _validate_host(self, host: str) -> None:
        """Validate host format (IP address or hostname).
        
        Parameters
        ----------
        host: str
            The host to validate.
            
        Raises
        ------
        CresControlValidationError
            If the host format is invalid.
        """
        if not host or not isinstance(host, str):
            raise CresControlValidationError("Host must be a non-empty string")
        
        host = host.strip()
        if not host:
            raise CresControlValidationError("Host must be a non-empty string")
        
        # Check for URL injection attempts
        if any(char in host for char in ['/', '?', '#', '@', ':']):
            raise CresControlValidationError("Host contains invalid characters")
        
        # Try to parse as IP address first
        try:
            ipaddress.ip_address(host)
            return  # Valid IP address
        except ValueError:
            pass
        
        # Validate as hostname
        hostname_pattern = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
        )
        if not hostname_pattern.match(host):
            raise CresControlValidationError("Invalid hostname format")
        
        if len(host) > 253:
            raise CresControlValidationError("Hostname too long")

    def _validate_parameter(self, parameter: str) -> None:
        """Validate parameter name format.
        
        Parameters
        ----------
        parameter: str
            The parameter name to validate.
            
        Raises
        ------
        CresControlValidationError
            If the parameter format is invalid.
        """
        if not parameter or not isinstance(parameter, str):
            raise CresControlValidationError("Parameter must be a non-empty string")
        
        parameter = parameter.strip()
        if not parameter:
            raise CresControlValidationError("Parameter must be a non-empty string")
        
        # Check for command injection attempts
        if any(char in parameter for char in [';', '\n', '\r', '\0']):
            raise CresControlValidationError("Parameter contains invalid characters")
        
        # Validate parameter format (basic alphanumeric with allowed separators)
        param_pattern = re.compile(r'^[a-zA-Z0-9._:-]+$')
        if not param_pattern.match(parameter):
            raise CresControlValidationError("Invalid parameter name format")
        
        if len(parameter) > 100:
            raise CresControlValidationError("Parameter name too long")

    def _validate_value(self, value: Any) -> str:
        """Validate and sanitize parameter value.
        
        Parameters
        ----------
        value: Any
            The value to validate and convert.
            
        Returns
        -------
        str
            The sanitized string representation of the value.
            
        Raises
        ------
        CresControlValidationError
            If the value is invalid.
        """
        if value is None:
            raise CresControlValidationError("Value cannot be None")
        
        if isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            # Check for reasonable bounds
            if isinstance(value, float) and not (-1e6 <= value <= 1e6):
                raise CresControlValidationError("Numeric value out of reasonable bounds")
            if isinstance(value, int) and not (-1000000 <= value <= 1000000):
                raise CresControlValidationError("Numeric value out of reasonable bounds")
            return str(value)
        elif isinstance(value, str):
            # Sanitize string values
            value = value.strip()
            if not value:
                raise CresControlValidationError("String value cannot be empty")
            
            # Check for command injection attempts
            if any(char in value for char in [';', '\n', '\r', '\0']):
                raise CresControlValidationError("String value contains invalid characters")
            
            if len(value) > 1000:
                raise CresControlValidationError("String value too long")
            
            return value
        else:
            raise CresControlValidationError(f"Unsupported value type: {type(value)}")

    def _validate_url(self, url: str) -> None:
        """Validate URL to prevent injection attacks.
        
        Parameters
        ----------
        url: str
            The URL to validate.
            
        Raises
        ------
        CresControlValidationError
            If the URL is invalid or potentially malicious.
        """
        if not url.startswith(self._base_url):
            raise CresControlValidationError("URL does not match expected base URL")
        
        # Check for path traversal attempts
        if '..' in url or '//' in url.replace('http://', ''):
            raise CresControlValidationError("URL contains path traversal attempts")

    def _parse_response_safely(self, text: str) -> Dict[str, Any]:
        """Safely parse the response text.
        
        Parameters
        ----------
        text: str
            The response text to parse.
            
        Returns
        -------
        Dict[str, Any]
            Parsed response data.
            
        Raises
        ------
        CresControlDeviceError
            If the response format is invalid.
        """
        if not isinstance(text, str):
            raise CresControlDeviceError("Response is not a string")
        
        if len(text) > 10000:  # Reasonable limit
            raise CresControlDeviceError("Response too large")
        
        result: Dict[str, Any] = {}
        try:
            # Parse the response. The device may return multiple values separated by
            # newlines or semicolons. Each value is formatted as
            # <parameter>[=<input>]::<value>
            # Normalize line endings and split lines
            for line in text.replace("\r", "\n").split("\n"):
                for part in line.split(";"):
                    part = part.strip()
                    if not part:
                        continue
                    # Only split on the first occurrence of "::"
                    if "::" in part:
                        key_part, value = part.split("::", 1)
                        # Remove write assignment from the key if present
                        key = key_part.split("=", 1)[0]
                        result[key.strip()] = value.strip()
                    else:
                        # Unknown format; record the command without a value
                        result[part] = None
        except Exception as err:
            raise CresControlDeviceError(f"Failed to parse response: {err}") from err
        
        return result

    # =============================================================================
    # Fan-Specific API Methods
    # =============================================================================

    async def get_all_fan_data(self) -> Dict[str, Any]:
        """Fetch all fan data with a single optimized request.
        
        This method efficiently retrieves fan enabled state, duty cycle,
        minimum duty cycle, and RPM with a single API call.
        
        Returns
        -------
        Dict[str, Any]
            Dictionary containing parsed fan data with keys:
            - enabled: bool - Fan enabled state
            - duty_cycle: float - Current duty cycle percentage (0-100)
            - duty_cycle_min: float - Minimum duty cycle percentage
            - rpm: int - Current fan RPM
            
        Raises
        ------
        CresControlValidationError
            If the response data is invalid or unparseable.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        from .const import (
            FAN_PARAM_ENABLED, FAN_PARAM_DUTY_CYCLE,
            FAN_PARAM_DUTY_CYCLE_MIN, FAN_PARAM_RPM,
            FAN_DUTY_CYCLE_MIN, FAN_DUTY_CYCLE_MAX, FAN_RPM_MAX
        )
        
        commands = [
            FAN_PARAM_ENABLED,
            FAN_PARAM_DUTY_CYCLE,
            FAN_PARAM_DUTY_CYCLE_MIN,
            FAN_PARAM_RPM,
        ]
        
        _LOGGER.debug("Fetching all fan data with batch request")
        
        try:
            response = await self.send_commands(commands)
            
            # Parse and validate fan data
            enabled_raw = response.get(FAN_PARAM_ENABLED, "0")
            duty_cycle_raw = response.get(FAN_PARAM_DUTY_CYCLE, "0")
            duty_cycle_min_raw = response.get(FAN_PARAM_DUTY_CYCLE_MIN, "0")
            rpm_raw = response.get(FAN_PARAM_RPM, "0")
            
            # Convert and validate enabled state
            enabled = self._parse_boolean_value(enabled_raw, "fan enabled")
            
            # Convert and validate duty cycle
            duty_cycle = self._parse_float_value(
                duty_cycle_raw, "fan duty cycle",
                min_val=FAN_DUTY_CYCLE_MIN, max_val=FAN_DUTY_CYCLE_MAX
            )
            
            # Convert and validate minimum duty cycle
            duty_cycle_min = self._parse_float_value(
                duty_cycle_min_raw, "fan minimum duty cycle",
                min_val=FAN_DUTY_CYCLE_MIN, max_val=FAN_DUTY_CYCLE_MAX
            )
            
            # Convert and validate RPM
            rpm = self._parse_int_value(
                rpm_raw, "fan RPM",
                min_val=0, max_val=FAN_RPM_MAX
            )
            
            fan_data = {
                "enabled": enabled,
                "duty_cycle": duty_cycle,
                "duty_cycle_min": duty_cycle_min,
                "rpm": rpm,
            }
            
            _LOGGER.debug("Fan data retrieved successfully: %s", fan_data)
            return fan_data
            
        except (CresControlError, ValueError) as err:
            error_msg = f"Failed to retrieve fan data: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    async def set_fan_speed(self, percentage: float, enable: bool = True) -> Dict[str, Any]:
        """Set fan speed via duty cycle percentage with validation.
        
        This method sets the fan duty cycle and optionally enables/disables the fan.
        It includes proper validation and can automatically enable the fan when
        setting a non-zero speed.
        
        Parameters
        ----------
        percentage: float
            Target duty cycle percentage (0-100).
        enable: bool
            Whether to enable the fan (default: True).
            
        Returns
        -------
        Dict[str, Any]
            Updated fan state after setting speed.
            
        Raises
        ------
        CresControlValidationError
            If the percentage value is invalid.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        from .const import (
            FAN_PARAM_ENABLED, FAN_PARAM_DUTY_CYCLE,
            FAN_DUTY_CYCLE_MIN, FAN_DUTY_CYCLE_MAX
        )
        
        # Validate percentage
        if not isinstance(percentage, (int, float)):
            raise CresControlValidationError("Fan speed percentage must be a number")
        
        if not (FAN_DUTY_CYCLE_MIN <= percentage <= FAN_DUTY_CYCLE_MAX):
            raise CresControlValidationError(
                f"Fan speed percentage must be between {FAN_DUTY_CYCLE_MIN} and {FAN_DUTY_CYCLE_MAX}"
            )
        
        _LOGGER.debug("Setting fan speed to %.1f%% (enabled: %s)", percentage, enable)
        
        # Prepare commands for batch update
        commands = []
        
        # Set enabled state first if enabling, or if disabling and percentage is 0
        if enable or percentage == 0:
            enabled_val = "1" if enable and percentage > 0 else "0"
            commands.append(f"{FAN_PARAM_ENABLED}={enabled_val}")
        
        # Set duty cycle
        commands.append(f"{FAN_PARAM_DUTY_CYCLE}={percentage}")
        
        try:
            await self.send_commands(commands)
            
            # Return updated fan data
            return await self.get_all_fan_data()
            
        except CresControlError as err:
            error_msg = f"Failed to set fan speed to {percentage}%: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    async def set_fan_enabled(self, enabled: bool) -> bool:
        """Enable or disable the fan.
        
        When disabling the fan, this method sets the duty cycle to 0 for
        safety and energy efficiency.
        
        Parameters
        ----------
        enabled: bool
            Whether to enable the fan.
            
        Returns
        -------
        bool
            The updated enabled state.
            
        Raises
        ------
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        from .const import FAN_PARAM_ENABLED, FAN_PARAM_DUTY_CYCLE
        
        _LOGGER.debug("Setting fan enabled state to: %s", enabled)
        
        try:
            commands = [f"{FAN_PARAM_ENABLED}={'1' if enabled else '0'}"]
            
            # When disabling, also set duty cycle to 0 for safety
            if not enabled:
                commands.append(f"{FAN_PARAM_DUTY_CYCLE}=0")
            
            await self.send_commands(commands)
            
            return enabled
            
        except CresControlError as err:
            error_msg = f"Failed to set fan enabled state to {enabled}: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    async def get_fan_duty_cycle_min(self) -> float:
        """Get the minimum duty cycle setting for fan startup reliability.
        
        Returns
        -------
        float
            Minimum duty cycle percentage.
            
        Raises
        ------
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        from .const import FAN_PARAM_DUTY_CYCLE_MIN, FAN_DUTY_CYCLE_MIN, FAN_DUTY_CYCLE_MAX
        
        try:
            value = await self.get_value(FAN_PARAM_DUTY_CYCLE_MIN)
            return self._parse_float_value(
                value, "fan minimum duty cycle",
                min_val=FAN_DUTY_CYCLE_MIN, max_val=FAN_DUTY_CYCLE_MAX
            )
        except CresControlError as err:
            error_msg = f"Failed to get fan minimum duty cycle: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    async def set_fan_duty_cycle_min(self, min_percentage: float) -> float:
        """Set the minimum duty cycle for fan startup reliability.
        
        Parameters
        ----------
        min_percentage: float
            Minimum duty cycle percentage (0-100).
            
        Returns
        -------
        float
            The updated minimum duty cycle value.
            
        Raises
        ------
        CresControlValidationError
            If the percentage value is invalid.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        from .const import (
            FAN_PARAM_DUTY_CYCLE_MIN,
            FAN_DUTY_CYCLE_MIN, FAN_DUTY_CYCLE_MAX
        )
        
        # Validate percentage
        if not isinstance(min_percentage, (int, float)):
            raise CresControlValidationError("Fan minimum duty cycle must be a number")
        
        if not (FAN_DUTY_CYCLE_MIN <= min_percentage <= FAN_DUTY_CYCLE_MAX):
            raise CresControlValidationError(
                f"Fan minimum duty cycle must be between {FAN_DUTY_CYCLE_MIN} and {FAN_DUTY_CYCLE_MAX}"
            )
        
        _LOGGER.debug("Setting fan minimum duty cycle to %.1f%%", min_percentage)
        
        try:
            await self.set_value(FAN_PARAM_DUTY_CYCLE_MIN, min_percentage)
            return min_percentage
            
        except CresControlError as err:
            error_msg = f"Failed to set fan minimum duty cycle to {min_percentage}%: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    # =============================================================================
    # PWM-Specific API Methods
    # =============================================================================

    async def get_all_pwm_data(self) -> Dict[str, Any]:
        """Fetch all PWM data with a single optimized request.
        
        This method efficiently retrieves PWM enabled states, duty cycles,
        and frequencies for all PWM-capable outputs and switches.
        
        Returns
        -------
        Dict[str, Any]
            Dictionary containing parsed PWM data with keys for each PWM parameter.
            
        Raises
        ------
        CresControlValidationError
            If the response data is invalid or unparseable.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        from .const import (
            PWM_PARAM_OUT_A_ENABLED, PWM_PARAM_OUT_B_ENABLED,
            PWM_PARAM_OUT_A_DUTY_CYCLE, PWM_PARAM_OUT_B_DUTY_CYCLE,
            PWM_PARAM_OUT_A_FREQUENCY, PWM_PARAM_OUT_B_FREQUENCY,
            PWM_PARAM_SWITCH_12V_ENABLED, PWM_PARAM_SWITCH_24V_A_ENABLED, PWM_PARAM_SWITCH_24V_B_ENABLED,
            PWM_PARAM_SWITCH_12V_DUTY_CYCLE, PWM_PARAM_SWITCH_24V_A_DUTY_CYCLE, PWM_PARAM_SWITCH_24V_B_DUTY_CYCLE,
            PWM_PARAM_SWITCH_12V_FREQUENCY, PWM_PARAM_SWITCH_24V_A_FREQUENCY, PWM_PARAM_SWITCH_24V_B_FREQUENCY,
            PWM_DUTY_CYCLE_MIN, PWM_DUTY_CYCLE_MAX, PWM_FREQUENCY_MIN, PWM_FREQUENCY_MAX
        )
        
        commands = [
            # Output A-B PWM parameters
            PWM_PARAM_OUT_A_ENABLED, PWM_PARAM_OUT_A_DUTY_CYCLE, PWM_PARAM_OUT_A_FREQUENCY,
            PWM_PARAM_OUT_B_ENABLED, PWM_PARAM_OUT_B_DUTY_CYCLE, PWM_PARAM_OUT_B_FREQUENCY,
            # Switch PWM parameters
            PWM_PARAM_SWITCH_12V_ENABLED, PWM_PARAM_SWITCH_12V_DUTY_CYCLE, PWM_PARAM_SWITCH_12V_FREQUENCY,
            PWM_PARAM_SWITCH_24V_A_ENABLED, PWM_PARAM_SWITCH_24V_A_DUTY_CYCLE, PWM_PARAM_SWITCH_24V_A_FREQUENCY,
            PWM_PARAM_SWITCH_24V_B_ENABLED, PWM_PARAM_SWITCH_24V_B_DUTY_CYCLE, PWM_PARAM_SWITCH_24V_B_FREQUENCY,
        ]
        
        _LOGGER.debug("Fetching all PWM data with batch request")
        
        try:
            response = await self.send_commands(commands)
            
            # Parse and validate PWM data
            pwm_data = {}
            
            # Process each parameter with appropriate validation
            for param in commands:
                raw_value = response.get(param, "0")
                
                if "enabled" in param:
                    # Boolean PWM enabled parameters
                    pwm_data[param] = self._parse_boolean_value(raw_value, f"PWM enabled ({param})")
                elif "duty-cycle" in param:
                    # Duty cycle parameters (0-100%)
                    pwm_data[param] = self._parse_float_value(
                        raw_value, f"PWM duty cycle ({param})",
                        min_val=PWM_DUTY_CYCLE_MIN, max_val=PWM_DUTY_CYCLE_MAX
                    )
                elif "frequency" in param:
                    # Frequency parameters (0-1000 Hz)
                    pwm_data[param] = self._parse_float_value(
                        raw_value, f"PWM frequency ({param})",
                        min_val=PWM_FREQUENCY_MIN, max_val=PWM_FREQUENCY_MAX
                    )
            
            _LOGGER.debug("PWM data retrieved successfully: %d parameters", len(pwm_data))
            return pwm_data
            
        except (CresControlError, ValueError) as err:
            error_msg = f"Failed to retrieve PWM data: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    async def set_pwm_enabled(self, parameter: str, enabled: bool) -> bool:
        """Enable or disable PWM mode for an output or switch.
        
        Parameters
        ----------
        parameter: str
            PWM enable parameter (e.g., "out-a:pwm-enabled", "switch-12v:pwm-enabled").
        enabled: bool
            Whether to enable PWM mode.
            
        Returns
        -------
        bool
            The updated PWM enabled state.
            
        Raises
        ------
        CresControlValidationError
            If the parameter is invalid or not PWM-capable.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        self._validate_pwm_enabled_parameter(parameter)
        
        _LOGGER.debug("Setting PWM enabled state to %s for parameter: %s", enabled, parameter)
        
        try:
            # When enabling PWM, we may need to disable normal output mode
            commands = [f"{parameter}={'true' if enabled else 'false'}"]
            
            # For outputs, disable normal output when enabling PWM
            if parameter.startswith("out-") and enabled:
                output_enabled_param = parameter.replace(":pwm-enabled", ":enabled")
                commands.append(f"{output_enabled_param}=false")
                _LOGGER.debug("Disabling normal output mode when enabling PWM: %s", output_enabled_param)
            
            await self.send_commands(commands)
            return enabled
            
        except CresControlError as err:
            error_msg = f"Failed to set PWM enabled state for {parameter}: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    async def set_pwm_duty_cycle(self, parameter: str, duty_cycle: float) -> float:
        """Set PWM duty cycle for an output or switch.
        
        Parameters
        ----------
        parameter: str
            PWM duty cycle parameter (e.g., "out-a:duty-cycle", "switch-12v:duty-cycle").
        duty_cycle: float
            Duty cycle percentage (0-100).
            
        Returns
        -------
        float
            The updated duty cycle value.
            
        Raises
        ------
        CresControlValidationError
            If the parameter or duty cycle is invalid.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        self._validate_pwm_duty_cycle_parameter(parameter)
        self._validate_pwm_duty_cycle_value(duty_cycle)
        
        _LOGGER.debug("Setting PWM duty cycle to %.1f%% for parameter: %s", duty_cycle, parameter)
        
        try:
            await self.set_value(parameter, duty_cycle)
            return duty_cycle
            
        except CresControlError as err:
            error_msg = f"Failed to set PWM duty cycle for {parameter}: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    async def set_pwm_frequency(self, parameter: str, frequency: float) -> float:
        """Set PWM frequency for an output or switch.
        
        Parameters
        ----------
        parameter: str
            PWM frequency parameter (e.g., "out-a:pwm-frequency", "switch-12v:pwm-frequency").
        frequency: float
            PWM frequency in Hz (0-1000).
            
        Returns
        -------
        float
            The updated frequency value.
            
        Raises
        ------
        CresControlValidationError
            If the parameter or frequency is invalid.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        self._validate_pwm_frequency_parameter(parameter)
        self._validate_pwm_frequency_value(frequency)
        
        _LOGGER.debug("Setting PWM frequency to %.1f Hz for parameter: %s", frequency, parameter)
        
        try:
            await self.set_value(parameter, frequency)
            return frequency
            
        except CresControlError as err:
            error_msg = f"Failed to set PWM frequency for {parameter}: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    async def batch_set_pwm_parameters(self, pwm_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Set multiple PWM parameters in a single batch operation.
        
        This method allows efficient updating of multiple PWM parameters
        (enabled states, duty cycles, frequencies) in one API call.
        
        Parameters
        ----------
        pwm_settings: Dict[str, Any]
            Dictionary mapping parameter names to their target values.
            
        Returns
        -------
        Dict[str, Any]
            Updated parameter values after batch operation.
            
        Raises
        ------
        CresControlValidationError
            If any parameter or value is invalid.
        CresControlNetworkError
            If the network request fails.
        CresControlDeviceError
            If the device response is invalid.
        """
        from .const import PWM_MAX_BATCH_OPERATIONS
        
        if not pwm_settings:
            raise CresControlValidationError("No PWM settings provided for batch operation")
        
        if len(pwm_settings) > PWM_MAX_BATCH_OPERATIONS:
            raise CresControlValidationError(
                f"Too many PWM operations ({len(pwm_settings)}), maximum is {PWM_MAX_BATCH_OPERATIONS}"
            )
        
        _LOGGER.debug("Batch setting %d PWM parameters", len(pwm_settings))
        
        try:
            # Validate all parameters first
            commands = []
            for param, value in pwm_settings.items():
                # Validate parameter type and value
                if "enabled" in param:
                    self._validate_pwm_enabled_parameter(param)
                    val_str = "true" if value else "false"
                elif "duty-cycle" in param:
                    self._validate_pwm_duty_cycle_parameter(param)
                    self._validate_pwm_duty_cycle_value(value)
                    val_str = str(value)
                elif "frequency" in param:
                    self._validate_pwm_frequency_parameter(param)
                    self._validate_pwm_frequency_value(value)
                    val_str = str(value)
                else:
                    raise CresControlValidationError(f"Unknown PWM parameter type: {param}")
                
                commands.append(f"{param}={val_str}")
            
            # Execute batch command
            response = await self.send_commands(commands)
            
            _LOGGER.debug("PWM batch operation successful: %d parameters updated", len(commands))
            return response
            
        except CresControlError as err:
            error_msg = f"Failed to execute PWM batch operation: {err}"
            _LOGGER.error(error_msg)
            raise CresControlDeviceError(error_msg) from err

    def _validate_pwm_enabled_parameter(self, parameter: str) -> None:
        """Validate PWM enabled parameter name.
        
        Parameters
        ----------
        parameter: str
            Parameter name to validate.
            
        Raises
        ------
        CresControlValidationError
            If the parameter is invalid or not PWM-capable.
        """
        from .const import PWM_CAPABLE_OUTPUTS, PWM_CAPABLE_SWITCHES, PWM_ERROR_OUTPUT_NOT_CAPABLE, PWM_ERROR_SWITCH_NOT_CAPABLE
        
        self._validate_parameter(parameter)
        
        if not parameter.endswith(":pwm-enabled"):
            raise CresControlValidationError(f"Invalid PWM enabled parameter format: {parameter}")
        
        # Extract device type and validate PWM capability
        if parameter.startswith("out-"):
            device = parameter.split(":")[0]
            if device not in PWM_CAPABLE_OUTPUTS:
                raise CresControlValidationError(f"{PWM_ERROR_OUTPUT_NOT_CAPABLE}: {device}")
        elif parameter.startswith("switch-"):
            device = parameter.split(":")[0]
            if device not in PWM_CAPABLE_SWITCHES:
                raise CresControlValidationError(f"{PWM_ERROR_SWITCH_NOT_CAPABLE}: {device}")
        else:
            raise CresControlValidationError(f"Unknown device type for PWM parameter: {parameter}")

    def _validate_pwm_duty_cycle_parameter(self, parameter: str) -> None:
        """Validate PWM duty cycle parameter name.
        
        Parameters
        ----------
        parameter: str
            Parameter name to validate.
            
        Raises
        ------
        CresControlValidationError
            If the parameter is invalid or not PWM-capable.
        """
        from .const import PWM_CAPABLE_OUTPUTS, PWM_CAPABLE_SWITCHES, PWM_ERROR_OUTPUT_NOT_CAPABLE, PWM_ERROR_SWITCH_NOT_CAPABLE
        
        self._validate_parameter(parameter)
        
        if not parameter.endswith(":duty-cycle"):
            raise CresControlValidationError(f"Invalid PWM duty cycle parameter format: {parameter}")
        
        # Extract device type and validate PWM capability
        if parameter.startswith("out-"):
            device = parameter.split(":")[0]
            if device not in PWM_CAPABLE_OUTPUTS:
                raise CresControlValidationError(f"{PWM_ERROR_OUTPUT_NOT_CAPABLE}: {device}")
        elif parameter.startswith("switch-"):
            device = parameter.split(":")[0]
            if device not in PWM_CAPABLE_SWITCHES:
                raise CresControlValidationError(f"{PWM_ERROR_SWITCH_NOT_CAPABLE}: {device}")
        else:
            raise CresControlValidationError(f"Unknown device type for PWM parameter: {parameter}")

    def _validate_pwm_frequency_parameter(self, parameter: str) -> None:
        """Validate PWM frequency parameter name.
        
        Parameters
        ----------
        parameter: str
            Parameter name to validate.
            
        Raises
        ------
        CresControlValidationError
            If the parameter is invalid or not PWM-capable.
        """
        from .const import PWM_CAPABLE_OUTPUTS, PWM_CAPABLE_SWITCHES, PWM_ERROR_OUTPUT_NOT_CAPABLE, PWM_ERROR_SWITCH_NOT_CAPABLE
        
        self._validate_parameter(parameter)
        
        if not parameter.endswith(":pwm-frequency"):
            raise CresControlValidationError(f"Invalid PWM frequency parameter format: {parameter}")
        
        # Extract device type and validate PWM capability
        if parameter.startswith("out-"):
            device = parameter.split(":")[0]
            if device not in PWM_CAPABLE_OUTPUTS:
                raise CresControlValidationError(f"{PWM_ERROR_OUTPUT_NOT_CAPABLE}: {device}")
        elif parameter.startswith("switch-"):
            device = parameter.split(":")[0]
            if device not in PWM_CAPABLE_SWITCHES:
                raise CresControlValidationError(f"{PWM_ERROR_SWITCH_NOT_CAPABLE}: {device}")
        else:
            raise CresControlValidationError(f"Unknown device type for PWM parameter: {parameter}")

    def _validate_pwm_duty_cycle_value(self, duty_cycle: float) -> None:
        """Validate PWM duty cycle value.
        
        Parameters
        ----------
        duty_cycle: float
            Duty cycle percentage to validate.
            
        Raises
        ------
        CresControlValidationError
            If the duty cycle is invalid.
        """
        from .const import PWM_DUTY_CYCLE_MIN, PWM_DUTY_CYCLE_MAX, PWM_ERROR_INVALID_DUTY_CYCLE
        
        if not isinstance(duty_cycle, (int, float)):
            raise CresControlValidationError("PWM duty cycle must be a number")
        
        if not (PWM_DUTY_CYCLE_MIN <= duty_cycle <= PWM_DUTY_CYCLE_MAX):
            raise CresControlValidationError(
                f"{PWM_ERROR_INVALID_DUTY_CYCLE}: {duty_cycle} (range: {PWM_DUTY_CYCLE_MIN}-{PWM_DUTY_CYCLE_MAX})"
            )

    def _validate_pwm_frequency_value(self, frequency: float) -> None:
        """Validate PWM frequency value.
        
        Parameters
        ----------
        frequency: float
            PWM frequency to validate.
            
        Raises
        ------
        CresControlValidationError
            If the frequency is invalid.
        """
        from .const import PWM_FREQUENCY_MIN, PWM_FREQUENCY_MAX, PWM_ERROR_INVALID_FREQUENCY
        
        if not isinstance(frequency, (int, float)):
            raise CresControlValidationError("PWM frequency must be a number")
        
        if not (PWM_FREQUENCY_MIN <= frequency <= PWM_FREQUENCY_MAX):
            raise CresControlValidationError(
                f"{PWM_ERROR_INVALID_FREQUENCY}: {frequency} (range: {PWM_FREQUENCY_MIN}-{PWM_FREQUENCY_MAX})"
            )

    # =============================================================================
    # Helper Methods for Data Validation and Parsing
    # =============================================================================

    def _parse_boolean_value(self, value: Any, context: str) -> bool:
        """Parse and validate boolean value from device response.
        
        Parameters
        ----------
        value: Any
            Raw value from device.
        context: str
            Context for error messages.
            
        Returns
        -------
        bool
            Parsed boolean value.
            
        Raises
        ------
        CresControlValidationError
            If the value cannot be parsed as a boolean.
        """
        if value in ("1", 1, "true", True, "on", "enabled"):
            return True
        elif value in ("0", 0, "false", False, "off", "disabled"):
            return False
        else:
            raise CresControlValidationError(f"Invalid boolean value for {context}: {value}")

    def _parse_float_value(self, value: Any, context: str, min_val: float = None, max_val: float = None) -> float:
        """Parse and validate float value from device response.
        
        Parameters
        ----------
        value: Any
            Raw value from device.
        context: str
            Context for error messages.
        min_val: float, optional
            Minimum allowed value.
        max_val: float, optional
            Maximum allowed value.
            
        Returns
        -------
        float
            Parsed and validated float value.
            
        Raises
        ------
        CresControlValidationError
            If the value cannot be parsed or is out of range.
        """
        try:
            float_val = float(value)
        except (ValueError, TypeError) as err:
            raise CresControlValidationError(f"Invalid numeric value for {context}: {value}") from err
        
        if min_val is not None and float_val < min_val:
            raise CresControlValidationError(f"{context} value {float_val} below minimum {min_val}")
        
        if max_val is not None and float_val > max_val:
            raise CresControlValidationError(f"{context} value {float_val} above maximum {max_val}")
        
        return float_val

    def _parse_int_value(self, value: Any, context: str, min_val: int = None, max_val: int = None) -> int:
        """Parse and validate integer value from device response.
        
        Parameters
        ----------
        value: Any
            Raw value from device.
        context: str
            Context for error messages.
        min_val: int, optional
            Minimum allowed value.
        max_val: int, optional
            Maximum allowed value.
            
        Returns
        -------
        int
            Parsed and validated integer value.
            
        Raises
        ------
        CresControlValidationError
            If the value cannot be parsed or is out of range.
        """
        try:
            int_val = int(float(value))  # Convert via float to handle "123.0" format
        except (ValueError, TypeError) as err:
            raise CresControlValidationError(f"Invalid integer value for {context}: {value}") from err
        
        if min_val is not None and int_val < min_val:
            raise CresControlValidationError(f"{context} value {int_val} below minimum {min_val}")
        
        if max_val is not None and int_val > max_val:
            raise CresControlValidationError(f"{context} value {int_val} above maximum {max_val}")
        
        return int_val
    # =============================================================================
    # WebSocket Integration Methods
    # =============================================================================

    def _setup_websocket_handlers(self) -> None:
        """Set up WebSocket message and status handlers."""
        if not self._websocket_client:
            return
            
        from .const import WEBSOCKET_MESSAGE_TYPE_DATA
        
        # Add message handler for data updates
        self._websocket_client.add_message_handler(
            WEBSOCKET_MESSAGE_TYPE_DATA,
            self._handle_websocket_data
        )
        
        # Add status handler for connection status changes
        self._websocket_client.add_status_handler(self._handle_websocket_status)
        
        # Add error handler for WebSocket errors
        self._websocket_client.add_error_handler(self._handle_websocket_error)

    async def _handle_websocket_data(self, message: Dict[str, Any]) -> None:
        """Handle WebSocket data messages.
        
        Parameters
        ----------
        message: Dict[str, Any]
            WebSocket message containing data updates.
        """
        data = message.get("data", {})
        
        _LOGGER.debug("Received WebSocket data update: %s", data)
        
        # Notify all registered data handlers
        for handler in self._websocket_data_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as err:
                _LOGGER.error("Error in WebSocket data handler: %s", err)

    async def _handle_websocket_status(self, status: str) -> None:
        """Handle WebSocket status changes.
        
        Parameters
        ----------
        status: str
            New WebSocket connection status.
        """
        _LOGGER.debug("WebSocket status changed to: %s", status)

    async def _handle_websocket_error(self, error: Exception) -> None:
        """Handle WebSocket errors.
        
        Parameters
        ----------
        error: Exception
            WebSocket error that occurred.
        """
        _LOGGER.warning("WebSocket error: %s", error)

    async def enable_websocket(self) -> bool:
        """Enable WebSocket connectivity.
        
        Returns
        -------
        bool
            True if WebSocket was enabled successfully, False otherwise.
        """
        if self._websocket_enabled:
            return True
            
        _LOGGER.info("Enabling WebSocket connectivity for %s", self._host)
        
        if not self._websocket_client:
            self._websocket_client = CresControlWebSocketClient(
                host=self._host,
                session=self._session,
                port=self._websocket_port,
                path=self._websocket_path,
                timeout=self._base_timeout
            )
            self._setup_websocket_handlers()
        
        try:
            success = await self._websocket_client.connect()
            if success:
                self._websocket_enabled = True
                return True
            else:
                _LOGGER.warning("WebSocket connection failed for %s", self._host)
                return False
        except Exception as err:
            _LOGGER.error("Failed to enable WebSocket: %s", err)
            return False

    async def disable_websocket(self) -> None:
        """Disable WebSocket connectivity."""
        if self._websocket_enabled and self._websocket_client:
            _LOGGER.info("Disabling WebSocket connectivity for %s", self._host)
            self._websocket_enabled = False
            
            try:
                await self._websocket_client.disconnect()
            except Exception as err:
                _LOGGER.warning("Error disconnecting WebSocket: %s", err)
            finally:
                self._websocket_client = None

    async def _subscribe_to_all_data(self) -> None:
        """Subscribe to all data topics for comprehensive updates."""
        if not self._websocket_client or not self._websocket_client.is_connected:
            return
            
        from .const import (
            WEBSOCKET_TOPIC_ALL, WEBSOCKET_TOPIC_FAN, WEBSOCKET_TOPIC_OUTPUTS,
            WEBSOCKET_TOPIC_INPUTS, WEBSOCKET_TOPIC_SWITCHES, WEBSOCKET_TOPIC_PWM
        )
        
        topics = [
            WEBSOCKET_TOPIC_ALL,
            WEBSOCKET_TOPIC_FAN,
            WEBSOCKET_TOPIC_OUTPUTS,
            WEBSOCKET_TOPIC_INPUTS,
            WEBSOCKET_TOPIC_SWITCHES,
            WEBSOCKET_TOPIC_PWM,
        ]
        
        for topic in topics:
            try:
                await self._websocket_client.subscribe(topic)
            except Exception as err:
                _LOGGER.warning("Failed to subscribe to WebSocket topic %s: %s", topic, err)

    def add_websocket_data_handler(self, handler: Callable) -> None:
        """Add a handler for WebSocket data updates.
        
        Parameters
        ----------
        handler: Callable
            Handler function to call when WebSocket data is received.
        """
        self._websocket_data_handlers.add(handler)

    def remove_websocket_data_handler(self, handler: Callable) -> None:
        """Remove a WebSocket data handler.
        
        Parameters
        ----------
        handler: Callable
            Handler function to remove.
        """
        self._websocket_data_handlers.discard(handler)

    @property
    def websocket_enabled(self) -> bool:
        """Check if WebSocket is enabled."""
        return self._websocket_enabled

    @property
    def websocket_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return (self._websocket_enabled and 
                self._websocket_client is not None and 
                self._websocket_client.is_connected)

    def get_websocket_status(self) -> Dict[str, Any]:
        """Get WebSocket connection status and statistics.
        
        Returns
        -------
        Dict[str, Any]
            WebSocket status information.
        """
        if not self._websocket_client:
            from .const import WEBSOCKET_STATUS_DISABLED
            return {
                "enabled": False,
                "status": WEBSOCKET_STATUS_DISABLED,
                "connected": False,
            }
        
        stats = self._websocket_client.get_statistics()
        stats["enabled"] = self._websocket_enabled
        return stats

    async def test_websocket_connection(self) -> bool:
        """Test WebSocket connection.
        
        Returns
        -------
        bool
            True if WebSocket connection test succeeds, False otherwise.
        """
        if not self._websocket_enabled:
            return False
            
        try:
            if not self._websocket_client:
                self._websocket_client = CresControlWebSocketClient(
                    host=self._host,
                    session=self._session,
                    port=self._websocket_port,
                    path=self._websocket_path,
                    timeout=self._base_timeout
                )
                self._setup_websocket_handlers()
            
            await self._websocket_client.connect()
            
            # Send a test ping
            from .const import WEBSOCKET_MESSAGE_TYPE_PING
            await self._websocket_client.send_message(WEBSOCKET_MESSAGE_TYPE_PING)
            
            return True
            
        except Exception as err:
            _LOGGER.debug("WebSocket connection test failed: %s", err)
            return False

    async def send_websocket_command(self, command: str) -> None:
        """Send a command via WebSocket using CresControl protocol.
        
        Parameters
        ----------
        command: str
            Command to send (simple string, not JSON).
        """
        if not self.websocket_connected:
            raise CresControlWebSocketError("WebSocket not enabled")
        
        await self._websocket_client.send_command(command)
        
    def set_websocket_data_handler(self, handler: Callable) -> None:
        """Set WebSocket data handler for real-time updates.
        
        Parameters
        ----------
        handler: Callable
            Handler function to call when WebSocket data is received.
        """
        if self._websocket_client:
            self._websocket_client.set_data_handler(handler)


class CresControlWebSocketClient:
   """WebSocket client for real-time communication with CresControl devices."""
   
   def __init__(
       self,
       host: str,
       session: ClientSession,
       port: int = 8080,
       path: str = "/ws",
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
           WebSocket port (default: 8080).
       path: str
           WebSocket endpoint path (default: "/ws").
       timeout: int
           Connection timeout in seconds (default: 30).
       """
       from .const import (
           WEBSOCKET_CONNECT_TIMEOUT, WEBSOCKET_PING_INTERVAL, WEBSOCKET_PING_TIMEOUT,
           WEBSOCKET_CLOSE_TIMEOUT, WEBSOCKET_MAX_SIZE, WEBSOCKET_MAX_QUEUE,
           WEBSOCKET_RECONNECT_DELAY, WEBSOCKET_RECONNECT_MAX_DELAY,
           WEBSOCKET_RECONNECT_MULTIPLIER, WEBSOCKET_RECONNECT_MAX_ATTEMPTS,
           WEBSOCKET_RECONNECT_JITTER, WEBSOCKET_STATUS_DISCONNECTED,
           WEBSOCKET_COMPRESSION_ENABLED, WEBSOCKET_BUFFER_SIZE
       )
       
       self._host = host
       self._port = port
       self._path = path
       self._session = session
       self._timeout = timeout
       self._ws_url = f"ws://{host}:{port}{path}"
       
       # Connection state
       self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
       self._status = WEBSOCKET_STATUS_DISCONNECTED
       self._connection_task: Optional[asyncio.Task] = None
       self._reconnect_task: Optional[asyncio.Task] = None
       self._ping_task: Optional[asyncio.Task] = None
       
       # Event handlers
       self._message_handlers: Dict[str, Set[Callable]] = {}
       self._status_handlers: Set[Callable] = set()
       self._error_handlers: Set[Callable] = set()
       
       # Reconnection state
       self._reconnect_delay = WEBSOCKET_RECONNECT_DELAY
       self._reconnect_attempts = 0
       self._max_reconnect_attempts = WEBSOCKET_RECONNECT_MAX_ATTEMPTS
       self._should_reconnect = True
       
       # Configuration
       self._connect_timeout = WEBSOCKET_CONNECT_TIMEOUT
       self._ping_interval = WEBSOCKET_PING_INTERVAL
       self._ping_timeout = WEBSOCKET_PING_TIMEOUT
       self._close_timeout = WEBSOCKET_CLOSE_TIMEOUT
       self._max_size = WEBSOCKET_MAX_SIZE
       self._max_queue = WEBSOCKET_MAX_QUEUE
       self._compression = WEBSOCKET_COMPRESSION_ENABLED
       self._buffer_size = WEBSOCKET_BUFFER_SIZE
       
       # Statistics
       self._messages_received = 0
       self._messages_sent = 0
       self._connection_time: Optional[datetime] = None
       self._last_ping_time: Optional[datetime] = None
       self._last_pong_time: Optional[datetime] = None
       
       # Subscriptions and data handling
       self._subscriptions: Set[str] = set()
       self._data_handler: Optional[Callable] = None
       
   async def connect(self) -> bool:
       """Connect to the WebSocket server."""
       from .const import WEBSOCKET_STATUS_CONNECTING, WEBSOCKET_STATUS_CONNECTED
       
       if self._websocket and not self._websocket.closed:
           _LOGGER.debug("WebSocket already connected to %s", self._ws_url)
           return
           
       _LOGGER.info("Connecting to WebSocket at %s", self._ws_url)
       self._status = WEBSOCKET_STATUS_CONNECTING
       await self._notify_status_change()
       
       try:
           timeout = aiohttp.ClientTimeout(total=self._connect_timeout)
           
           self._websocket = await self._session.ws_connect(
               self._ws_url,
               timeout=timeout,
               max_msg_size=self._max_size,
               compress=self._compression,
               heartbeat=self._ping_interval,
           )
           
           self._status = WEBSOCKET_STATUS_CONNECTED
           self._connection_time = dt_util.utcnow()
           self._reconnect_attempts = 0
           self._reconnect_delay = WEBSOCKET_RECONNECT_DELAY
           
           _LOGGER.info("WebSocket connected successfully to %s", self._ws_url)
           await self._notify_status_change()
           
           # Start background tasks
           self._connection_task = asyncio.create_task(self._handle_messages())
           self._ping_task = asyncio.create_task(self._ping_loop())
           
           # Resubscribe to previously subscribed topics
           if self._subscriptions:
               await self._resubscribe()
               
       except Exception as err:
           self._status = WEBSOCKET_STATUS_DISCONNECTED
           await self._notify_status_change()
           error_msg = f"Failed to connect to WebSocket: {err}"
           _LOGGER.error(error_msg)
           await self._notify_error(CresControlWebSocketError(error_msg))
           raise CresControlWebSocketError(error_msg) from err
   
   async def disconnect(self) -> None:
       """Disconnect from the WebSocket server."""
       from .const import WEBSOCKET_STATUS_DISCONNECTED
       
       _LOGGER.info("Disconnecting from WebSocket at %s", self._ws_url)
       self._should_reconnect = False
       
       # Cancel background tasks
       if self._ping_task:
           self._ping_task.cancel()
           try:
               await self._ping_task
           except asyncio.CancelledError:
               pass
           self._ping_task = None
           
       if self._connection_task:
           self._connection_task.cancel()
           try:
               await self._connection_task
           except asyncio.CancelledError:
               pass
           self._connection_task = None
           
       if self._reconnect_task:
           self._reconnect_task.cancel()
           try:
               await self._reconnect_task
           except asyncio.CancelledError:
               pass
           self._reconnect_task = None
       
       # Close WebSocket connection
       if self._websocket and not self._websocket.closed:
           try:
               await asyncio.wait_for(
                   self._websocket.close(),
                   timeout=self._close_timeout
               )
           except asyncio.TimeoutError:
               _LOGGER.warning("WebSocket close timeout, forcing closure")
           except Exception as err:
               _LOGGER.warning("Error closing WebSocket: %s", err)
       
       self._websocket = None
       self._status = WEBSOCKET_STATUS_DISCONNECTED
       self._connection_time = None
       await self._notify_status_change()
       
       _LOGGER.info("WebSocket disconnected from %s", self._ws_url)
   
   async def send_command(self, command: str) -> None:
       """Send a command to the WebSocket server using CresControl protocol.
       
       Parameters
       ----------
       command: str
           Command string to send (not JSON).
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
       """Subscribe to data updates using CresControl protocol."""
       if not self._websocket or self._websocket.closed:
           return
           
       try:
           # Try different subscription commands to see what works
           subscription_commands = [
               "subscription:subscribe",
               "subscription:subscribe:all",
               "subscribe:all"
           ]
           
           for cmd in subscription_commands:
               try:
                   await self.send_command(cmd)
                   _LOGGER.debug("Sent subscription command: %s", cmd)
                   break  # Stop after first successful command
               except Exception as e:
                   _LOGGER.debug("Subscription command %s failed: %s", cmd, e)
                   continue
           
       except Exception as e:
           _LOGGER.warning("Failed to subscribe to updates: %s", e)
           # Don't raise error - subscription failure shouldn't prevent connection
   
   def set_data_handler(self, handler: Callable) -> None:
       """Set handler for data updates.
       
       Parameters
       ----------
       handler: Callable
           Function to call when data updates are received.
       """
       self._data_handler = handler
   
   async def subscribe(self, topic: str) -> None:
       """Subscribe to a WebSocket topic.
       
       Parameters
       ----------
       topic: str
           Topic to subscribe to.
       """
       from .const import WEBSOCKET_MESSAGE_TYPE_SUBSCRIBE
       
       self._subscriptions.add(topic)
       
       if self._websocket and not self._websocket.closed:
           await self.send_message(WEBSOCKET_MESSAGE_TYPE_SUBSCRIBE, {"topic": topic})
           _LOGGER.debug("Subscribed to WebSocket topic: %s", topic)
   
   async def unsubscribe(self, topic: str) -> None:
       """Unsubscribe from a WebSocket topic.
       
       Parameters
       ----------
       topic: str
           Topic to unsubscribe from.
       """
       from .const import WEBSOCKET_MESSAGE_TYPE_UNSUBSCRIBE
       
       self._subscriptions.discard(topic)
       
       if self._websocket and not self._websocket.closed:
           await self.send_message(WEBSOCKET_MESSAGE_TYPE_UNSUBSCRIBE, {"topic": topic})
           _LOGGER.debug("Unsubscribed from WebSocket topic: %s", topic)
   
   def add_message_handler(self, message_type: str, handler: Callable) -> None:
       """Add a handler for specific message types.
       
       Parameters
       ----------
       message_type: str
           Type of message to handle.
       handler: Callable
           Handler function to call when message is received.
       """
       if message_type not in self._message_handlers:
           self._message_handlers[message_type] = set()
       self._message_handlers[message_type].add(handler)
   
   def remove_message_handler(self, message_type: str, handler: Callable) -> None:
       """Remove a message handler.
       
       Parameters
       ----------
       message_type: str
           Type of message.
       handler: Callable
           Handler function to remove.
       """
       if message_type in self._message_handlers:
           self._message_handlers[message_type].discard(handler)
   
   def add_status_handler(self, handler: Callable) -> None:
       """Add a handler for status changes.
       
       Parameters
       ----------
       handler: Callable
           Handler function to call when status changes.
       """
       self._status_handlers.add(handler)
   
   def remove_status_handler(self, handler: Callable) -> None:
       """Remove a status handler.
       
       Parameters
       ----------
       handler: Callable
           Handler function to remove.
       """
       self._status_handlers.discard(handler)
   
   def add_error_handler(self, handler: Callable) -> None:
       """Add a handler for errors.
       
       Parameters
       ----------
       handler: Callable
           Handler function to call when errors occur.
       """
       self._error_handlers.add(handler)
   
   def remove_error_handler(self, handler: Callable) -> None:
       """Remove an error handler.
       
       Parameters
       ----------
       handler: Callable
           Handler function to remove.
       """
       self._error_handlers.discard(handler)
   
   @property
   def is_connected(self) -> bool:
       """Check if WebSocket is connected."""
       return self._websocket is not None and not self._websocket.closed
   
   @property
   def status(self) -> str:
       """Get current connection status."""
       return self._status
   
   def get_statistics(self) -> Dict[str, Any]:
       """Get WebSocket connection statistics.
       
       Returns
       -------
       Dict[str, Any]
           Statistics about the WebSocket connection.
       """
       return {
           "status": self._status,
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
           "reconnect_attempts": self._reconnect_attempts,
           "subscriptions": list(self._subscriptions),
           "last_ping": (
               self._last_ping_time.isoformat()
               if self._last_ping_time else None
           ),
           "last_pong": (
               self._last_pong_time.isoformat()
               if self._last_pong_time else None
           ),
       }
   
   async def _handle_messages(self) -> None:
       """Handle incoming WebSocket messages."""
       from .const import (
           WEBSOCKET_MESSAGE_TYPE_PONG, WEBSOCKET_STATUS_DISCONNECTED,
           WEBSOCKET_STATUS_RECONNECTING
       )
       
       _LOGGER.debug("Starting WebSocket message handler")
       
       try:
           async for msg in self._websocket:
               if msg.type == WSMsgType.TEXT:
                   try:
                       # CresControl uses text messages in format "param::value", not JSON
                       await self._process_crescontrol_message(msg.data)
                       self._messages_received += 1
                       
                   except Exception as err:
                       _LOGGER.warning("Error processing WebSocket message: %s", err)
                       
               elif msg.type == WSMsgType.ERROR:
                   error_msg = f"WebSocket error: {self._websocket.exception()}"
                   _LOGGER.error(error_msg)
                   await self._notify_error(CresControlWebSocketError(error_msg))
                   break
                   
               elif msg.type == WSMsgType.CLOSE:
                   _LOGGER.info("WebSocket connection closed by server")
                   break
                   
       except Exception as err:
           _LOGGER.error("Error in WebSocket message handler: %s", err)
           await self._notify_error(CresControlWebSocketError(f"Message handler error: {err}"))
       
       finally:
           if self._should_reconnect and self._status != WEBSOCKET_STATUS_DISCONNECTED:
               self._status = WEBSOCKET_STATUS_RECONNECTING
               await self._notify_status_change()
               self._reconnect_task = asyncio.create_task(self._reconnect_loop())
   
   async def _process_crescontrol_message(self, message: str) -> None:
       """Process a CresControl WebSocket message in format 'param::value'.
       
       Parameters
       ----------
       message: str
           Raw message text from WebSocket.
       """
       try:
           # CresControl WebSocket uses same format as HTTP: "param::value" or "command::response"
           if "::" in message:
               parts = message.split("::", 1)
               if len(parts) == 2:
                   param, value = parts
                   param = param.strip()
                   value = value.strip()
                   
                   # Skip error responses and subscription echoes
                   if value.startswith('{"error"') or param.startswith('{"command"'):
                       _LOGGER.debug("Skipping error/echo response: %s", message)
                       return
                   
                   # Handle parameter value updates
                   if ":" in param and not param.startswith("{"):
                       # This looks like a real parameter update (e.g., "in-a:voltage::3.14")
                       data_update = {param: value}
                       
                       if self._data_handler:
                           try:
                               if asyncio.iscoroutinefunction(self._data_handler):
                                   await self._data_handler(data_update)
                               else:
                                   self._data_handler(data_update)
                           except Exception as err:
                               _LOGGER.error("Error in WebSocket data handler: %s", err)
                       
                       _LOGGER.debug("Parsed WebSocket data update: %s = %s", param, value)
                   else:
                       _LOGGER.debug("Received WebSocket response: %s = %s", param, value)
           else:
               _LOGGER.debug("Received WebSocket message without delimiter: %s", message)
               
       except Exception as err:
           _LOGGER.error("Error processing CresControl WebSocket message: %s", err)
   
   async def _ping_loop(self) -> None:
       """Send periodic ping messages to keep connection alive."""
       from .const import WEBSOCKET_MESSAGE_TYPE_PING
       
       _LOGGER.debug("Starting WebSocket ping loop")
       
       try:
           while self.is_connected:
               await asyncio.sleep(self._ping_interval)
               
               if self.is_connected:
                   try:
                       await self.send_message(WEBSOCKET_MESSAGE_TYPE_PING)
                       self._last_ping_time = dt_util.utcnow()
                       
                   except Exception as err:
                       _LOGGER.warning("Failed to send WebSocket ping: %s", err)
                       break
                       
       except asyncio.CancelledError:
           _LOGGER.debug("WebSocket ping loop cancelled")
       except Exception as err:
           _LOGGER.error("Error in WebSocket ping loop: %s", err)
   
   async def _reconnect_loop(self) -> None:
       """Handle automatic reconnection with exponential backoff."""
       from .const import (
           WEBSOCKET_RECONNECT_MAX_DELAY, WEBSOCKET_RECONNECT_MULTIPLIER,
           WEBSOCKET_RECONNECT_JITTER, WEBSOCKET_STATUS_DISCONNECTED
       )
       
       _LOGGER.debug("Starting WebSocket reconnection loop")
       
       try:
           while self._should_reconnect:
               self._reconnect_attempts += 1
               
               if (self._max_reconnect_attempts > 0 and
                   self._reconnect_attempts > self._max_reconnect_attempts):
                   _LOGGER.error(
                       "WebSocket max reconnection attempts (%d) exceeded",
                       self._max_reconnect_attempts
                   )
                   self._status = WEBSOCKET_STATUS_DISCONNECTED
                   await self._notify_status_change()
                   break
               
               _LOGGER.info(
                   "WebSocket reconnection attempt %d (delay: %.1fs)",
                   self._reconnect_attempts, self._reconnect_delay
               )
               
               # Wait with jitter
               jitter = random.uniform(0, WEBSOCKET_RECONNECT_JITTER * self._reconnect_delay)
               await asyncio.sleep(self._reconnect_delay + jitter)
               
               try:
                   await self.connect()
                   _LOGGER.info("WebSocket reconnection successful")
                   break
                   
               except Exception as err:
                   _LOGGER.warning("WebSocket reconnection failed: %s", err)
                   
                   # Increase delay for next attempt
                   self._reconnect_delay = min(
                       self._reconnect_delay * WEBSOCKET_RECONNECT_MULTIPLIER,
                       WEBSOCKET_RECONNECT_MAX_DELAY
                   )
                   
       except asyncio.CancelledError:
           _LOGGER.debug("WebSocket reconnection loop cancelled")
       except Exception as err:
           _LOGGER.error("Error in WebSocket reconnection loop: %s", err)
           self._status = WEBSOCKET_STATUS_DISCONNECTED
           await self._notify_status_change()
   
   async def _resubscribe(self) -> None:
       """Resubscribe to topics after reconnection."""
       from .const import WEBSOCKET_MESSAGE_TYPE_SUBSCRIBE
       
       if not self._subscriptions:
           return
           
       _LOGGER.debug("Resubscribing to %d WebSocket topics", len(self._subscriptions))
       
       for topic in self._subscriptions:
           try:
               await self.send_message(WEBSOCKET_MESSAGE_TYPE_SUBSCRIBE, {"topic": topic})
           except Exception as err:
               _LOGGER.warning("Failed to resubscribe to topic %s: %s", topic, err)
   
   async def _notify_status_change(self) -> None:
       """Notify all status handlers of status changes."""
       for handler in self._status_handlers:
           try:
               if asyncio.iscoroutinefunction(handler):
                   await handler(self._status)
               else:
                   handler(self._status)
           except Exception as err:
               _LOGGER.error("Error in WebSocket status handler: %s", err)
   
   async def _notify_error(self, error: Exception) -> None:
       """Notify all error handlers of errors.
       
       Parameters
       ----------
       error: Exception
           Error that occurred.
       """
       for handler in self._error_handlers:
           try:
               if asyncio.iscoroutinefunction(handler):
                   await handler(error)
               else:
                   handler(error)
           except Exception as err:
               _LOGGER.error("Error in WebSocket error handler: %s", err)
