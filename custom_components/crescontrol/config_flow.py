"""
Configuration flow for the CresControl integration.

Simplified configuration flow that only requires the host IP address
and performs basic connectivity testing.
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
from aiohttp import ClientTimeout, ClientError

from .simple_http_client import SimpleCresControlHTTPClient
from .const import DOMAIN

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
            
            # Basic host validation
            if not host:
                errors["host"] = "invalid_host"
            elif not self._is_valid_host(host):
                errors["host"] = "invalid_host"
            else:
                try:
                    # Check if this host is already configured
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    
                    # Perform simple connection validation
                    await self._validate_connection(host)
                    
                    _LOGGER.info("Successfully validated CresControl connection to %s", host)
                    return self.async_create_entry(
                        title=f"CresControl ({host})",
                        data={"host": host}
                    )
                    
                except Exception as err:
                    _LOGGER.warning("Failed to connect to CresControl at %s: %s", host, err)
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
            }),
            errors=errors,
        )

    def _is_valid_host(self, host: str) -> bool:
        """Validate host format (basic IP address or hostname check)."""
        import re
        
        # Check for basic IP address format first
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        if ip_pattern.match(host):
            # Validate IP address ranges
            parts = host.split('.')
            return all(0 <= int(part) <= 255 for part in parts)
        
        # If it looks like an incomplete IP (contains only digits and dots), reject it
        if re.match(r'^[\d.]+$', host):
            return False
        
        # Check for basic hostname format
        hostname_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$')
        return hostname_pattern.match(host) is not None

    async def _validate_connection(self, host: str) -> None:
        """Validate connection to CresControl device using simple connectivity test."""
        session = async_get_clientsession(self.hass)
        client = SimpleCresControlHTTPClient(host, session)
        
        # Try WebSocket connectivity first (known to work)
        try:
            result = await client.get_value("in-a:voltage")
            if result is not None:
                return  # WebSocket connection successful
        except Exception as e:
            _LOGGER.debug("WebSocket test failed: %s", e)
        
        # Try HTTP connectivity as fallback
        try:
            connected = await client.test_connectivity()
            if connected:
                return  # HTTP connection successful
        except Exception as e:
            _LOGGER.debug("HTTP test failed: %s", e)
        
        # If both fail, raise an error
        raise Exception("Unable to connect via WebSocket or HTTP")

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> CresControlOptionsFlow:
        """Get the options flow for this handler."""
        return CresControlOptionsFlow(config_entry)


class CresControlOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for CresControl (simplified)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Manage the options (currently no options available)."""
        # For now, no options are configurable in the simplified version
        # This can be extended later if needed
        return self.async_create_entry(title="", data={})