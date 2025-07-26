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
from homeassistant.helpers import device_registry as dr

from .websocket_client import CresControlWebSocketClient
from .hybrid_coordinator import CresControlHybridCoordinator
from .simple_http_client import SimpleCresControlHTTPClient
from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "number", "fan"]


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the CresControl integration from YAML (deprecated)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CresControl from a config entry created via the UI."""
    host = entry.data["host"]
    
    # Use default update interval (simplified configuration)
    update_interval = timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS)
    
    session = async_get_clientsession(hass)
    
    # Create WebSocket client for real-time data
    websocket_client = CresControlWebSocketClient(
        host=host,
        session=session,
        port=81,  # Fixed port based on testing
        path="/websocket"  # Fixed path based on testing
    )
    
    # Create HTTP client for fallback communication
    http_client = SimpleCresControlHTTPClient(host, session)
    
    # Create hybrid coordinator that prioritizes WebSocket with HTTP fallback
    coordinator = CresControlHybridCoordinator(
        hass=hass,
        http_client=http_client,
        websocket_client=websocket_client,
        host=host,
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
        "websocket_client": websocket_client,
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