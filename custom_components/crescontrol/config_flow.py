"""
Configuration flow for the CresControl integration.

This module implements the UI flow presented to the user when they add
a new CresControl device in Home Assistant. The only required piece of
information is the host (IP address or hostname) of the device. The flow
verifies connectivity by performing a simple read request against the
device. If the device cannot be reached, the user receives an error and
is invited to correct the host entry. A unique ID equal to the host is
used to prevent multiple configurations for the same device.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp import ClientTimeout

from .api import CresControlClient, CresControlValidationError, CresControlNetworkError, CresControlDeviceError, CresControlWebSocketError
from .const import (
    DOMAIN,
    MIN_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    CONF_UPDATE_INTERVAL,
    CONF_WEBSOCKET_ENABLED,
    CONF_WEBSOCKET_PORT,
    CONF_WEBSOCKET_PATH,
    DEFAULT_WEBSOCKET_ENABLED,
    DEFAULT_WEBSOCKET_PORT,
    DEFAULT_WEBSOCKET_PATH,
    CONFIG_FLOW_RETRY_ATTEMPTS,
    CONFIG_FLOW_RETRY_DELAY,
    CONFIG_FLOW_TIMEOUT,
    CONNECTION_TEST_TIMEOUT,
)


_LOGGER = logging.getLogger(__name__)


class CresControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CresControl."""

    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step where the user enters the host with enhanced error handling."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            host: str = user_input["host"].strip()
            update_interval: int = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS)
            websocket_enabled: bool = user_input.get(CONF_WEBSOCKET_ENABLED, DEFAULT_WEBSOCKET_ENABLED)
            websocket_port: int = user_input.get(CONF_WEBSOCKET_PORT, DEFAULT_WEBSOCKET_PORT)
            websocket_path: str = user_input.get(CONF_WEBSOCKET_PATH, DEFAULT_WEBSOCKET_PATH).strip()
            
            # Validate update interval
            if not (MIN_UPDATE_INTERVAL <= update_interval <= MAX_UPDATE_INTERVAL):
                errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
            
            # Validate WebSocket configuration
            if websocket_enabled:
                if not (1 <= websocket_port <= 65535):
                    errors[CONF_WEBSOCKET_PORT] = "invalid_websocket_port"
                if not websocket_path.startswith("/"):
                    errors[CONF_WEBSOCKET_PATH] = "invalid_websocket_path"
            
            # Validate host format and connection with enhanced resilience
            if not errors:
                try:
                    # Check if this host is already configured
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    
                    # Perform connection validation with retry logic
                    await self._validate_connection_with_retry(
                        host, websocket_enabled, websocket_port, websocket_path
                    )
                    
                except CresControlValidationError as err:
                    _LOGGER.warning("Invalid host format for CresControl: %s - %s", host, err)
                    errors["base"] = "invalid_host"
                except CresControlNetworkError as err:
                    _LOGGER.warning("Network error connecting to CresControl at %s: %s", host, err)
                    errors["base"] = "cannot_connect"
                except CresControlDeviceError as err:
                    _LOGGER.warning("Device error with CresControl at %s: %s", host, err)
                    errors["base"] = "device_error"
                except CresControlWebSocketError as err:
                    _LOGGER.warning("WebSocket error with CresControl at %s: %s", host, err)
                    errors["base"] = "websocket_error"
                except TimeoutError as err:
                    _LOGGER.warning("Timeout connecting to CresControl at %s: %s", host, err)
                    errors["base"] = "timeout"
                except Exception as err:
                    _LOGGER.error("Unexpected error connecting to CresControl at %s: %s", host, err)
                    errors["base"] = "unknown"
                else:
                    _LOGGER.info("Successfully validated CresControl connection to %s", host)
                    return self.async_create_entry(
                        title=host,
                        data={
                            "host": host,
                            CONF_UPDATE_INTERVAL: update_interval,
                            CONF_WEBSOCKET_ENABLED: websocket_enabled,
                            CONF_WEBSOCKET_PORT: websocket_port,
                            CONF_WEBSOCKET_PATH: websocket_path,
                        }
                    )

    async def _validate_connection_with_retry(
        self,
        host: str,
        websocket_enabled: bool = False,
        websocket_port: int = DEFAULT_WEBSOCKET_PORT,
        websocket_path: str = DEFAULT_WEBSOCKET_PATH
    ) -> None:
        """Validate connection to CresControl device with retry logic and enhanced error handling."""
        session = async_get_clientsession(self.hass)
        client = CresControlClient(
            host,
            session,
            timeout=CONFIG_FLOW_TIMEOUT,
            websocket_enabled=websocket_enabled,
            websocket_port=websocket_port,
            websocket_path=websocket_path
        )
        
        last_exception = None
        
        for attempt in range(CONFIG_FLOW_RETRY_ATTEMPTS):
            try:
                _LOGGER.debug(
                    "CresControl config flow connection attempt %d/%d for %s",
                    attempt + 1, CONFIG_FLOW_RETRY_ATTEMPTS, host
                )
                
                # Test connection with a quick timeout
                test_timeout = CONNECTION_TEST_TIMEOUT if attempt == 0 else CONFIG_FLOW_TIMEOUT
                client._timeout = ClientTimeout(total=test_timeout)
                
                # Use a simple read command to ensure the device responds
                # We don't rely on a specific value being returned; absence of an exception is sufficient
                await client.get_value("in-a:voltage")
                
                # If WebSocket is enabled, also test WebSocket connectivity
                if websocket_enabled:
                    _LOGGER.debug("Testing WebSocket connection for config flow")
                    websocket_test_success = await client.test_websocket_connection()
                    if not websocket_test_success:
                        _LOGGER.warning("WebSocket connection test failed, but HTTP works")
                        # Note: We don't fail the entire config if WebSocket fails,
                        # as HTTP polling can still work
                
                _LOGGER.debug("CresControl config flow connection successful on attempt %d", attempt + 1)
                return  # Success - exit retry loop
                
            except CresControlNetworkError as err:
                last_exception = err
                _LOGGER.debug(
                    "CresControl config flow network error on attempt %d/%d: %s",
                    attempt + 1, CONFIG_FLOW_RETRY_ATTEMPTS, err
                )
                
                # For network errors, retry with progressive delay
                if attempt < CONFIG_FLOW_RETRY_ATTEMPTS - 1:
                    delay = CONFIG_FLOW_RETRY_DELAY * (attempt + 1)
                    _LOGGER.debug("Retrying CresControl connection in %.1f seconds", delay)
                    await asyncio.sleep(delay)
                    
            except CresControlDeviceError as err:
                last_exception = err
                _LOGGER.debug(
                    "CresControl config flow device error on attempt %d/%d: %s",
                    attempt + 1, CONFIG_FLOW_RETRY_ATTEMPTS, err
                )
                
                # For device errors, shorter retry delay
                if attempt < CONFIG_FLOW_RETRY_ATTEMPTS - 1:
                    delay = CONFIG_FLOW_RETRY_DELAY * 0.5
                    _LOGGER.debug("Retrying CresControl connection in %.1f seconds", delay)
                    await asyncio.sleep(delay)
                    
            except CresControlValidationError:
                # Validation errors don't benefit from retries
                raise
                
            except asyncio.TimeoutError as err:
                last_exception = TimeoutError(f"Connection timeout after {test_timeout}s")
                _LOGGER.debug(
                    "CresControl config flow timeout on attempt %d/%d",
                    attempt + 1, CONFIG_FLOW_RETRY_ATTEMPTS
                )
                
                # For timeouts, use longer delay and increase timeout for next attempt
                if attempt < CONFIG_FLOW_RETRY_ATTEMPTS - 1:
                    delay = CONFIG_FLOW_RETRY_DELAY * 1.5
                    _LOGGER.debug("Retrying CresControl connection in %.1f seconds", delay)
                    await asyncio.sleep(delay)
                    
            except Exception as err:
                last_exception = err
                _LOGGER.debug(
                    "CresControl config flow unexpected error on attempt %d/%d: %s",
                    attempt + 1, CONFIG_FLOW_RETRY_ATTEMPTS, err
                )
                # Don't retry on unexpected errors
                break
        
        # All attempts failed - raise the last exception
        _LOGGER.error(
            "CresControl config flow failed after %d attempts for %s: %s",
            CONFIG_FLOW_RETRY_ATTEMPTS, host, last_exception
        )
        
        if last_exception:
            raise last_exception
        else:
            raise CresControlNetworkError("Connection validation failed")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL_SECONDS): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
                ),
                vol.Optional(CONF_WEBSOCKET_ENABLED, default=DEFAULT_WEBSOCKET_ENABLED): bool,
                vol.Optional(CONF_WEBSOCKET_PORT, default=DEFAULT_WEBSOCKET_PORT): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_WEBSOCKET_PATH, default=DEFAULT_WEBSOCKET_PATH): str,
            }),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> CresControlOptionsFlow:
        """Get the options flow for this handler."""
        return CresControlOptionsFlow(config_entry)


class CresControlOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for CresControl."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            update_interval: int = user_input[CONF_UPDATE_INTERVAL]
            websocket_enabled: bool = user_input.get(CONF_WEBSOCKET_ENABLED, DEFAULT_WEBSOCKET_ENABLED)
            websocket_port: int = user_input.get(CONF_WEBSOCKET_PORT, DEFAULT_WEBSOCKET_PORT)
            websocket_path: str = user_input.get(CONF_WEBSOCKET_PATH, DEFAULT_WEBSOCKET_PATH).strip()
            
            # Validate update interval
            if not (MIN_UPDATE_INTERVAL <= update_interval <= MAX_UPDATE_INTERVAL):
                errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
            
            # Validate WebSocket configuration
            if websocket_enabled:
                if not (1 <= websocket_port <= 65535):
                    errors[CONF_WEBSOCKET_PORT] = "invalid_websocket_port"
                if not websocket_path.startswith("/"):
                    errors[CONF_WEBSOCKET_PATH] = "invalid_websocket_path"
            
            if not errors:
                # Update the config entry data
                new_data = dict(self.config_entry.data)
                new_data[CONF_UPDATE_INTERVAL] = update_interval
                new_data[CONF_WEBSOCKET_ENABLED] = websocket_enabled
                new_data[CONF_WEBSOCKET_PORT] = websocket_port
                new_data[CONF_WEBSOCKET_PATH] = websocket_path
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        # Get current values or defaults
        current_interval = self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS)
        current_websocket_enabled = self.config_entry.data.get(CONF_WEBSOCKET_ENABLED, DEFAULT_WEBSOCKET_ENABLED)
        current_websocket_port = self.config_entry.data.get(CONF_WEBSOCKET_PORT, DEFAULT_WEBSOCKET_PORT)
        current_websocket_path = self.config_entry.data.get(CONF_WEBSOCKET_PATH, DEFAULT_WEBSOCKET_PATH)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_UPDATE_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
                ),
                vol.Optional(CONF_WEBSOCKET_ENABLED, default=current_websocket_enabled): bool,
                vol.Optional(CONF_WEBSOCKET_PORT, default=current_websocket_port): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_WEBSOCKET_PATH, default=current_websocket_path): str,
            }),
            errors=errors,
        )
