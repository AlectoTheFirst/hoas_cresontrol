"""
Configuration flow for the CresControl integration.

This module implements the UI flow presented to the user when they add
a new CresControl device in Home Assistant. The only required piece of
information is the host (IP address or hostname) of the device.
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

from .api import CresControlClient, CresControlValidationError, CresControlNetworkError, CresControlDeviceError
from .const import (
    DOMAIN,
    MIN_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    CONF_UPDATE_INTERVAL,
    CONF_WEBSOCKET_ENABLED,
    CONF_WEBSOCKET_PORT,
    CONF_WEBSOCKET_PATH,
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
        """Handle the initial step where the user enters the host."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            host: str = user_input["host"].strip()
            update_interval: int = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS)
            websocket_enabled: bool = user_input.get(CONF_WEBSOCKET_ENABLED, True)
            websocket_port: int = user_input.get(CONF_WEBSOCKET_PORT, 81)
            websocket_path: str = user_input.get(CONF_WEBSOCKET_PATH, "/websocket").strip()
            
            # Validate update interval
            if not (MIN_UPDATE_INTERVAL <= update_interval <= MAX_UPDATE_INTERVAL):
                errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
            
            # Validate WebSocket configuration
            if websocket_enabled:
                if not (1 <= websocket_port <= 65535):
                    errors[CONF_WEBSOCKET_PORT] = "invalid_websocket_port"
                if not websocket_path.startswith("/"):
                    errors[CONF_WEBSOCKET_PATH] = "invalid_websocket_path"
            
            # Validate host format and connection
            if not errors:
                try:
                    # Check if this host is already configured
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    
                    # Perform connection validation
                    await self._validate_connection(host)
                    
                except CresControlValidationError as err:
                    _LOGGER.warning("Invalid host format for CresControl: %s - %s", host, err)
                    errors["base"] = "invalid_host"
                except CresControlNetworkError as err:
                    _LOGGER.warning("Network error connecting to CresControl at %s: %s", host, err)
                    errors["base"] = "cannot_connect"
                except CresControlDeviceError as err:
                    _LOGGER.warning("Device error with CresControl at %s: %s", host, err)
                    errors["base"] = "device_error"
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

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL_SECONDS): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
                ),
                vol.Optional(CONF_WEBSOCKET_ENABLED, default=True): bool,
                vol.Optional(CONF_WEBSOCKET_PORT, default=81): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_WEBSOCKET_PATH, default="/websocket"): str,
            }),
            errors=errors,
        )

    async def _validate_connection(self, host: str) -> None:
        """Validate connection to CresControl device."""
        session = async_get_clientsession(self.hass)
        client = CresControlClient(host, session, timeout=CONFIG_FLOW_TIMEOUT)
        
        # Use a simple read command to ensure the device responds
        await client.get_value("in-a:voltage")

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
            websocket_enabled: bool = user_input.get(CONF_WEBSOCKET_ENABLED, True)
            websocket_port: int = user_input.get(CONF_WEBSOCKET_PORT, 81)
            websocket_path: str = user_input.get(CONF_WEBSOCKET_PATH, "/websocket").strip()
            
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
        current_websocket_enabled = self.config_entry.data.get(CONF_WEBSOCKET_ENABLED, True)
        current_websocket_port = self.config_entry.data.get(CONF_WEBSOCKET_PORT, 81)
        current_websocket_path = self.config_entry.data.get(CONF_WEBSOCKET_PATH, "/websocket")

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