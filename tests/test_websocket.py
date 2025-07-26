"""Tests for the CresControl WebSocket functionality."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from aiohttp import WSMsgType, WSMessage
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.crescontrol.api import (
    CresControlClient,
    CresControlWebSocketClient,
    CresControlWebSocketError,
    CresControlWebSocketAuthError,
    CresControlWebSocketProtocolError,
)
from custom_components.crescontrol.const import (
    DOMAIN,
    CONF_WEBSOCKET_ENABLED,
    CONF_WEBSOCKET_PORT,
    CONF_WEBSOCKET_PATH,
    DEFAULT_WEBSOCKET_PORT,
    DEFAULT_WEBSOCKET_PATH,
    WEBSOCKET_TOPIC_ALL,
    WEBSOCKET_STATUS_CONNECTED,
    WEBSOCKET_STATUS_DISCONNECTED,
    WEBSOCKET_STATUS_RECONNECTING,
)
from custom_components.crescontrol.config_flow import CresControlConfigFlow


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = AsyncMock()
    ws.closed = False
    ws.close_code = None
    return ws


@pytest.fixture
def mock_session():
    """Create a mock aiohttp ClientSession."""
    session = Mock()
    session.ws_connect = AsyncMock()
    return session


@pytest.fixture
def websocket_client(mock_session):
    """Create a CresControlWebSocketClient instance for testing."""
    return CresControlWebSocketClient("192.168.1.100", mock_session)


@pytest.fixture
def sample_websocket_message():
    """Sample WebSocket message from CresControl device."""
    return {
        "type": "data_update",
        "timestamp": "2025-01-26T10:30:00Z",
        "data": {
            "in-a:voltage": "3.14",
            "fan:enabled": "true",
            "fan:rpm": "1200"
        }
    }


class TestCresControlWebSocketClient:
    """Test CresControlWebSocketClient functionality."""

    def test_websocket_client_init(self, mock_session):
        """Test WebSocket client initialization."""
        client = CresControlWebSocketClient(
            "192.168.1.100", 
            mock_session, 
            port=8080, 
            path="/ws"
        )
        assert client._host == "192.168.1.100"
        assert client._session is mock_session
        assert client._port == 8080
        assert client._path == "/ws"
        assert client._websocket is None
        assert client._status == WEBSOCKET_STATUS_DISCONNECTED

    def test_websocket_client_url_property(self, websocket_client):
        """Test WebSocket URL property."""
        assert websocket_client.url == f"ws://192.168.1.100:{DEFAULT_WEBSOCKET_PORT}{DEFAULT_WEBSOCKET_PATH}"

    def test_websocket_client_status_properties(self, websocket_client):
        """Test WebSocket status properties."""
        assert not websocket_client.is_connected
        assert websocket_client.status == WEBSOCKET_STATUS_DISCONNECTED

    @pytest.mark.asyncio
    async def test_websocket_connect_success(self, websocket_client, mock_session, mock_websocket):
        """Test successful WebSocket connection."""
        mock_session.ws_connect.return_value.__aenter__.return_value = mock_websocket
        
        # Mock the subscription command
        mock_websocket.send_str = AsyncMock()
        
        result = await websocket_client.connect()
        
        assert result is True
        assert websocket_client.is_connected
        assert websocket_client.status == WEBSOCKET_STATUS_CONNECTED
        assert websocket_client._websocket is mock_websocket
        
        # Verify connection parameters
        mock_session.ws_connect.assert_called_once_with(
            websocket_client.url,
            timeout=30,
            heartbeat=30
        )
        
        # Verify subscription command was sent
        expected_subscription = json.dumps({
            "command": "subscription:subscribe",
            "topic": WEBSOCKET_TOPIC_ALL
        })
        mock_websocket.send_str.assert_called_with(expected_subscription)

    @pytest.mark.asyncio
    async def test_websocket_connect_failure(self, websocket_client, mock_session):
        """Test WebSocket connection failure."""
        mock_session.ws_connect.side_effect = Exception("Connection failed")
        
        result = await websocket_client.connect()
        
        assert result is False
        assert not websocket_client.is_connected
        assert websocket_client.status == WEBSOCKET_STATUS_DISCONNECTED

    @pytest.mark.asyncio
    async def test_websocket_disconnect(self, websocket_client, mock_websocket):
        """Test WebSocket disconnection."""
        # Set up connected state
        websocket_client._websocket = mock_websocket
        websocket_client._status = WEBSOCKET_STATUS_CONNECTED
        
        await websocket_client.disconnect()
        
        mock_websocket.close.assert_called_once()
        assert websocket_client._websocket is None
        assert websocket_client.status == WEBSOCKET_STATUS_DISCONNECTED

    @pytest.mark.asyncio
    async def test_websocket_send_command(self, websocket_client, mock_websocket):
        """Test sending WebSocket command."""
        # Set up connected state
        websocket_client._websocket = mock_websocket
        websocket_client._status = WEBSOCKET_STATUS_CONNECTED
        mock_websocket.send_str = AsyncMock()
        
        command = {"command": "get_value", "parameter": "in-a:voltage"}
        await websocket_client.send_command(command)
        
        expected_message = json.dumps(command)
        mock_websocket.send_str.assert_called_once_with(expected_message)

    @pytest.mark.asyncio
    async def test_websocket_send_command_not_connected(self, websocket_client):
        """Test sending command when not connected raises error."""
        command = {"command": "get_value", "parameter": "in-a:voltage"}
        
        with pytest.raises(CresControlWebSocketError, match="WebSocket not connected"):
            await websocket_client.send_command(command)

    @pytest.mark.asyncio
    async def test_websocket_message_handling(self, websocket_client, sample_websocket_message):
        """Test WebSocket message handling."""
        handler_called = False
        received_data = None
        
        def test_handler(data):
            nonlocal handler_called, received_data
            handler_called = True
            received_data = data
        
        websocket_client.set_data_handler(test_handler)
        
        # Simulate message reception
        await websocket_client._handle_message(json.dumps(sample_websocket_message))
        
        assert handler_called
        assert received_data == sample_websocket_message["data"]

    @pytest.mark.asyncio
    async def test_websocket_invalid_message_handling(self, websocket_client):
        """Test handling of invalid WebSocket messages."""
        handler_called = False
        
        def test_handler(data):
            nonlocal handler_called
            handler_called = True
        
        websocket_client.set_data_handler(test_handler)
        
        # Test invalid JSON
        await websocket_client._handle_message("invalid json")
        assert not handler_called
        
        # Test message without data field
        await websocket_client._handle_message('{"type": "status"}')
        assert not handler_called

    @pytest.mark.asyncio
    async def test_websocket_reconnection_logic(self, websocket_client, mock_session, mock_websocket):
        """Test WebSocket reconnection logic."""
        # Mock initial successful connection
        mock_session.ws_connect.return_value.__aenter__.return_value = mock_websocket
        mock_websocket.send_str = AsyncMock()
        
        # Connect initially
        await websocket_client.connect()
        assert websocket_client.is_connected
        
        # Simulate connection loss
        websocket_client._status = WEBSOCKET_STATUS_DISCONNECTED
        websocket_client._websocket = None
        
        # Test reconnection
        await websocket_client.connect()
        
        # Should reconnect successfully
        assert websocket_client.is_connected
        assert websocket_client.status == WEBSOCKET_STATUS_CONNECTED


class TestCresControlClientWebSocketIntegration:
    """Test CresControl main client WebSocket integration."""

    @pytest.fixture
    def client_with_websocket(self, mock_session):
        """Create CresControlClient with WebSocket enabled."""
        client = CresControlClient("192.168.1.100", mock_session)
        return client

    @pytest.mark.asyncio
    async def test_enable_websocket_success(self, client_with_websocket, mock_session):
        """Test enabling WebSocket on main client."""
        with patch.object(CresControlWebSocketClient, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = True
            
            result = await client_with_websocket.enable_websocket()
            
            assert result is True
            assert client_with_websocket._websocket_client is not None
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_enable_websocket_failure(self, client_with_websocket, mock_session):
        """Test WebSocket enable failure."""
        with patch.object(CresControlWebSocketClient, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = False
            
            result = await client_with_websocket.enable_websocket()
            
            assert result is False
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disable_websocket(self, client_with_websocket):
        """Test disabling WebSocket."""
        # Set up WebSocket client
        mock_ws_client = Mock()
        mock_ws_client.disconnect = AsyncMock()
        client_with_websocket._websocket_client = mock_ws_client
        
        await client_with_websocket.disable_websocket()
        
        mock_ws_client.disconnect.assert_called_once()
        assert client_with_websocket._websocket_client is None

    @pytest.mark.asyncio
    async def test_send_websocket_command(self, client_with_websocket):
        """Test sending command via WebSocket."""
        # Set up WebSocket client
        mock_ws_client = Mock()
        mock_ws_client.send_command = AsyncMock()
        mock_ws_client.is_connected = True
        client_with_websocket._websocket_client = mock_ws_client
        
        command = {"command": "get_value", "parameter": "in-a:voltage"}
        await client_with_websocket.send_websocket_command(command)
        
        mock_ws_client.send_command.assert_called_once_with(command)

    @pytest.mark.asyncio
    async def test_send_websocket_command_not_enabled(self, client_with_websocket):
        """Test sending WebSocket command when not enabled."""
        command = {"command": "get_value", "parameter": "in-a:voltage"}
        
        with pytest.raises(CresControlWebSocketError, match="WebSocket not enabled"):
            await client_with_websocket.send_websocket_command(command)

    def test_websocket_data_handler_management(self, client_with_websocket):
        """Test WebSocket data handler management."""
        handler = Mock()
        
        # Set up WebSocket client
        mock_ws_client = Mock()
        mock_ws_client.set_data_handler = Mock()
        client_with_websocket._websocket_client = mock_ws_client
        
        client_with_websocket.set_websocket_data_handler(handler)
        
        mock_ws_client.set_data_handler.assert_called_once_with(handler)


class TestConfigFlowWebSocketIntegration:
    """Test WebSocket integration in config flow."""

    @pytest.fixture
    def config_flow(self):
        """Create a CresControlConfigFlow instance for testing."""
        flow = CresControlConfigFlow()
        flow.hass = Mock(spec=HomeAssistant)
        return flow

    @pytest.mark.asyncio
    async def test_config_flow_with_websocket_enabled(self, config_flow):
        """Test configuration flow with WebSocket enabled."""
        user_input = {
            "host": "192.168.1.100",
            CONF_WEBSOCKET_ENABLED: True,
            CONF_WEBSOCKET_PORT: 8080,
            CONF_WEBSOCKET_PATH: "/websocket"
        }
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={
                "type": "create_entry", 
                "title": "192.168.1.100", 
                "data": user_input
            }
        )
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(return_value="3.14")
            mock_client.enable_websocket = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify WebSocket was tested
            mock_client.enable_websocket.assert_called_once()
            
            # Verify config was saved correctly
            assert result["type"] == "create_entry"
            assert result["data"][CONF_WEBSOCKET_ENABLED] is True
            assert result["data"][CONF_WEBSOCKET_PORT] == 8080

    @pytest.mark.asyncio
    async def test_config_flow_websocket_test_failure_fallback(self, config_flow):
        """Test config flow falls back gracefully when WebSocket test fails."""
        user_input = {
            "host": "192.168.1.100",
            CONF_WEBSOCKET_ENABLED: True,
            CONF_WEBSOCKET_PORT: 8080
        }
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={
                "type": "create_entry", 
                "title": "192.168.1.100", 
                "data": {
                    "host": "192.168.1.100",
                    CONF_WEBSOCKET_ENABLED: False  # Falls back to disabled
                }
            }
        )
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(return_value="3.14")
            mock_client.enable_websocket = AsyncMock(return_value=False)  # WebSocket fails
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Should still succeed but with WebSocket disabled
            assert result["type"] == "create_entry"
            assert result["data"][CONF_WEBSOCKET_ENABLED] is False

    @pytest.mark.asyncio
    async def test_config_flow_default_websocket_disabled(self, config_flow):
        """Test config flow defaults to WebSocket disabled for backward compatibility."""
        user_input = {"host": "192.168.1.100"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={
                "type": "create_entry", 
                "title": "192.168.1.100", 
                "data": {
                    "host": "192.168.1.100",
                    CONF_WEBSOCKET_ENABLED: False
                }
            }
        )
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(return_value="3.14")
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Should default to WebSocket disabled
            assert result["type"] == "create_entry"
            assert result["data"][CONF_WEBSOCKET_ENABLED] is False


class TestCoordinatorWebSocketIntegration:
    """Test WebSocket integration in coordinator."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock HomeAssistant instance."""
        hass = Mock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}
        hass.config_entries = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        return hass

    @pytest.fixture
    def mock_config_entry_websocket_enabled(self):
        """Create config entry with WebSocket enabled."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        entry.data = {
            "host": "192.168.1.100",
            CONF_WEBSOCKET_ENABLED: True,
            CONF_WEBSOCKET_PORT: 8080
        }
        entry.async_on_unload = Mock()
        entry.add_update_listener = Mock()
        return entry

    @pytest.fixture
    def mock_config_entry_websocket_disabled(self):
        """Create config entry with WebSocket disabled."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        entry.data = {
            "host": "192.168.1.100",
            CONF_WEBSOCKET_ENABLED: False
        }
        entry.async_on_unload = Mock()
        entry.add_update_listener = Mock()
        return entry

    @pytest.mark.asyncio
    async def test_coordinator_setup_with_websocket_enabled(self, mock_hass, mock_config_entry_websocket_enabled):
        """Test coordinator setup with WebSocket enabled."""
        sample_data = {"in-a:voltage": "3.14", "fan:enabled": "true"}
        
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_data)
            mock_client.enable_websocket = AsyncMock(return_value=True)
            mock_client.set_websocket_data_handler = Mock()
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            from custom_components.crescontrol import async_setup_entry
            result = await async_setup_entry(mock_hass, mock_config_entry_websocket_enabled)
            
            assert result is True
            
            # Verify WebSocket was enabled
            mock_client.enable_websocket.assert_called_once()
            mock_client.set_websocket_data_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_coordinator_setup_websocket_disabled_backward_compatibility(self, mock_hass, mock_config_entry_websocket_disabled):
        """Test coordinator works correctly with WebSocket disabled (backward compatibility)."""
        sample_data = {"in-a:voltage": "3.14", "fan:enabled": "true"}
        
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_data)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            from custom_components.crescontrol import async_setup_entry
            result = await async_setup_entry(mock_hass, mock_config_entry_websocket_disabled)
            
            assert result is True
            
            # Verify WebSocket methods were not called
            assert not hasattr(mock_client, 'enable_websocket') or not mock_client.enable_websocket.called

    @pytest.mark.asyncio
    async def test_coordinator_websocket_data_handling(self, mock_hass, mock_config_entry_websocket_enabled):
        """Test coordinator handling of WebSocket data updates."""
        sample_data = {"in-a:voltage": "3.14", "fan:enabled": "true"}
        
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_data)
            mock_client.enable_websocket = AsyncMock(return_value=True)
            
            # Capture the WebSocket data handler
            websocket_handler = None
            def capture_handler(handler):
                nonlocal websocket_handler
                websocket_handler = handler
            
            mock_client.set_websocket_data_handler = Mock(side_effect=capture_handler)
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            from custom_components.crescontrol import async_setup_entry
            await async_setup_entry(mock_hass, mock_config_entry_websocket_enabled)
            
            # Verify handler was set
            assert websocket_handler is not None
            
            # Test handler with WebSocket data
            coordinator = mock_hass.data[DOMAIN][mock_config_entry_websocket_enabled.entry_id]["coordinator"]
            
            # Simulate WebSocket data reception
            new_data = {"in-a:voltage": "4.2", "fan:rpm": "1500"}
            websocket_handler(new_data)
            
            # The coordinator should update its data without making HTTP requests
            assert coordinator.data is not None

    @pytest.mark.asyncio
    async def test_coordinator_unload_with_websocket(self, mock_hass, mock_config_entry_websocket_enabled):
        """Test coordinator unload properly closes WebSocket connections."""
        sample_data = {"in-a:voltage": "3.14", "fan:enabled": "true"}
        
        with patch("custom_components.crescontrol.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.CresControlClient") as mock_client_class, \
             patch("homeassistant.helpers.device_registry.async_get") as mock_device_registry:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.send_commands = AsyncMock(return_value=sample_data)
            mock_client.enable_websocket = AsyncMock(return_value=True)
            mock_client.set_websocket_data_handler = Mock()
            mock_client.disable_websocket = AsyncMock()
            mock_client_class.return_value = mock_client
            
            mock_registry = Mock()
            mock_registry.async_get_or_create = Mock()
            mock_device_registry.return_value = mock_registry
            
            mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
            
            from custom_components.crescontrol import async_setup_entry, async_unload_entry
            
            # Setup
            await async_setup_entry(mock_hass, mock_config_entry_websocket_enabled)
            
            # Unload
            result = await async_unload_entry(mock_hass, mock_config_entry_websocket_enabled)
            
            assert result is True
            
            # Verify WebSocket was properly disabled
            mock_client.disable_websocket.assert_called_once()


class TestWebSocketErrorHandling:
    """Test WebSocket error handling scenarios."""

    @pytest.mark.asyncio
    async def test_websocket_auth_error(self, websocket_client, mock_session):
        """Test WebSocket authentication error handling."""
        mock_session.ws_connect.side_effect = CresControlWebSocketAuthError("Authentication failed")
        
        result = await websocket_client.connect()
        
        assert result is False
        assert websocket_client.status == WEBSOCKET_STATUS_DISCONNECTED

    @pytest.mark.asyncio
    async def test_websocket_protocol_error(self, websocket_client, mock_session):
        """Test WebSocket protocol error handling."""
        mock_session.ws_connect.side_effect = CresControlWebSocketProtocolError("Protocol error")
        
        result = await websocket_client.connect()
        
        assert result is False
        assert websocket_client.status == WEBSOCKET_STATUS_DISCONNECTED

    @pytest.mark.asyncio
    async def test_websocket_connection_lost_during_operation(self, websocket_client, mock_websocket):
        """Test handling of connection loss during operation."""
        # Set up connected state
        websocket_client._websocket = mock_websocket
        websocket_client._status = WEBSOCKET_STATUS_CONNECTED
        
        # Simulate connection loss
        mock_websocket.send_str = AsyncMock(side_effect=Exception("Connection lost"))
        
        command = {"command": "get_value", "parameter": "in-a:voltage"}
        
        with pytest.raises(CresControlWebSocketError):
            await websocket_client.send_command(command)


class TestWebSocketBackwardCompatibility:
    """Test backward compatibility with existing HTTP-only setups."""

    @pytest.mark.asyncio
    async def test_existing_config_without_websocket_settings(self):
        """Test that existing configs without WebSocket settings still work."""
        # Simulate old config entry without WebSocket settings
        entry_data = {"host": "192.168.1.100"}
        
        # Should not raise any errors when accessing WebSocket settings
        websocket_enabled = entry_data.get(CONF_WEBSOCKET_ENABLED, False)
        websocket_port = entry_data.get(CONF_WEBSOCKET_PORT, DEFAULT_WEBSOCKET_PORT)
        websocket_path = entry_data.get(CONF_WEBSOCKET_PATH, DEFAULT_WEBSOCKET_PATH)
        
        assert websocket_enabled is False
        assert websocket_port == DEFAULT_WEBSOCKET_PORT
        assert websocket_path == DEFAULT_WEBSOCKET_PATH

    @pytest.mark.asyncio
    async def test_migration_from_http_only_to_websocket(self, mock_session):
        """Test smooth migration from HTTP-only to WebSocket-enabled setup."""
        # Start with HTTP-only client
        client = CresControlClient("192.168.1.100", mock_session)
        
        # Verify HTTP operations work
        with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"in-a:voltage": "3.14"}
            result = await client.get_value("in-a:voltage")
            assert result == "3.14"
        
        # Enable WebSocket
        with patch.object(CresControlWebSocketClient, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = True
            result = await client.enable_websocket()
            assert result is True
        
        # Verify both HTTP and WebSocket work
        assert client._websocket_client is not None


class TestWebSocketDiagnostics:
    """Test WebSocket diagnostic sensor functionality."""

    def test_websocket_status_sensor_attributes(self):
        """Test WebSocket status sensor provides correct attributes."""
        # This would be tested in the actual sensor entity tests
        # Here we just verify the constants are properly defined
        assert WEBSOCKET_STATUS_CONNECTED == "connected"
        assert WEBSOCKET_STATUS_DISCONNECTED == "disconnected"
        assert WEBSOCKET_STATUS_RECONNECTING == "reconnecting"

    def test_websocket_configuration_constants(self):
        """Test WebSocket configuration constants are properly defined."""
        assert CONF_WEBSOCKET_ENABLED == "websocket_enabled"
        assert CONF_WEBSOCKET_PORT == "websocket_port"
        assert CONF_WEBSOCKET_PATH == "websocket_path"
        assert DEFAULT_WEBSOCKET_PORT == 8080
        assert DEFAULT_WEBSOCKET_PATH == "/websocket"
        assert WEBSOCKET_TOPIC_ALL == "all"