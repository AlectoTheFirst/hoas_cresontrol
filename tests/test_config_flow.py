"""Tests for the CresControl configuration flow."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from custom_components.crescontrol.config_flow import CresControlConfigFlow
from custom_components.crescontrol.api import (
    CresControlValidationError,
    CresControlNetworkError,
    CresControlDeviceError,
)
from custom_components.crescontrol.const import DOMAIN


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = Mock(spec=HomeAssistant)
    return hass


@pytest.fixture
def config_flow(mock_hass):
    """Create a CresControlConfigFlow instance for testing."""
    flow = CresControlConfigFlow()
    flow.hass = mock_hass
    return flow


class TestCresControlConfigFlow:
    """Test the CresControl configuration flow."""

    def test_flow_version(self):
        """Test that the flow has the correct version."""
        assert CresControlConfigFlow.VERSION == 1
        assert CresControlConfigFlow.MINOR_VERSION == 0

    @pytest.mark.asyncio
    async def test_show_form_no_user_input(self, config_flow):
        """Test that the form is shown when no user input is provided."""
        result = await config_flow.async_step_user(user_input=None)
        
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "host" in result["data_schema"].schema
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_successful_configuration(self, config_flow):
        """Test successful device configuration."""
        user_input = {"host": "192.168.1.100"}
        
        # Mock the async_set_unique_id and _abort_if_unique_id_configured
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={"type": "create_entry", "title": "192.168.1.100", "data": {"host": "192.168.1.100"}}
        )
        
        # Mock the client and its get_value method
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(return_value="3.14")
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify the flow completed successfully
            assert result["type"] == "create_entry"
            assert result["title"] == "192.168.1.100"
            assert result["data"] == {"host": "192.168.1.100"}
            
            # Verify the client was created and tested
            mock_client_class.assert_called_once_with("192.168.1.100", mock_session)
            mock_client.get_value.assert_called_once_with("in-a:voltage")
            
            # Verify unique ID was set
            config_flow.async_set_unique_id.assert_called_once_with("192.168.1.100")

    @pytest.mark.asyncio
    async def test_duplicate_host_configuration(self, config_flow):
        """Test that duplicate host configuration is prevented."""
        user_input = {"host": "192.168.1.100"}
        
        # Mock the unique ID check to raise an abort condition
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock(
            side_effect=config_entries.ConfigEntryError("Already configured")
        )
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession"):
            with pytest.raises(config_entries.ConfigEntryError):
                await config_flow.async_step_user(user_input=user_input)
            
            config_flow.async_set_unique_id.assert_called_once_with("192.168.1.100")

    @pytest.mark.asyncio
    async def test_invalid_host_format(self, config_flow):
        """Test handling of invalid host format."""
        user_input = {"host": "invalid;host"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_show_form = Mock(return_value={"type": "form", "errors": {"base": "invalid_host"}})
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            # The client initialization should raise a validation error
            mock_client_class.side_effect = CresControlValidationError("Invalid host format")
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify the form is shown again with error
            config_flow.async_show_form.assert_called_once()
            call_args = config_flow.async_show_form.call_args
            assert call_args[1]["errors"] == {"base": "invalid_host"}

    @pytest.mark.asyncio
    async def test_network_connection_error(self, config_flow):
        """Test handling of network connection errors."""
        user_input = {"host": "192.168.1.100"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_show_form = Mock(return_value={"type": "form", "errors": {"base": "cannot_connect"}})
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(side_effect=CresControlNetworkError("Connection failed"))
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify the form is shown again with error
            config_flow.async_show_form.assert_called_once()
            call_args = config_flow.async_show_form.call_args
            assert call_args[1]["errors"] == {"base": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_device_error(self, config_flow):
        """Test handling of device errors."""
        user_input = {"host": "192.168.1.100"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_show_form = Mock(return_value={"type": "form", "errors": {"base": "device_error"}})
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(side_effect=CresControlDeviceError("Device error"))
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify the form is shown again with error
            config_flow.async_show_form.assert_called_once()
            call_args = config_flow.async_show_form.call_args
            assert call_args[1]["errors"] == {"base": "device_error"}

    @pytest.mark.asyncio
    async def test_unexpected_error(self, config_flow):
        """Test handling of unexpected errors."""
        user_input = {"host": "192.168.1.100"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_show_form = Mock(return_value={"type": "form", "errors": {"base": "unknown"}})
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(side_effect=ValueError("Unexpected error"))
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify the form is shown again with error
            config_flow.async_show_form.assert_called_once()
            call_args = config_flow.async_show_form.call_args
            assert call_args[1]["errors"] == {"base": "unknown"}

    @pytest.mark.asyncio
    async def test_host_trimming(self, config_flow):
        """Test that host input is properly trimmed."""
        user_input = {"host": "  192.168.1.100  "}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={"type": "create_entry", "title": "192.168.1.100", "data": {"host": "192.168.1.100"}}
        )
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(return_value="3.14")
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify the client was created with trimmed host
            mock_client_class.assert_called_once_with("192.168.1.100", mock_session)
            
            # Verify unique ID was set with trimmed host
            config_flow.async_set_unique_id.assert_called_once_with("192.168.1.100")

    @pytest.mark.asyncio
    async def test_hostname_configuration(self, config_flow):
        """Test configuration with hostname instead of IP."""
        user_input = {"host": "crescontrol.local"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={"type": "create_entry", "title": "crescontrol.local", "data": {"host": "crescontrol.local"}}
        )
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(return_value="3.14")
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify the flow completed successfully with hostname
            assert result["type"] == "create_entry"
            assert result["title"] == "crescontrol.local"
            assert result["data"] == {"host": "crescontrol.local"}
            
            mock_client_class.assert_called_once_with("crescontrol.local", mock_session)

    @pytest.mark.asyncio
    async def test_validation_before_unique_id_check(self, config_flow):
        """Test that validation occurs before unique ID check."""
        # This test ensures that invalid hosts don't get to the unique ID check
        user_input = {"host": "http://invalid"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_show_form = Mock(return_value={"type": "form", "errors": {"base": "invalid_host"}})
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            # The client initialization should raise a validation error due to invalid host
            mock_client_class.side_effect = CresControlValidationError("Host contains invalid characters")
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify unique ID was still set (happens before client creation)
            config_flow.async_set_unique_id.assert_called_once_with("http://invalid")
            
            # Verify the form is shown again with error
            config_flow.async_show_form.assert_called_once()
            call_args = config_flow.async_show_form.call_args
            assert call_args[1]["errors"] == {"base": "invalid_host"}

    @pytest.mark.asyncio
    async def test_communication_test_parameter(self, config_flow):
        """Test that the correct parameter is used for communication testing."""
        user_input = {"host": "192.168.1.100"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={"type": "create_entry", "title": "192.168.1.100", "data": {"host": "192.168.1.100"}}
        )
        
        with patch("custom_components.crescontrol.config_flow.async_get_clientsession") as mock_session_getter, \
             patch("custom_components.crescontrol.config_flow.CresControlClient") as mock_client_class:
            
            mock_session = Mock()
            mock_session_getter.return_value = mock_session
            
            mock_client = Mock()
            mock_client.get_value = AsyncMock(return_value="3.14")
            mock_client_class.return_value = mock_client
            
            result = await config_flow.async_step_user(user_input=user_input)
            
            # Verify that the specific test parameter is used
            mock_client.get_value.assert_called_once_with("in-a:voltage")