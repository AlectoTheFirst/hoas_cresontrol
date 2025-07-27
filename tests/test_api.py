"""Tests for the CresControl API client."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from aiohttp import ClientError, ServerTimeoutError, ClientResponse
from aiohttp.client import ClientSession

from custom_components.crescontrol.api import (
    CresControlClient,
    CresControlError,
    CresControlNetworkError,
    CresControlDeviceError,
    CresControlValidationError,
)


@pytest.fixture
def mock_session():
    """Create a mock aiohttp ClientSession."""
    return Mock(spec=ClientSession)


@pytest.fixture
def client(mock_session):
    """Create a CresControlClient instance for testing."""
    return CresControlClient("192.168.1.100", mock_session)


class TestCresControlClientInit:
    """Test CresControlClient initialization."""

    def test_init_valid_ip(self, mock_session):
        """Test initialization with valid IP address."""
        client = CresControlClient("192.168.1.100", mock_session, timeout=15)
        assert client._base_url == "http://192.168.1.100"
        assert client._session is mock_session
        assert client._timeout.total == 15

    def test_init_valid_hostname(self, mock_session):
        """Test initialization with valid hostname."""
        client = CresControlClient("crescontrol.local", mock_session)
        assert client._base_url == "http://crescontrol.local"

    def test_init_default_timeout(self, mock_session):
        """Test initialization with default timeout."""
        client = CresControlClient("192.168.1.100", mock_session)
        assert client._timeout.total == 30

    def test_init_invalid_host_empty(self, mock_session):
        """Test initialization with empty host."""
        with pytest.raises(CresControlValidationError, match="Host must be a non-empty string"):
            CresControlClient("", mock_session)

    def test_init_invalid_host_none(self, mock_session):
        """Test initialization with None host."""
        with pytest.raises(CresControlValidationError, match="Host must be a non-empty string"):
            CresControlClient(None, mock_session)

    def test_init_invalid_host_with_scheme(self, mock_session):
        """Test initialization with host containing URL scheme."""
        with pytest.raises(CresControlValidationError, match="Host contains invalid characters"):
            CresControlClient("http://192.168.1.100", mock_session)

    def test_init_invalid_host_with_port(self, mock_session):
        """Test initialization with host containing port."""
        with pytest.raises(CresControlValidationError, match="Host contains invalid characters"):
            CresControlClient("192.168.1.100:80", mock_session)


class TestHostValidation:
    """Test host validation methods."""

    def test_validate_host_valid_ipv4(self, client):
        """Test validation of valid IPv4 addresses."""
        # Should not raise
        client._validate_host("192.168.1.1")
        client._validate_host("10.0.0.1")
        client._validate_host("172.16.0.1")

    def test_validate_host_valid_ipv6(self, client):
        """Test validation of valid IPv6 addresses."""
        # Should not raise
        client._validate_host("::1")
        client._validate_host("2001:db8::1")

    def test_validate_host_valid_hostname(self, client):
        """Test validation of valid hostnames."""
        # Should not raise
        client._validate_host("localhost")
        client._validate_host("crescontrol.local")
        client._validate_host("my-device")

    def test_validate_host_invalid_characters(self, client):
        """Test validation rejects hosts with invalid characters."""
        invalid_hosts = [
            "192.168.1.1/path",
            "host?query=value",
            "host#fragment",
            "user@host",
            "host:port",
        ]
        for host in invalid_hosts:
            with pytest.raises(CresControlValidationError, match="Host contains invalid characters"):
                client._validate_host(host)

    def test_validate_host_too_long(self, client):
        """Test validation rejects overly long hostnames."""
        long_hostname = "a" * 254
        with pytest.raises(CresControlValidationError, match="Hostname too long"):
            client._validate_host(long_hostname)


class TestParameterValidation:
    """Test parameter validation methods."""

    def test_validate_parameter_valid(self, client):
        """Test validation of valid parameter names."""
        valid_params = [
            "in-a:voltage",
            "fan:enabled",
            "out-a:voltage",
            "switch-12v:enabled",
        ]
        for param in valid_params:
            # Should not raise
            client._validate_parameter(param)

    def test_validate_parameter_empty(self, client):
        """Test validation rejects empty parameters."""
        with pytest.raises(CresControlValidationError, match="Parameter must be a non-empty string"):
            client._validate_parameter("")

    def test_validate_parameter_none(self, client):
        """Test validation rejects None parameters."""
        with pytest.raises(CresControlValidationError, match="Parameter must be a non-empty string"):
            client._validate_parameter(None)

    def test_validate_parameter_invalid_characters(self, client):
        """Test validation rejects parameters with invalid characters."""
        invalid_params = [
            "param;injection",
            "param\ninjection",
            "param\rinjection",
            "param\0injection",
        ]
        for param in invalid_params:
            with pytest.raises(CresControlValidationError, match="Parameter contains invalid characters"):
                client._validate_parameter(param)

    def test_validate_parameter_invalid_format(self, client):
        """Test validation rejects parameters with invalid format."""
        invalid_params = [
            "param with spaces",
            "param@invalid",
            "param#invalid",
        ]
        for param in invalid_params:
            with pytest.raises(CresControlValidationError, match="Invalid parameter name format"):
                client._validate_parameter(param)

    def test_validate_parameter_too_long(self, client):
        """Test validation rejects overly long parameter names."""
        long_param = "a" * 101
        with pytest.raises(CresControlValidationError, match="Parameter name too long"):
            client._validate_parameter(long_param)


class TestValueValidation:
    """Test value validation methods."""

    def test_validate_value_boolean(self, client):
        """Test validation and conversion of boolean values."""
        assert client._validate_value(True) == "true"
        assert client._validate_value(False) == "false"

    def test_validate_value_integer(self, client):
        """Test validation and conversion of integer values."""
        assert client._validate_value(42) == "42"
        assert client._validate_value(-10) == "-10"
        assert client._validate_value(0) == "0"

    def test_validate_value_float(self, client):
        """Test validation and conversion of float values."""
        assert client._validate_value(3.14) == "3.14"
        assert client._validate_value(-2.5) == "-2.5"
        assert client._validate_value(0.0) == "0.0"

    def test_validate_value_string(self, client):
        """Test validation and conversion of string values."""
        assert client._validate_value("test") == "test"
        assert client._validate_value("  trimmed  ") == "trimmed"

    def test_validate_value_none(self, client):
        """Test validation rejects None values."""
        with pytest.raises(CresControlValidationError, match="Value cannot be None"):
            client._validate_value(None)

    def test_validate_value_empty_string(self, client):
        """Test validation rejects empty strings."""
        with pytest.raises(CresControlValidationError, match="String value cannot be empty"):
            client._validate_value("")
        with pytest.raises(CresControlValidationError, match="String value cannot be empty"):
            client._validate_value("   ")

    def test_validate_value_invalid_string_characters(self, client):
        """Test validation rejects strings with invalid characters."""
        invalid_strings = [
            "value;injection",
            "value\ninjection",
            "value\rinjection",
            "value\0injection",
        ]
        for value in invalid_strings:
            with pytest.raises(CresControlValidationError, match="String value contains invalid characters"):
                client._validate_value(value)

    def test_validate_value_numeric_bounds(self, client):
        """Test validation rejects out-of-bounds numeric values."""
        with pytest.raises(CresControlValidationError, match="Numeric value out of reasonable bounds"):
            client._validate_value(1e7)  # Too large float
        with pytest.raises(CresControlValidationError, match="Numeric value out of reasonable bounds"):
            client._validate_value(-1e7)  # Too large negative float
        with pytest.raises(CresControlValidationError, match="Numeric value out of reasonable bounds"):
            client._validate_value(1000001)  # Too large int
        with pytest.raises(CresControlValidationError, match="Numeric value out of reasonable bounds"):
            client._validate_value(-1000001)  # Too large negative int

    def test_validate_value_unsupported_type(self, client):
        """Test validation rejects unsupported value types."""
        with pytest.raises(CresControlValidationError, match="Unsupported value type"):
            client._validate_value([1, 2, 3])
        with pytest.raises(CresControlValidationError, match="Unsupported value type"):
            client._validate_value({"key": "value"})


class TestResponseParsing:
    """Test response parsing methods."""

    def test_parse_response_single_value(self, client):
        """Test parsing response with single value."""
        response = "in-a:voltage::3.14"
        result = client._parse_response_safely(response)
        assert result == {"in-a:voltage": "3.14"}

    def test_parse_response_multiple_values(self, client):
        """Test parsing response with multiple values."""
        response = "in-a:voltage::3.14;fan:enabled::true"
        result = client._parse_response_safely(response)
        assert result == {"in-a:voltage": "3.14", "fan:enabled": "true"}

    def test_parse_response_with_assignment(self, client):
        """Test parsing response with assignment echoed back."""
        response = "out-a:voltage=5.0::5.0"
        result = client._parse_response_safely(response)
        assert result == {"out-a:voltage": "5.0"}

    def test_parse_response_multiline(self, client):
        """Test parsing response with multiple lines."""
        response = "in-a:voltage::3.14\nfan:enabled::true"
        result = client._parse_response_safely(response)
        assert result == {"in-a:voltage": "3.14", "fan:enabled": "true"}

    def test_parse_response_invalid_format(self, client):
        """Test parsing response with invalid format."""
        response = "invalid_response_without_delimiter"
        result = client._parse_response_safely(response)
        assert result == {"invalid_response_without_delimiter": None}

    def test_parse_response_empty(self, client):
        """Test parsing empty response."""
        result = client._parse_response_safely("")
        assert result == {}

    def test_parse_response_not_string(self, client):
        """Test parsing non-string response raises error."""
        with pytest.raises(CresControlDeviceError, match="Response is not a string"):
            client._parse_response_safely(123)

    def test_parse_response_too_large(self, client):
        """Test parsing overly large response raises error."""
        large_response = "a" * 10001
        with pytest.raises(CresControlDeviceError, match="Response too large"):
            client._parse_response_safely(large_response)


class TestSendCommands:
    """Test send_commands method."""

    @pytest.mark.asyncio
    async def test_send_commands_single_string(self, client, mock_session):
        """Test sending a single command as string."""
        mock_response = AsyncMock()
        mock_response.text.return_value = "in-a:voltage::3.14"
        mock_response.raise_for_status.return_value = None
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        result = await client.send_commands("in-a:voltage")
        
        assert result == {"in-a:voltage": "3.14"}
        mock_session.get.assert_called_once_with(
            "http://192.168.1.100/command",
            params={"query": "in-a:voltage"},
            timeout=client._timeout
        )

    @pytest.mark.asyncio
    async def test_send_commands_list(self, client, mock_session):
        """Test sending multiple commands as list."""
        mock_response = AsyncMock()
        mock_response.text.return_value = "in-a:voltage::3.14;fan:enabled::true"
        mock_response.raise_for_status.return_value = None
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        commands = ["in-a:voltage", "fan:enabled"]
        result = await client.send_commands(commands)
        
        assert result == {"in-a:voltage": "3.14", "fan:enabled": "true"}
        mock_session.get.assert_called_once_with(
            "http://192.168.1.100/command",
            params={"query": "in-a:voltage;fan:enabled"},
            timeout=client._timeout
        )

    @pytest.mark.asyncio
    async def test_send_commands_with_assignment(self, client, mock_session):
        """Test sending command with value assignment."""
        mock_response = AsyncMock()
        mock_response.text.return_value = "out-a:voltage=5.0::5.0"
        mock_response.raise_for_status.return_value = None
        
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        result = await client.send_commands("out-a:voltage=5.0")
        
        assert result == {"out-a:voltage": "5.0"}

    @pytest.mark.asyncio
    async def test_send_commands_invalid_command_in_list(self, client):
        """Test sending commands with invalid command in list."""
        commands = ["valid:param", 123]  # Non-string command
        with pytest.raises(CresControlValidationError, match="All commands must be strings"):
            await client.send_commands(commands)

    @pytest.mark.asyncio
    async def test_send_commands_query_too_long(self, client):
        """Test sending commands with overly long query."""
        long_command = "a" * 2001
        with pytest.raises(CresControlValidationError, match="Command query too long"):
            await client.send_commands(long_command)

    @pytest.mark.asyncio
    async def test_send_commands_network_timeout(self, client, mock_session):
        """Test network timeout handling."""
        mock_session.get.side_effect = ServerTimeoutError("Timeout")
        
        with pytest.raises(CresControlNetworkError, match="Request timeout"):
            await client.send_commands("in-a:voltage")

    @pytest.mark.asyncio
    async def test_send_commands_network_error(self, client, mock_session):
        """Test network error handling."""
        mock_session.get.side_effect = ClientError("Network error")
        
        with pytest.raises(CresControlNetworkError, match="Network error"):
            await client.send_commands("in-a:voltage")

    @pytest.mark.asyncio
    async def test_send_commands_unexpected_error(self, client, mock_session):
        """Test unexpected error handling."""
        mock_session.get.side_effect = ValueError("Unexpected error")
        
        with pytest.raises(CresControlDeviceError, match="Device error"):
            await client.send_commands("in-a:voltage")


class TestGetValue:
    """Test get_value method."""

    @pytest.mark.asyncio
    async def test_get_value_success(self, client):
        """Test successful value retrieval."""
        with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"in-a:voltage": "3.14"}
            
            result = await client.get_value("in-a:voltage")
            
            assert result == "3.14"
            mock_send.assert_called_once_with(["in-a:voltage"])

    @pytest.mark.asyncio
    async def test_get_value_not_found(self, client):
        """Test value retrieval when parameter not in response."""
        with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {}
            
            result = await client.get_value("missing:param")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_get_value_invalid_parameter(self, client):
        """Test value retrieval with invalid parameter."""
        with pytest.raises(CresControlValidationError):
            await client.get_value("invalid;param")


class TestSetValue:
    """Test set_value method."""

    @pytest.mark.asyncio
    async def test_set_value_success(self, client):
        """Test successful value setting."""
        with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"out-a:voltage": "5.0"}
            
            result = await client.set_value("out-a:voltage", 5.0)
            
            assert result == "5.0"
            mock_send.assert_called_once_with(["out-a:voltage=5.0"])

    @pytest.mark.asyncio
    async def test_set_value_boolean(self, client):
        """Test setting boolean value."""
        with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"fan:enabled": "true"}
            
            result = await client.set_value("fan:enabled", True)
            
            assert result == "true"
            mock_send.assert_called_once_with(["fan:enabled=true"])

    @pytest.mark.asyncio
    async def test_set_value_invalid_parameter(self, client):
        """Test setting value with invalid parameter."""
        with pytest.raises(CresControlValidationError):
            await client.set_value("invalid;param", "value")

    @pytest.mark.asyncio
    async def test_set_value_invalid_value(self, client):
        """Test setting invalid value."""
        with pytest.raises(CresControlValidationError):
            await client.set_value("out-a:voltage", None)


class TestUrlValidation:
    """Test URL validation methods."""

    def test_validate_url_valid(self, client):
        """Test validation of valid URLs."""
        valid_url = "http://192.168.1.100/command"
        # Should not raise
        client._validate_url(valid_url)

    def test_validate_url_invalid_base(self, client):
        """Test validation rejects URLs with wrong base."""
        invalid_url = "http://malicious.com/command"
        with pytest.raises(CresControlValidationError, match="URL does not match expected base URL"):
            client._validate_url(invalid_url)

    def test_validate_url_path_traversal(self, client):
        """Test validation rejects path traversal attempts."""
        invalid_urls = [
            "http://192.168.1.100/../etc/passwd",
            "http://192.168.1.100//command",
        ]
        for url in invalid_urls:
            with pytest.raises(CresControlValidationError, match="URL contains path traversal attempts"):
                client._validate_url(url)


class TestPWMSpecificMethods:
   """Test PWM-specific API methods."""

   @pytest.mark.asyncio
   async def test_get_all_pwm_data_success(self, client):
       """Test successful PWM data retrieval."""
       with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
           mock_send.return_value = {
               "out-a:pwm-enabled": "true",
               "out-a:duty-cycle": "50.0",
               "out-a:pwm-frequency": "100.0",
               "out-b:pwm-enabled": "false",
               "out-b:duty-cycle": "0.0",
               "out-b:pwm-frequency": "0.0",
               "switch-12v:pwm-enabled": "true",
               "switch-12v:duty-cycle": "75.0",
               "switch-12v:pwm-frequency": "200.0",
           }
           
           result = await client.get_all_pwm_data()
           
           # Verify parsed values
           assert result["out-a:pwm-enabled"] is True
           assert result["out-a:duty-cycle"] == 50.0
           assert result["out-a:pwm-frequency"] == 100.0
           assert result["out-b:pwm-enabled"] is False
           assert result["switch-12v:pwm-enabled"] is True
           assert result["switch-12v:duty-cycle"] == 75.0

   @pytest.mark.asyncio
   async def test_set_pwm_enabled_success(self, client):
       """Test successful PWM enable/disable."""
       with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
           mock_send.return_value = {"out-a:pwm-enabled": "true"}
           
           result = await client.set_pwm_enabled("out-a:pwm-enabled", True)
           
           assert result is True
           mock_send.assert_called_once()
           commands = mock_send.call_args[0][0]
           assert "out-a:pwm-enabled=true" in commands

   @pytest.mark.asyncio
   async def test_set_pwm_enabled_with_output_disable(self, client):
       """Test PWM enable for output also disables normal output."""
       with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
           mock_send.return_value = {"out-a:pwm-enabled": "true"}
           
           await client.set_pwm_enabled("out-a:pwm-enabled", True)
           
           commands = mock_send.call_args[0][0]
           assert "out-a:pwm-enabled=true" in commands
           assert "out-a:enabled=false" in commands

   @pytest.mark.asyncio
   async def test_set_pwm_duty_cycle_success(self, client):
       """Test successful PWM duty cycle setting."""
       with patch.object(client, 'set_value', new_callable=AsyncMock) as mock_set:
           mock_set.return_value = "75.0"
           
           result = await client.set_pwm_duty_cycle("out-a:duty-cycle", 75.0)
           
           assert result == 75.0
           mock_set.assert_called_once_with("out-a:duty-cycle", 75.0)

   @pytest.mark.asyncio
   async def test_set_pwm_frequency_success(self, client):
       """Test successful PWM frequency setting."""
       with patch.object(client, 'set_value', new_callable=AsyncMock) as mock_set:
           mock_set.return_value = "100.0"
           
           result = await client.set_pwm_frequency("out-a:pwm-frequency", 100.0)
           
           assert result == 100.0
           mock_set.assert_called_once_with("out-a:pwm-frequency", 100.0)

   @pytest.mark.asyncio
   async def test_batch_set_pwm_parameters_success(self, client):
       """Test successful batch PWM parameter setting."""
       with patch.object(client, 'send_commands', new_callable=AsyncMock) as mock_send:
           mock_send.return_value = {
               "out-a:pwm-enabled": "true",
               "out-a:duty-cycle": "50.0",
               "out-a:pwm-frequency": "100.0",
           }
           
           pwm_settings = {
               "out-a:pwm-enabled": True,
               "out-a:duty-cycle": 50.0,
               "out-a:pwm-frequency": 100.0,
           }
           
           result = await client.batch_set_pwm_parameters(pwm_settings)
           
           assert result["out-a:pwm-enabled"] == "true"
           assert result["out-a:duty-cycle"] == "50.0"
           assert result["out-a:pwm-frequency"] == "100.0"

   @pytest.mark.asyncio
   async def test_batch_set_pwm_parameters_empty(self, client):
       """Test batch PWM with empty settings."""
       with pytest.raises(CresControlValidationError, match="No PWM settings provided"):
           await client.batch_set_pwm_parameters({})

   @pytest.mark.asyncio
   async def test_batch_set_pwm_parameters_too_many(self, client):
       """Test batch PWM with too many operations."""
       # Create more than the maximum allowed operations
       pwm_settings = {f"out-{chr(97+i)}:pwm-enabled": True for i in range(11)}
       
       with pytest.raises(CresControlValidationError, match="Too many PWM operations"):
           await client.batch_set_pwm_parameters(pwm_settings)


class TestPWMValidation:
   """Test PWM parameter validation methods."""

   def test_validate_pwm_enabled_parameter_valid_output(self, client):
       """Test validation of valid PWM enabled parameters for outputs."""
       valid_params = [
           "out-a:pwm-enabled",
           "out-b:pwm-enabled",
       ]
       for param in valid_params:
           # Should not raise
           client._validate_pwm_enabled_parameter(param)

   def test_validate_pwm_enabled_parameter_valid_switch(self, client):
       """Test validation of valid PWM enabled parameters for switches."""
       valid_params = [
           "switch-12v:pwm-enabled",
           "switch-24v-a:pwm-enabled",
           "switch-24v-b:pwm-enabled",
       ]
       for param in valid_params:
           # Should not raise
           client._validate_pwm_enabled_parameter(param)

   def test_validate_pwm_enabled_parameter_invalid_format(self, client):
       """Test validation rejects invalid PWM enabled parameter format."""
       with pytest.raises(CresControlValidationError, match="Invalid PWM enabled parameter format"):
           client._validate_pwm_enabled_parameter("out-a:enabled")

   def test_validate_pwm_enabled_parameter_unsupported_output(self, client):
       """Test validation rejects PWM for unsupported outputs."""
       with pytest.raises(CresControlValidationError, match="Output does not support PWM control"):
           client._validate_pwm_enabled_parameter("out-c:pwm-enabled")

   def test_validate_pwm_duty_cycle_parameter_valid(self, client):
       """Test validation of valid PWM duty cycle parameters."""
       valid_params = [
           "out-a:duty-cycle",
           "out-b:duty-cycle",
           "switch-12v:duty-cycle",
           "switch-24v-a:duty-cycle",
           "switch-24v-b:duty-cycle",
       ]
       for param in valid_params:
           # Should not raise
           client._validate_pwm_duty_cycle_parameter(param)

   def test_validate_pwm_duty_cycle_parameter_invalid_format(self, client):
       """Test validation rejects invalid PWM duty cycle parameter format."""
       with pytest.raises(CresControlValidationError, match="Invalid PWM duty cycle parameter format"):
           client._validate_pwm_duty_cycle_parameter("out-a:voltage")

   def test_validate_pwm_frequency_parameter_valid(self, client):
       """Test validation of valid PWM frequency parameters."""
       valid_params = [
           "out-a:pwm-frequency",
           "out-b:pwm-frequency",
           "switch-12v:pwm-frequency",
           "switch-24v-a:pwm-frequency",
           "switch-24v-b:pwm-frequency",
       ]
       for param in valid_params:
           # Should not raise
           client._validate_pwm_frequency_parameter(param)

   def test_validate_pwm_frequency_parameter_invalid_format(self, client):
       """Test validation rejects invalid PWM frequency parameter format."""
       with pytest.raises(CresControlValidationError, match="Invalid PWM frequency parameter format"):
           client._validate_pwm_frequency_parameter("out-a:voltage")

   def test_validate_pwm_duty_cycle_value_valid(self, client):
       """Test validation of valid PWM duty cycle values."""
       valid_values = [0.0, 25.5, 50.0, 75.0, 100.0]
       for value in valid_values:
           # Should not raise
           client._validate_pwm_duty_cycle_value(value)

   def test_validate_pwm_duty_cycle_value_invalid_range(self, client):
       """Test validation rejects PWM duty cycle values outside valid range."""
       invalid_values = [-1.0, -10.0, 101.0, 150.0]
       for value in invalid_values:
           with pytest.raises(CresControlValidationError, match="PWM duty cycle must be between 0 and 100 percent"):
               client._validate_pwm_duty_cycle_value(value)

   def test_validate_pwm_duty_cycle_value_invalid_type(self, client):
       """Test validation rejects non-numeric PWM duty cycle values."""
       with pytest.raises(CresControlValidationError, match="PWM duty cycle must be a number"):
           client._validate_pwm_duty_cycle_value("invalid")

   def test_validate_pwm_frequency_value_valid(self, client):
       """Test validation of valid PWM frequency values."""
       valid_values = [0.0, 50.0, 100.0, 500.0, 1000.0]
       for value in valid_values:
           # Should not raise
           client._validate_pwm_frequency_value(value)

   def test_validate_pwm_frequency_value_invalid_range(self, client):
       """Test validation rejects PWM frequency values outside valid range."""
       invalid_values = [-1.0, -10.0, 1001.0, 2000.0]
       for value in invalid_values:
           with pytest.raises(CresControlValidationError, match="PWM frequency must be between 0 and 1000 Hz"):
               client._validate_pwm_frequency_value(value)

   def test_validate_pwm_frequency_value_invalid_type(self, client):
       """Test validation rejects non-numeric PWM frequency values."""
       with pytest.raises(CresControlValidationError, match="PWM frequency must be a number"):
           client._validate_pwm_frequency_value("invalid")