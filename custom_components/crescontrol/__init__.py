"""
Home Assistant integration for CresControl controllers.

This integration exposes the CresControl device to Home Assistant by
providing sensors, switches and numeric controls for the analog outputs,
fan and auxiliary switches. Communication with the device is done via
HTTP requests to its built‑in API with WebSocket support for real-time updates.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import device_registry as dr

from .api import CresControlClient, CresControlError
from .websocket_client import CresControlWebSocketClient
from .hybrid_coordinator import CresControlHybridCoordinator
from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    CONF_UPDATE_INTERVAL,
    CONF_WEBSOCKET_ENABLED,
    CONF_WEBSOCKET_PORT,
    CONF_WEBSOCKET_PATH,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number", "fan"]


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the CresControl integration from YAML (deprecated)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CresControl from a config entry created via the UI."""
    host = entry.data["host"]
    
    # Get configuration with defaults
    update_interval_seconds = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS)
    update_interval = timedelta(seconds=update_interval_seconds)
    websocket_enabled = entry.data.get(CONF_WEBSOCKET_ENABLED, True)
    websocket_port = entry.data.get(CONF_WEBSOCKET_PORT, 81)
    websocket_path = entry.data.get(CONF_WEBSOCKET_PATH, "/websocket")
    
    session = async_get_clientsession(hass)
    
    # Create HTTP client for fallback communication
    http_client = CresControlClient(host, session)
    
    # Create coordinator
    if websocket_enabled:
        # Create WebSocket client for real-time data
        websocket_client = CresControlWebSocketClient(
            host=host,
            session=session,
            port=websocket_port,
            path=websocket_path
        )
        
        # Create hybrid coordinator that prioritizes WebSocket with HTTP fallback
        coordinator = CresControlHybridCoordinator(
            hass=hass,
            http_client=http_client,
            websocket_client=websocket_client,
            host=host,
            update_interval=update_interval,
        )
    else:
        # Create simple HTTP-only coordinator
        async def update_method():
            commands = [
                'in-a:voltage', 'fan:enabled', 'fan:duty-cycle',
                'out-a:enabled', 'out-a:voltage', 'out-b:enabled', 'out-b:voltage'
            ]
            return await http_client.send_commands(commands)
        
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"CresControl {host}",
            update_method=update_method,
            update_interval=update_interval,
        )

    try:
        # Perform initial refresh
        _LOGGER.info("Performing initial connection test for CresControl at %s", host)
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("CresControl initial setup successful for %s", host)
        
    except Exception as err:
        error_msg = f"Unable to connect to CresControl at {host}: {err}"
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

    # Store data for platforms
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "http_client": http_client,
        "websocket_client": websocket_client if websocket_enabled else None,
        "coordinator": coordinator,
        "device_info": device_info,
    }

    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a CresControl config entry."""
    # Shutdown coordinator and clean up connections
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
        if coordinator and hasattr(coordinator, 'async_shutdown'):
            await coordinator.async_shutdown()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok