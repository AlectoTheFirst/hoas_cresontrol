"""Tests for the CresControl DataUpdateCoordinator."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from datetime import timedelta

from custom_components.crescontrol import async_setup_entry, async_unload_entry
from custom_components.crescontrol.api import (
    CresControlClient,
    CresControlNetworkError,
    CresControlDeviceError,
)
from custom_components.crescontrol.const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
)


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.config_entries = Mock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry."""
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {"host": "192.168.1.100"}
    return entry


@pytest.fixture
def mock_client():
    """Create a mock CresControlClient."""
    client = Mock(spec=CresControlClient)
    return client


@pytest.fixture
def sample_device_data():
    """Sample data that would be returned from the CresControl device."""
    return {
        "in-a:voltage": "3.14",
        "in-b:voltage": "2.71",
        "fan:enabled": "true",
        "fan:rpm": "1200",
        "switch-12v:enabled": "false",
        "switch-24v-a:enabled": "true",
        "switch-24v-b:enabled": "false",
        "out-a:enabled": "true",
        "out-a:voltage": "5.0",
        "out-b:enabled": "false",
        "out-b:voltage": "0.0",
        "out-c:enabled": "true",
        "out-c:voltage": "3.3",
        "out-d:enabled": "false",
        "out-d:voltage": "0.0",
        "out-e:enabled": "true",
        "out-e:voltage": "8.2",
        "out-f:enabled": "false",
        "out-f:voltage": "0.0",
    }


class TestCoordinatorDataFetching:
    """Test DataUpdateCoordinator data fetching functionality."""

    @pytest.mark.asyncio
    async def test_coordinator_setup_success(self, mock_hass, mock_config_entry, sample_device_data):
        """Test successful coordinator setup and initial data fetch."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Test the setup
            result = await async_setup_entry(mock_hass, mock_config_entry)
            
            assert result is True
            
            # Verify the coordinator was created and configured
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            
            assert "coordinator" in entry_data
            assert "client" in entry_data
            assert "device_info" in entry_data
            
            coordinator = entry_data["coordinator"]
            assert coordinator.name == "CresControl data"
            assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL
            
            # Verify the client was created correctly
            mock_client_class.assert_called_once_with("192.168.1.100", mock_session)
            
            # Verify platforms were set up
            mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
                mock_config_entry, ["sensor", "switch", "number"]
            )

    @pytest.mark.asyncio
    async def test_coordinator_data_update_success(self, mock_hass, mock_config_entry, sample_device_data):
        """Test successful data update through coordinator."""
        expected_commands = [
            "in-a:voltage",
            "in-b:voltage",
            "fan:enabled",
            "fan:rpm",
            "switch-12v:enabled",
            "switch-24v-a:enabled",
            "switch-24v-b:enabled",
            "out-a:enabled", "out-a:voltage",
            "out-b:enabled", "out-b:voltage",
            "out-c:enabled", "out-c:voltage",
            "out-d:enabled", "out-d:voltage",
            "out-e:enabled", "out-e:voltage",
            "out-f:enabled", "out-f:voltage",
        ]
        
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Trigger a data update
            await coordinator.async_request_refresh()
            
            # Verify the correct commands were sent
            mock_client.send_commands.assert_called_with(expected_commands)
            
            # Verify the data is available
            assert coordinator.data == sample_device_data

    @pytest.mark.asyncio
    async def test_coordinator_network_error_handling(self, mock_hass, mock_config_entry):
        """Test coordinator handling of network errors."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            # First call succeeds for initial setup, second call fails
            mock_client.send_commands = AsyncMock(
                side_effect=[{"in-a:voltage": "3.14"}, CresControlNetworkError("Network error")]
            )
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Trigger a data update that should fail
            with pytest.raises(UpdateFailed, match="Error communicating with CresControl at 192.168.1.100"):
                await coordinator.async_request_refresh()

    @pytest.mark.asyncio
    async def test_coordinator_device_error_handling(self, mock_hass, mock_config_entry):
        """Test coordinator handling of device errors."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            # First call succeeds for initial setup, second call fails
            mock_client.send_commands = AsyncMock(
                side_effect=[{"in-a:voltage": "3.14"}, CresControlDeviceError("Device error")]
            )
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Trigger a data update that should fail
            with pytest.raises(UpdateFailed, match="Error communicating with CresControl at 192.168.1.100"):
                await coordinator.async_request_refresh()

    @pytest.mark.asyncio
    async def test_coordinator_unexpected_error_handling(self, mock_hass, mock_config_entry):
        """Test coordinator handling of unexpected errors."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            # First call succeeds for initial setup, second call fails
            mock_client.send_commands = AsyncMock(
                side_effect=[{"in-a:voltage": "3.14"}, ValueError("Unexpected error")]
            )
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Trigger a data update that should fail
            with pytest.raises(UpdateFailed, match="Error communicating with CresControl at 192.168.1.100"):
                await coordinator.async_request_refresh()


class TestCoordinatorSetup:
    """Test coordinator setup and initialization."""

    @pytest.mark.asyncio
    async def test_initial_refresh_failure_raises_config_entry_not_ready(self, mock_hass, mock_config_entry):
        """Test that initial refresh failure raises ConfigEntryNotReady."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(side_effect=CresControlNetworkError("Connection failed"))
            mock_client_class.return_value = mock_client
            
            # The setup should raise ConfigEntryNotReady
            with pytest.raises(ConfigEntryNotReady, match="Unable to connect to CresControl"):
                await async_setup_entry(mock_hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_device_registry_setup(self, mock_hass, mock_config_entry, sample_device_data):
        """Test that device registry entry is created correctly."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Verify device registry entry was created
            mock_registry.async_get_or_create.assert_called_once_with(
                config_entry_id="test_entry_id",
                identifiers={(DOMAIN, "192.168.1.100")},
                name="CresControl (192.168.1.100)",
                manufacturer="Crescience",
                model="CresControl Cannabis Grow Controller",
                configuration_url="http://192.168.1.100",
            )

    @pytest.mark.asyncio
    async def test_coordinator_update_interval(self, mock_hass, mock_config_entry, sample_device_data):
        """Test that coordinator uses correct update interval."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_coordinator_custom_update_interval(self, mock_hass, sample_device_data):
        """Test that coordinator uses custom update interval from config entry."""
        # Create config entry with custom interval
        mock_config_entry = Mock(spec=ConfigEntry)
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.data = {"host": "192.168.1.100", CONF_UPDATE_INTERVAL: 30}
        mock_config_entry.async_on_unload = Mock(return_value=None)
        mock_config_entry.add_update_listener = Mock(return_value=None)
        
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Verify the update interval is custom value
            assert coordinator.update_interval == timedelta(seconds=30)

    @pytest.mark.asyncio
    async def test_coordinator_backward_compatibility_no_interval(self, mock_hass, sample_device_data):
        """Test backward compatibility when no update interval is specified."""
        # Create config entry without interval (old format)
        mock_config_entry = Mock(spec=ConfigEntry)
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.data = {"host": "192.168.1.100"}  # No interval specified
        mock_config_entry.async_on_unload = Mock(return_value=None)
        mock_config_entry.add_update_listener = Mock(return_value=None)
        
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Verify the update interval defaults to original default
            assert coordinator.update_interval == timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS)

    @pytest.mark.asyncio
    async def test_coordinator_reload_on_options_change(self, mock_hass, sample_device_data):
        """Test that coordinator is reloaded when options change."""
        from custom_components.crescontrol import async_reload_entry
        
        # Create config entry with initial interval
        mock_config_entry = Mock(spec=ConfigEntry)
        mock_config_entry.entry_id = "test_entry_id"
        mock_config_entry.data = {"host": "192.168.1.100", CONF_UPDATE_INTERVAL: 15}
        mock_config_entry.async_on_unload = Mock(return_value=None)
        mock_config_entry.add_update_listener = Mock(return_value=None)
        
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Verify initial interval
            assert coordinator.update_interval == timedelta(seconds=15)
            
            # Simulate options change by updating config entry data
            mock_config_entry.data = {"host": "192.168.1.100", CONF_UPDATE_INTERVAL: 60}
            
            # Test reload functionality
            await async_reload_entry(mock_hass, mock_config_entry)
            
            # Verify new coordinator has updated interval
            new_coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            assert new_coordinator.update_interval == timedelta(seconds=60)
            
            coordinator = mock_hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Verify the update interval is correct
            assert coordinator.update_interval == DEFAULT_UPDATE_INTERVAL
            assert coordinator.update_interval == timedelta(seconds=10)


class TestCoordinatorUnload:
    """Test coordinator unloading."""

    @pytest.mark.asyncio
    async def test_unload_entry_success(self, mock_hass, mock_config_entry, sample_device_data):
        """Test successful unloading of config entry."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Verify data is stored
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
            
            # Unload the entry
            result = await async_unload_entry(mock_hass, mock_config_entry)
            
            assert result is True
            
            # Verify platforms were unloaded
            mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
                mock_config_entry, ["sensor", "switch", "number"]
            )
            
            # Verify data was cleaned up
            assert mock_config_entry.entry_id not in mock_hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_unload_entry_failure(self, mock_hass, mock_config_entry, sample_device_data):
        """Test handling of unload failure."""
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_device_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            # Set up the integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Make unload fail
            mock_hass.config_entries.async_unload_platforms.return_value = False
            
            # Unload the entry
            result = await async_unload_entry(mock_hass, mock_config_entry)
            
            assert result is False
            
            # Verify data was NOT cleaned up since unload failed
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]


class TestLegacyYamlSetup:
    """Test legacy YAML setup functionality."""

    @pytest.mark.asyncio
    async def test_async_setup_yaml_deprecated(self, mock_hass):
        """Test that YAML setup returns True but does nothing."""
        from custom_components.crescontrol import async_setup
        
        result = await async_setup(mock_hass, {})
        
        # Should return True but not set up anything
        assert result is True
        
        # No data should be stored for YAML config
        assert DOMAIN not in mock_hass.data or not mock_hass.data[DOMAIN]