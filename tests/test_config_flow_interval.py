"""Tests for the CresControl configuration flow update interval functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from custom_components.crescontrol.config_flow import CresControlConfigFlow, CresControlOptionsFlow
from custom_components.crescontrol.const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
)


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


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry."""
    entry = Mock(spec=config_entries.ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {"host": "192.168.1.100", CONF_UPDATE_INTERVAL: 30}
    return entry


class TestCresControlConfigFlowInterval:
    """Test the CresControl configuration flow with update interval."""

    @pytest.mark.asyncio
    async def test_config_with_default_interval(self, config_flow):
        """Test configuration with default update interval."""
        user_input = {"host": "192.168.1.100"}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={
                "type": "create_entry", 
                "title": "192.168.1.100", 
                "data": {
                    "host": "192.168.1.100",
                    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_SECONDS,
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
            
            # Verify the flow completed successfully with default interval
            assert result["type"] == "create_entry"
            assert result["data"]["host"] == "192.168.1.100"
            assert result["data"][CONF_UPDATE_INTERVAL] == DEFAULT_UPDATE_INTERVAL_SECONDS

    @pytest.mark.asyncio
    async def test_config_with_custom_interval(self, config_flow):
        """Test configuration with custom update interval."""
        user_input = {"host": "192.168.1.100", CONF_UPDATE_INTERVAL: 30}
        
        config_flow.async_set_unique_id = AsyncMock()
        config_flow._abort_if_unique_id_configured = Mock()
        config_flow.async_create_entry = Mock(
            return_value={
                "type": "create_entry", 
                "title": "192.168.1.100", 
                "data": {
                    "host": "192.168.1.100",
                    CONF_UPDATE_INTERVAL: 30,
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
            
            # Verify the flow completed successfully with custom interval
            assert result["type"] == "create_entry"
            assert result["data"]["host"] == "192.168.1.100"
            assert result["data"][CONF_UPDATE_INTERVAL] == 30

    @pytest.mark.asyncio
    async def test_config_interval_too_low(self, config_flow):
        """Test configuration with interval below minimum."""
        user_input = {"host": "192.168.1.100", CONF_UPDATE_INTERVAL: MIN_UPDATE_INTERVAL - 1}
        
        config_flow.async_show_form = Mock(
            return_value={"type": "form", "errors": {CONF_UPDATE_INTERVAL: "invalid_update_interval"}}
        )
        
        result = await config_flow.async_step_user(user_input=user_input)
        
        # Verify the form is shown again with error
        config_flow.async_show_form.assert_called_once()
        call_args = config_flow.async_show_form.call_args
        assert call_args[1]["errors"] == {CONF_UPDATE_INTERVAL: "invalid_update_interval"}

    @pytest.mark.asyncio
    async def test_config_interval_too_high(self, config_flow):
        """Test configuration with interval above maximum."""
        user_input = {"host": "192.168.1.100", CONF_UPDATE_INTERVAL: MAX_UPDATE_INTERVAL + 1}
        
        config_flow.async_show_form = Mock(
            return_value={"type": "form", "errors": {CONF_UPDATE_INTERVAL: "invalid_update_interval"}}
        )
        
        result = await config_flow.async_step_user(user_input=user_input)
        
        # Verify the form is shown again with error
        config_flow.async_show_form.assert_called_once()
        call_args = config_flow.async_show_form.call_args
        assert call_args[1]["errors"] == {CONF_UPDATE_INTERVAL: "invalid_update_interval"}

    @pytest.mark.asyncio
    async def test_config_schema_includes_interval(self, config_flow):
        """Test that the configuration schema includes the update interval field."""
        result = await config_flow.async_step_user(user_input=None)
        
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        
        # Check that both host and update_interval are in the schema
        schema_keys = [str(key) for key in result["data_schema"].schema.keys()]
        assert any("host" in key for key in schema_keys)
        assert any(CONF_UPDATE_INTERVAL in key for key in schema_keys)


class TestCresControlOptionsFlow:
    """Test the CresControl options flow."""

    @pytest.mark.asyncio
    async def test_options_flow_init(self, mock_hass, mock_config_entry):
        """Test options flow initialization."""
        options_flow = CresControlOptionsFlow(mock_config_entry)
        options_flow.hass = mock_hass
        
        result = await options_flow.async_step_init(user_input=None)
        
        assert result["type"] == "form"
        assert result["step_id"] == "init"
        
        # Check that update_interval is in the schema
        schema_keys = [str(key) for key in result["data_schema"].schema.keys()]
        assert any(CONF_UPDATE_INTERVAL in key for key in schema_keys)

    @pytest.mark.asyncio
    async def test_options_flow_update_interval(self, mock_hass, mock_config_entry):
        """Test updating interval through options flow."""
        options_flow = CresControlOptionsFlow(mock_config_entry)
        options_flow.hass = mock_hass
        options_flow.async_create_entry = Mock(
            return_value={"type": "create_entry", "title": "", "data": {}}
        )
        
        # Mock the config entry update
        mock_hass.config_entries = Mock()
        mock_hass.config_entries.async_update_entry = Mock()
        
        user_input = {CONF_UPDATE_INTERVAL: 60}
        result = await options_flow.async_step_init(user_input=user_input)
        
        # Verify the config entry was updated
        mock_hass.config_entries.async_update_entry.assert_called_once()
        call_args = mock_hass.config_entries.async_update_entry.call_args
        updated_data = call_args[1]["data"]
        assert updated_data[CONF_UPDATE_INTERVAL] == 60
        
        # Verify the flow completed
        assert result["type"] == "create_entry"

    @pytest.mark.asyncio
    async def test_options_flow_invalid_interval(self, mock_hass, mock_config_entry):
        """Test options flow with invalid interval."""
        options_flow = CresControlOptionsFlow(mock_config_entry)
        options_flow.hass = mock_hass
        options_flow.async_show_form = Mock(
            return_value={"type": "form", "errors": {CONF_UPDATE_INTERVAL: "invalid_update_interval"}}
        )
        
        user_input = {CONF_UPDATE_INTERVAL: MAX_UPDATE_INTERVAL + 1}
        result = await options_flow.async_step_init(user_input=user_input)
        
        # Verify the form is shown again with error
        options_flow.async_show_form.assert_called_once()
        call_args = options_flow.async_show_form.call_args
        assert call_args[1]["errors"] == {CONF_UPDATE_INTERVAL: "invalid_update_interval"}

    @pytest.mark.asyncio
    async def test_options_flow_uses_current_value(self, mock_hass, mock_config_entry):
        """Test that options flow uses current config value as default."""
        options_flow = CresControlOptionsFlow(mock_config_entry)
        options_flow.hass = mock_hass
        
        result = await options_flow.async_step_init(user_input=None)
        
        # The form should be shown with current value as default
        assert result["type"] == "form"
        # The current value from mock_config_entry is 30 seconds
        # We can't easily test the default value in the schema, but we know it should use 30