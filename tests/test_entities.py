"""Tests for CresControl entity platforms (sensor, switch, number)."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, REVOLUTIONS_PER_MINUTE

from custom_components.crescontrol.sensor import (
    async_setup_entry as sensor_async_setup_entry,
    CresControlSensor,
    SENSOR_DEFINITIONS,
)
from custom_components.crescontrol.switch import (
    async_setup_entry as switch_async_setup_entry,
    CresControlSwitch,
    SWITCH_DEFINITIONS,
)
from custom_components.crescontrol.number import (
    async_setup_entry as number_async_setup_entry,
    CresControlNumber,
    NUMBER_DEFINITIONS,
)
from custom_components.crescontrol.fan import (
    async_setup_entry as fan_async_setup_entry,
    CresControlFan,
)
from custom_components.crescontrol.const import DOMAIN


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    return Mock(spec=HomeAssistant)


@pytest.fixture
def mock_config_entry():
    """Create a mock ConfigEntry."""
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {"host": "192.168.1.100"}
    return entry


@pytest.fixture
def mock_coordinator():
    """Create a mock DataUpdateCoordinator."""
    coordinator = Mock()
    coordinator.config_entry = Mock()
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.data = {
        "in-a:voltage": "3.14",
        "in-b:voltage": "2.71",
        "fan:enabled": "1",
        "fan:duty-cycle": "75.0",
        "fan:duty-cycle-min": "20.0",
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
    }
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_client():
    """Create a mock CresControlClient."""
    client = Mock()
    client.set_value = AsyncMock()
    # Add fan-specific methods
    client.get_all_fan_data = AsyncMock(return_value={
        "enabled": True,
        "duty_cycle": 75.0,
        "duty_cycle_min": 20.0,
        "rpm": 1200,
    })
    client.set_fan_speed = AsyncMock(return_value={
        "enabled": True,
        "duty_cycle": 50.0,
        "duty_cycle_min": 20.0,
        "rpm": 800,
    })
    client.set_fan_enabled = AsyncMock(return_value=True)
    client.get_fan_duty_cycle_min = AsyncMock(return_value=20.0)
    client.set_fan_duty_cycle_min = AsyncMock(return_value=25.0)
    return client


@pytest.fixture
def device_info():
    """Create sample device info."""
    return {
        "identifiers": {(DOMAIN, "192.168.1.100")},
        "name": "CresControl (192.168.1.100)",
        "manufacturer": "Crescience",
        "model": "CresControl Cannabis Grow Controller",
        "configuration_url": "http://192.168.1.100",
    }


class TestSensorEntities:
    """Test sensor entity functionality."""

    @pytest.mark.asyncio
    async def test_sensor_setup_entry(self, mock_hass, mock_config_entry, mock_coordinator, device_info):
        """Test sensor platform setup."""
        mock_hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "device_info": device_info,
                }
            }
        }
        
        mock_add_entities = Mock()
        
        await sensor_async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)
        
        # Verify entities were added
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        
        # Should create one entity per sensor definition
        assert len(entities) == len(SENSOR_DEFINITIONS)
        
        for entity in entities:
            assert isinstance(entity, CresControlSensor)

    def test_sensor_definitions_structure(self):
        """Test that sensor definitions have required fields."""
        for definition in SENSOR_DEFINITIONS:
            assert "key" in definition
            assert "name" in definition
            assert "unit" in definition
            assert "device_class" in definition
            assert "state_class" in definition

    def test_sensor_entity_initialization(self, mock_coordinator, device_info):
        """Test sensor entity initialization."""
        definition = SENSOR_DEFINITIONS[0]  # in-a:voltage
        sensor = CresControlSensor(mock_coordinator, device_info, definition)
        
        assert sensor._key == "in-a:voltage"
        assert sensor._attr_name == "CresControl In A Voltage"
        assert sensor._attr_unique_id == "test_entry_id_in-a:voltage"
        assert sensor._attr_native_unit_of_measurement == UnitOfElectricPotential.VOLT
        assert sensor._device_info == device_info

    def test_sensor_device_info_property(self, mock_coordinator, device_info):
        """Test sensor device_info property."""
        definition = SENSOR_DEFINITIONS[0]
        sensor = CresControlSensor(mock_coordinator, device_info, definition)
        
        assert sensor.device_info == device_info

    def test_sensor_native_value_float(self, mock_coordinator, device_info):
        """Test sensor native_value with float data."""
        definition = SENSOR_DEFINITIONS[0]  # in-a:voltage
        sensor = CresControlSensor(mock_coordinator, device_info, definition)
        
        # Value contains decimal point, should be parsed as float
        assert sensor.native_value == 3.14
        assert isinstance(sensor.native_value, float)

    def test_sensor_native_value_int(self, mock_coordinator, device_info):
        """Test sensor native_value with integer data."""
        definition = SENSOR_DEFINITIONS[2]  # fan:rpm
        sensor = CresControlSensor(mock_coordinator, device_info, definition)
        
        # Value doesn't contain decimal point, should be parsed as int
        assert sensor.native_value == 1200
        assert isinstance(sensor.native_value, int)

    def test_sensor_native_value_none(self, mock_coordinator, device_info):
        """Test sensor native_value when data is missing."""
        definition = {"key": "missing:param", "name": "Missing", "unit": None, "device_class": None, "state_class": None}
        sensor = CresControlSensor(mock_coordinator, device_info, definition)
        
        assert sensor.native_value is None

    def test_sensor_native_value_unparseable(self, mock_coordinator, device_info):
        """Test sensor native_value with unparseable data."""
        mock_coordinator.data["in-a:voltage"] = "invalid_value"
        definition = SENSOR_DEFINITIONS[0]
        sensor = CresControlSensor(mock_coordinator, device_info, definition)
        
        # Should fall back to raw string
        assert sensor.native_value == "invalid_value"


class TestSwitchEntities:
    """Test switch entity functionality."""

    @pytest.mark.asyncio
    async def test_switch_setup_entry(self, mock_hass, mock_config_entry, mock_coordinator, mock_client, device_info):
        """Test switch platform setup."""
        mock_hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "client": mock_client,
                    "device_info": device_info,
                }
            }
        }
        
        mock_add_entities = Mock()
        
        await switch_async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)
        
        # Verify entities were added
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        
        # Should create one entity per switch definition
        assert len(entities) == len(SWITCH_DEFINITIONS)
        
        for entity in entities:
            assert isinstance(entity, CresControlSwitch)

    def test_switch_definitions_structure(self):
        """Test that switch definitions have required fields."""
        for definition in SWITCH_DEFINITIONS:
            assert "key" in definition
            assert "name" in definition

    def test_switch_entity_initialization(self, mock_coordinator, mock_client, device_info):
        """Test switch entity initialization."""
        definition = SWITCH_DEFINITIONS[0]  # fan:enabled
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        assert switch._key == "fan:enabled"
        assert switch._attr_name == "CresControl Fan"
        assert switch._attr_unique_id == "test_entry_id_fan:enabled"
        assert switch._client == mock_client
        assert switch._device_info == device_info

    def test_switch_is_on_true(self, mock_coordinator, mock_client, device_info):
        """Test switch is_on property when switch is on."""
        definition = SWITCH_DEFINITIONS[0]  # fan:enabled
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        # fan:enabled is "true" in mock data
        assert switch.is_on is True

    def test_switch_is_on_false(self, mock_coordinator, mock_client, device_info):
        """Test switch is_on property when switch is off."""
        definition = SWITCH_DEFINITIONS[1]  # switch-12v:enabled
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        # switch-12v:enabled is "false" in mock data
        assert switch.is_on is False

    def test_switch_is_on_none(self, mock_coordinator, mock_client, device_info):
        """Test switch is_on property when data is missing."""
        definition = {"key": "missing:enabled", "name": "Missing"}
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        assert switch.is_on is None

    def test_switch_is_on_various_true_values(self, mock_coordinator, mock_client, device_info):
        """Test switch is_on property with various truthy values."""
        definition = {"key": "test:enabled", "name": "Test"}
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        # Test different true representations
        for true_value in ["true", "True", "TRUE", "t", "T", "1"]:
            mock_coordinator.data["test:enabled"] = true_value
            assert switch.is_on is True

    def test_switch_is_on_various_false_values(self, mock_coordinator, mock_client, device_info):
        """Test switch is_on property with various falsy values."""
        definition = {"key": "test:enabled", "name": "Test"}
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        # Test different false representations
        for false_value in ["false", "False", "FALSE", "f", "F", "0", "off", "disabled"]:
            mock_coordinator.data["test:enabled"] = false_value
            assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_switch_turn_on(self, mock_coordinator, mock_client, device_info):
        """Test switch turn_on functionality."""
        definition = SWITCH_DEFINITIONS[0]  # fan:enabled
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        await switch.async_turn_on()
        
        # Verify client was called to set value
        mock_client.set_value.assert_called_once_with("fan:enabled", True)
        
        # Verify coordinator refresh was triggered
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_turn_off(self, mock_coordinator, mock_client, device_info):
        """Test switch turn_off functionality."""
        definition = SWITCH_DEFINITIONS[0]  # fan:enabled
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        await switch.async_turn_off()
        
        # Verify client was called to set value
        mock_client.set_value.assert_called_once_with("fan:enabled", False)
        
        # Verify coordinator refresh was triggered
        mock_coordinator.async_request_refresh.assert_called_once()


class TestNumberEntities:
    """Test number entity functionality."""

    @pytest.mark.asyncio
    async def test_number_setup_entry(self, mock_hass, mock_config_entry, mock_coordinator, mock_client, device_info):
        """Test number platform setup."""
        mock_hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "client": mock_client,
                    "device_info": device_info,
                }
            }
        }
        
        mock_add_entities = Mock()
        
        await number_async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)
        
        # Verify entities were added
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        
        # Should create one entity per number definition
        assert len(entities) == len(NUMBER_DEFINITIONS)
        
        for entity in entities:
            assert isinstance(entity, CresControlNumber)

    def test_number_definitions_structure(self):
        """Test that number definitions have required fields."""
        for definition in NUMBER_DEFINITIONS:
            assert "key" in definition
            assert "name" in definition

    def test_number_entity_initialization(self, mock_coordinator, mock_client, device_info):
        """Test number entity initialization."""
        definition = NUMBER_DEFINITIONS[0]  # out-a:voltage
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        assert number._key == "out-a:voltage"
        assert number._attr_name == "CresControl Out A Voltage"
        assert number._attr_unique_id == "test_entry_id_out-a:voltage"
        assert number._attr_native_min_value == 0.0
        assert number._attr_native_max_value == 10.0
        assert number._attr_native_step == 0.01
        assert number._attr_native_unit_of_measurement == UnitOfElectricPotential.VOLT
        assert number._client == mock_client
        assert number._device_info == device_info

    def test_number_native_value_valid(self, mock_coordinator, mock_client, device_info):
        """Test number native_value with valid data."""
        definition = NUMBER_DEFINITIONS[0]  # out-a:voltage
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        # out-a:voltage is "5.0" in mock data
        assert number.native_value == 5.0
        assert isinstance(number.native_value, float)

    def test_number_native_value_none(self, mock_coordinator, mock_client, device_info):
        """Test number native_value when data is missing."""
        definition = {"key": "missing:voltage", "name": "Missing"}
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        assert number.native_value is None

    def test_number_native_value_invalid(self, mock_coordinator, mock_client, device_info):
        """Test number native_value with invalid data."""
        mock_coordinator.data["out-a:voltage"] = "invalid_voltage"
        definition = NUMBER_DEFINITIONS[0]
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        assert number.native_value is None

    @pytest.mark.asyncio
    async def test_number_set_native_value_normal(self, mock_coordinator, mock_client, device_info):
        """Test setting number value within normal range."""
        definition = NUMBER_DEFINITIONS[0]  # out-a:voltage
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        await number.async_set_native_value(7.5)
        
        # Verify client was called to set value
        mock_client.set_value.assert_called_once_with("out-a:voltage", 7.5)
        
        # Verify coordinator refresh was triggered
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_number_set_native_value_clamped_low(self, mock_coordinator, mock_client, device_info):
        """Test setting number value below minimum (should be clamped)."""
        definition = NUMBER_DEFINITIONS[0]  # out-a:voltage
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        await number.async_set_native_value(-5.0)
        
        # Should be clamped to minimum value (0.0)
        mock_client.set_value.assert_called_once_with("out-a:voltage", 0.0)

    @pytest.mark.asyncio
    async def test_number_set_native_value_clamped_high(self, mock_coordinator, mock_client, device_info):
        """Test setting number value above maximum (should be clamped)."""
        definition = NUMBER_DEFINITIONS[0]  # out-a:voltage
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        await number.async_set_native_value(15.0)
        
        # Should be clamped to maximum value (10.0)
        mock_client.set_value.assert_called_once_with("out-a:voltage", 10.0)

    @pytest.mark.asyncio
    async def test_number_set_native_value_exact_bounds(self, mock_coordinator, mock_client, device_info):
        """Test setting number value at exact boundaries."""
        definition = NUMBER_DEFINITIONS[0]  # out-a:voltage
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        # Test minimum boundary
        await number.async_set_native_value(0.0)
        mock_client.set_value.assert_called_with("out-a:voltage", 0.0)
        
        # Reset mock
        mock_client.reset_mock()
        mock_coordinator.async_request_refresh.reset_mock()
        
        # Test maximum boundary
        await number.async_set_native_value(10.0)
        mock_client.set_value.assert_called_with("out-a:voltage", 10.0)


class TestFanEntities:
    """Test fan entity functionality."""

    @pytest.mark.asyncio
    async def test_fan_setup_entry(self, mock_hass, mock_config_entry, mock_coordinator, mock_client, device_info):
        """Test fan platform setup."""
        mock_hass.data = {
            DOMAIN: {
                mock_config_entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "client": mock_client,
                    "device_info": device_info,
                }
            }
        }
        
        mock_add_entities = Mock()
        
        await fan_async_setup_entry(mock_hass, mock_config_entry, mock_add_entities)
        
        # Verify entity was added
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        
        # Should create one fan entity
        assert len(entities) == 1
        assert isinstance(entities[0], CresControlFan)

    def test_fan_entity_initialization(self, mock_coordinator, mock_client, device_info):
        """Test fan entity initialization."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        assert fan._attr_name == "CresControl Fan"
        assert fan._attr_unique_id == "test_entry_id_fan"
        assert fan._attr_speed_count == 100
        assert fan._device_info == device_info
        
        # Check supported features
        from homeassistant.components.fan import FanEntityFeature
        expected_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        assert fan._attr_supported_features == expected_features

    def test_fan_is_on_enabled_with_duty_cycle(self, mock_coordinator, mock_client, device_info):
        """Test fan is_on property when enabled with duty cycle."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        # fan:enabled is "1" and duty-cycle is "75.0" in mock data
        assert fan.is_on is True

    def test_fan_is_on_enabled_no_duty_cycle(self, mock_coordinator, mock_client, device_info):
        """Test fan is_on property when enabled but no duty cycle."""
        mock_coordinator.data["fan:enabled"] = "1"
        mock_coordinator.data["fan:duty-cycle"] = "0"
        fan = CresControlFan(mock_coordinator, device_info)
        
        assert fan.is_on is False

    def test_fan_is_on_disabled(self, mock_coordinator, mock_client, device_info):
        """Test fan is_on property when disabled."""
        mock_coordinator.data["fan:enabled"] = "0"
        mock_coordinator.data["fan:duty-cycle"] = "75.0"
        fan = CresControlFan(mock_coordinator, device_info)
        
        assert fan.is_on is False

    def test_fan_percentage_enabled(self, mock_coordinator, mock_client, device_info):
        """Test fan percentage property when enabled."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        # fan:duty-cycle is "75.0" in mock data
        assert fan.percentage == 75

    def test_fan_percentage_disabled(self, mock_coordinator, mock_client, device_info):
        """Test fan percentage property when disabled."""
        mock_coordinator.data["fan:enabled"] = "0"
        fan = CresControlFan(mock_coordinator, device_info)
        
        assert fan.percentage == 0

    def test_fan_percentage_none_data(self, mock_coordinator, mock_client, device_info):
        """Test fan percentage property with missing data."""
        mock_coordinator.data = None
        fan = CresControlFan(mock_coordinator, device_info)
        
        assert fan.percentage == 0

    def test_fan_icon_on(self, mock_coordinator, mock_client, device_info):
        """Test fan icon when on."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        # Fan should be on based on mock data
        from custom_components.crescontrol.const import FAN_ICON
        assert fan.icon == FAN_ICON

    def test_fan_icon_off(self, mock_coordinator, mock_client, device_info):
        """Test fan icon when off."""
        mock_coordinator.data["fan:enabled"] = "0"
        fan = CresControlFan(mock_coordinator, device_info)
        
        from custom_components.crescontrol.const import FAN_ICON_OFF
        assert fan.icon == FAN_ICON_OFF

    @pytest.mark.asyncio
    async def test_fan_turn_on_no_percentage(self, mock_coordinator, mock_client, device_info):
        """Test fan turn_on without percentage (should use minimum)."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        await fan.async_turn_on()
        
        # Should call set_fan_speed with minimum duty cycle or low speed
        mock_client.set_fan_speed.assert_called_once()
        args = mock_client.set_fan_speed.call_args
        assert args[0][0] >= 20  # At least minimum or low speed
        assert args[1]["enable"] is True
        
        # Verify coordinator refresh was triggered
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_fan_turn_on_with_percentage(self, mock_coordinator, mock_client, device_info):
        """Test fan turn_on with specific percentage."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        await fan.async_turn_on(percentage=60)
        
        # Should call set_fan_speed with specified percentage
        mock_client.set_fan_speed.assert_called_once_with(60, enable=True)
        
        # Verify coordinator refresh was triggered
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_fan_turn_on_with_preset(self, mock_coordinator, mock_client, device_info):
        """Test fan turn_on with preset mode."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        await fan.async_turn_on(preset_mode="medium")
        
        # Should call set_fan_speed with medium speed (50%)
        mock_client.set_fan_speed.assert_called_once_with(50, enable=True)

    @pytest.mark.asyncio
    async def test_fan_turn_off(self, mock_coordinator, mock_client, device_info):
        """Test fan turn_off functionality."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        await fan.async_turn_off()
        
        # Should call set_fan_enabled with False
        mock_client.set_fan_enabled.assert_called_once_with(False)
        
        # Verify coordinator refresh was triggered
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_fan_set_percentage_normal(self, mock_coordinator, mock_client, device_info):
        """Test setting fan percentage within normal range."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        await fan.async_set_percentage(80)
        
        # Should call set_fan_speed with specified percentage
        mock_client.set_fan_speed.assert_called_once_with(80, enable=True)
        
        # Verify coordinator refresh was triggered
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_fan_set_percentage_zero(self, mock_coordinator, mock_client, device_info):
        """Test setting fan percentage to zero (turn off)."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        await fan.async_set_percentage(0)
        
        # Should call set_fan_enabled with False
        mock_client.set_fan_enabled.assert_called_once_with(False)
        
        # Verify coordinator refresh was triggered
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_fan_set_percentage_invalid_range(self, mock_coordinator, mock_client, device_info):
        """Test setting fan percentage outside valid range."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        # Test negative percentage (should be ignored)
        await fan.async_set_percentage(-10)
        mock_client.set_fan_speed.assert_not_called()
        mock_client.set_fan_enabled.assert_not_called()
        
        # Reset mocks
        mock_client.reset_mock()
        
        # Test percentage over 100 (should be ignored)
        await fan.async_set_percentage(120)
        mock_client.set_fan_speed.assert_not_called()
        mock_client.set_fan_enabled.assert_not_called()

    def test_fan_extra_state_attributes(self, mock_coordinator, mock_client, device_info):
        """Test fan extra state attributes."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        attributes = fan.extra_state_attributes
        
        # Should include fan data
        assert "duty_cycle" in attributes
        assert "duty_cycle_min" in attributes
        assert "rpm" in attributes
        assert "raw_enabled" in attributes
        
        # Check values from mock data
        assert attributes["duty_cycle"] == 75.0
        assert attributes["duty_cycle_min"] == 20.0
        assert attributes["rpm"] == 1200
        assert attributes["raw_enabled"] is True

    def test_fan_get_current_fan_data_valid(self, mock_coordinator, mock_client, device_info):
        """Test _get_current_fan_data with valid data."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        data = fan._get_current_fan_data()
        
        assert data is not None
        assert data["enabled"] is True
        assert data["duty_cycle"] == 75.0
        assert data["duty_cycle_min"] == 20.0
        assert data["rpm"] == 1200

    def test_fan_get_current_fan_data_invalid_values(self, mock_coordinator, mock_client, device_info):
        """Test _get_current_fan_data with invalid values."""
        # Set invalid data
        mock_coordinator.data["fan:enabled"] = "invalid"
        mock_coordinator.data["fan:duty-cycle"] = "not_a_number"
        mock_coordinator.data["fan:rpm"] = "invalid_rpm"
        
        fan = CresControlFan(mock_coordinator, device_info)
        data = fan._get_current_fan_data()
        
        assert data is not None
        assert data["enabled"] is False  # Invalid enabled value defaults to False
        assert data["duty_cycle"] == 0.0  # Invalid duty cycle defaults to 0
        assert data["rpm"] == 0  # Invalid RPM defaults to 0

    def test_fan_get_current_fan_data_no_coordinator_data(self, mock_coordinator, mock_client, device_info):
        """Test _get_current_fan_data with no coordinator data."""
        mock_coordinator.data = None
        fan = CresControlFan(mock_coordinator, device_info)
        
        data = fan._get_current_fan_data()
        assert data is None

    def test_fan_boolean_value_parsing(self, mock_coordinator, mock_client, device_info):
        """Test fan enabled state parsing with various boolean representations."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        # Test various true values
        for true_value in ["1", 1, "true", True, "on", "enabled"]:
            mock_coordinator.data["fan:enabled"] = true_value
            data = fan._get_current_fan_data()
            assert data["enabled"] is True, f"Failed for true value: {true_value}"
        
        # Test various false values
        for false_value in ["0", 0, "false", False, "off", "disabled"]:
            mock_coordinator.data["fan:enabled"] = false_value
            data = fan._get_current_fan_data()
            assert data["enabled"] is False, f"Failed for false value: {false_value}"

    def test_fan_duty_cycle_clamping(self, mock_coordinator, mock_client, device_info):
        """Test duty cycle value clamping to valid range."""
        fan = CresControlFan(mock_coordinator, device_info)
        
        # Test value below minimum
        mock_coordinator.data["fan:duty-cycle"] = "-10.0"
        data = fan._get_current_fan_data()
        assert data["duty_cycle"] == 0.0
        
        # Test value above maximum
        mock_coordinator.data["fan:duty-cycle"] = "150.0"
        data = fan._get_current_fan_data()
        assert data["duty_cycle"] == 100.0
        
        # Test valid value
        mock_coordinator.data["fan:duty-cycle"] = "50.0"
        data = fan._get_current_fan_data()
        assert data["duty_cycle"] == 50.0


class TestEntityUniqueIds:
    """Test entity unique ID generation."""

    def test_sensor_unique_ids_are_unique(self, mock_coordinator, device_info):
        """Test that all sensor entities have unique IDs."""
        unique_ids = set()
        
        for definition in SENSOR_DEFINITIONS:
            sensor = CresControlSensor(mock_coordinator, device_info, definition)
            assert sensor._attr_unique_id not in unique_ids
            unique_ids.add(sensor._attr_unique_id)

    def test_switch_unique_ids_are_unique(self, mock_coordinator, mock_client, device_info):
        """Test that all switch entities have unique IDs."""
        unique_ids = set()
        
        for definition in SWITCH_DEFINITIONS:
            switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
            assert switch._attr_unique_id not in unique_ids
            unique_ids.add(switch._attr_unique_id)

    def test_number_unique_ids_are_unique(self, mock_coordinator, mock_client, device_info):
        """Test that all number entities have unique IDs."""
        unique_ids = set()
        
        for definition in NUMBER_DEFINITIONS:
            number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
            assert number._attr_unique_id not in unique_ids
            unique_ids.add(number._attr_unique_id)

    def test_cross_platform_unique_ids_are_unique(self, mock_coordinator, mock_client, device_info):
        """Test that unique IDs are unique across all platforms."""
        unique_ids = set()
        
        # Check sensors
        for definition in SENSOR_DEFINITIONS:
            sensor = CresControlSensor(mock_coordinator, device_info, definition)
            assert sensor._attr_unique_id not in unique_ids
            unique_ids.add(sensor._attr_unique_id)
        
        # Check switches
        for definition in SWITCH_DEFINITIONS:
            switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
            assert switch._attr_unique_id not in unique_ids
            unique_ids.add(switch._attr_unique_id)
        
        # Check numbers
        for definition in NUMBER_DEFINITIONS:
            number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
            assert number._attr_unique_id not in unique_ids
            unique_ids.add(number._attr_unique_id)
        
        # Check fan
        fan = CresControlFan(mock_coordinator, device_info)
        assert fan._attr_unique_id not in unique_ids
        unique_ids.add(fan._attr_unique_id)


class TestEntityDeviceInfo:
    """Test entity device information."""

    def test_all_entities_have_consistent_device_info(self, mock_coordinator, mock_client, device_info):
        """Test that all entities return the same device info."""
        # Test sensor
        sensor_definition = SENSOR_DEFINITIONS[0]
        sensor = CresControlSensor(mock_coordinator, device_info, sensor_definition)
        assert sensor.device_info == device_info
        
        # Test switch
        switch_definition = SWITCH_DEFINITIONS[0]
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, switch_definition)
        assert switch.device_info == device_info
        
        # Test number
        number_definition = NUMBER_DEFINITIONS[0]
        number = CresControlNumber(mock_coordinator, mock_client, device_info, number_definition)
        assert number.device_info == device_info
        
        # Test fan
        fan = CresControlFan(mock_coordinator, device_info)
        assert fan.device_info == device_info


class TestEntityDefinitions:
    """Test entity definition consistency."""

    def test_sensor_definitions_have_expected_keys(self):
        """Test that sensor definitions contain expected parameters."""
        expected_keys = {
            "in-a:voltage",
            "in-b:voltage",
            "fan:rpm",
        }
        
        actual_keys = {definition["key"] for definition in SENSOR_DEFINITIONS}
        assert actual_keys == expected_keys

    def test_switch_definitions_have_expected_keys(self):
        """Test that switch definitions contain expected parameters."""
        expected_keys = {
            "fan:enabled",
            "switch-12v:enabled",
            "switch-24v-a:enabled",
            "switch-24v-b:enabled",
            "out-a:enabled",
            "out-b:enabled",
            "out-c:enabled",
            "out-d:enabled",
            "out-e:enabled",
            "out-f:enabled",
            # PWM enable switches for outputs A-B
            "out-a:pwm-enabled",
            "out-b:pwm-enabled",
            # PWM enable switches for power rail switches
            "switch-12v:pwm-enabled",
            "switch-24v-a:pwm-enabled",
            "switch-24v-b:pwm-enabled",
        }
        
        actual_keys = {definition["key"] for definition in SWITCH_DEFINITIONS}
        assert actual_keys == expected_keys

    def test_number_definitions_have_expected_keys(self):
        """Test that number definitions contain expected parameters."""
        expected_keys = {
            "out-a:voltage",
            "out-b:voltage",
            "out-c:voltage",
            "out-d:voltage",
            "out-e:voltage",
            "out-f:voltage",
        }
        
        actual_keys = {definition["key"] for definition in NUMBER_DEFINITIONS}
        # Update expected keys to include PWM entities
        expected_keys = {
            "out-a:voltage",
            "out-b:voltage",
            "out-c:voltage",
            "out-d:voltage",
            "out-e:voltage",
            "out-f:voltage",
            # PWM duty cycle controls
            "out-a:duty-cycle",
            "out-b:duty-cycle",
            "switch-12v:duty-cycle",
            "switch-24v-a:duty-cycle",
            "switch-24v-b:duty-cycle",
            # PWM frequency controls
            "out-a:pwm-frequency",
            "out-b:pwm-frequency",
            "switch-12v:pwm-frequency",
            "switch-24v-a:pwm-frequency",
            "switch-24v-b:pwm-frequency",
        }
        assert actual_keys == expected_keys


class TestPWMNumberEntities:
    """Test PWM number entity functionality."""

    def test_pwm_duty_cycle_entity_initialization(self, mock_coordinator, mock_client, device_info):
        """Test PWM duty cycle number entity initialization."""
        definition = {
            "key": "out-a:duty-cycle",
            "name": "Out A Duty Cycle",
            "icon": "mdi:pulse",
            "entity_category": EntityCategory.CONFIG,
            "min_value": 0.0,
            "max_value": 100.0,
            "step": 0.1,
            "unit": "%",
        }
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        assert number._key == "out-a:duty-cycle"
        assert number._attr_name == "CresControl Out A Duty Cycle"
        assert number._attr_native_min_value == 0.0
        assert number._attr_native_max_value == 100.0
        assert number._attr_native_step == 0.1
        
        from homeassistant.const import PERCENTAGE
        assert number._attr_native_unit_of_measurement == PERCENTAGE
        assert number._attr_icon == "mdi:pulse"

    def test_pwm_frequency_entity_initialization(self, mock_coordinator, mock_client, device_info):
        """Test PWM frequency number entity initialization."""
        definition = {
            "key": "out-a:pwm-frequency",
            "name": "Out A PWM Frequency",
            "icon": "mdi:sine-wave",
            "entity_category": EntityCategory.CONFIG,
            "min_value": 0.0,
            "max_value": 1000.0,
            "step": 1.0,
            "unit": "Hz",
        }
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        assert number._key == "out-a:pwm-frequency"
        assert number._attr_name == "CresControl Out A PWM Frequency"
        assert number._attr_native_min_value == 0.0
        assert number._attr_native_max_value == 1000.0
        assert number._attr_native_step == 1.0
        
        from homeassistant.const import UnitOfFrequency
        assert number._attr_native_unit_of_measurement == UnitOfFrequency.HERTZ
        assert number._attr_icon == "mdi:sine-wave"

    def test_pwm_switch_duty_cycle_entity_initialization(self, mock_coordinator, mock_client, device_info):
        """Test PWM switch duty cycle number entity initialization."""
        definition = {
            "key": "switch-12v:duty-cycle",
            "name": "12V Switch Duty Cycle",
            "icon": "mdi:pulse",
            "entity_category": EntityCategory.CONFIG,
            "min_value": 0.0,
            "max_value": 100.0,
            "step": 0.1,
            "unit": "%",
        }
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        assert number._key == "switch-12v:duty-cycle"
        assert number._attr_name == "CresControl 12V Switch Duty Cycle"
        assert number._attr_native_min_value == 0.0
        assert number._attr_native_max_value == 100.0
        
        from homeassistant.const import PERCENTAGE
        assert number._attr_native_unit_of_measurement == PERCENTAGE

    @pytest.mark.asyncio
    async def test_pwm_duty_cycle_set_value_valid_range(self, mock_coordinator, mock_client, device_info):
        """Test setting PWM duty cycle within valid range."""
        definition = {
            "key": "out-a:duty-cycle",
            "name": "Out A Duty Cycle",
            "min_value": 0.0,
            "max_value": 100.0,
            "step": 0.1,
            "unit": "%",
        }
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        await number.async_set_native_value(50.5)
        
        mock_client.set_value.assert_called_once_with("out-a:duty-cycle", 50.5)
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_pwm_frequency_set_value_valid_range(self, mock_coordinator, mock_client, device_info):
        """Test setting PWM frequency within valid range."""
        definition = {
            "key": "out-a:pwm-frequency",
            "name": "Out A PWM Frequency",
            "min_value": 0.0,
            "max_value": 1000.0,
            "step": 1.0,
            "unit": "Hz",
        }
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        await number.async_set_native_value(100.0)
        
        mock_client.set_value.assert_called_once_with("out-a:pwm-frequency", 100.0)
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_pwm_duty_cycle_set_value_clamping(self, mock_coordinator, mock_client, device_info):
        """Test PWM duty cycle value clamping."""
        definition = {
            "key": "out-a:duty-cycle",
            "name": "Out A Duty Cycle",
            "min_value": 0.0,
            "max_value": 100.0,
            "step": 0.1,
            "unit": "%",
        }
        number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
        
        # Test clamping above maximum
        await number.async_set_native_value(150.0)
        mock_client.set_value.assert_called_with("out-a:duty-cycle", 100.0)
        
        # Reset mock
        mock_client.reset_mock()
        
        # Test clamping below minimum
        await number.async_set_native_value(-10.0)
        mock_client.set_value.assert_called_with("out-a:duty-cycle", 0.0)


class TestPWMSwitchEntities:
    """Test PWM switch entity functionality."""

    def test_pwm_switch_entity_initialization(self, mock_coordinator, mock_client, device_info):
        """Test PWM enable switch entity initialization."""
        definition = {
            "key": "out-a:pwm-enabled",
            "name": "Out A PWM Enabled",
            "icon": "mdi:toggle-switch",
            "entity_category": EntityCategory.CONFIG,
        }
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        assert switch._key == "out-a:pwm-enabled"
        assert switch._attr_name == "CresControl Out A PWM Enabled"
        assert switch._attr_icon == "mdi:toggle-switch"
        assert switch._attr_entity_category == EntityCategory.CONFIG

    def test_pwm_switch_power_rail_initialization(self, mock_coordinator, mock_client, device_info):
        """Test PWM enable switch for power rail initialization."""
        definition = {
            "key": "switch-12v:pwm-enabled",
            "name": "12V Switch PWM Enabled",
            "icon": "mdi:toggle-switch",
            "entity_category": EntityCategory.CONFIG,
        }
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        assert switch._key == "switch-12v:pwm-enabled"
        assert switch._attr_name == "CresControl 12V Switch PWM Enabled"

    def test_pwm_switch_is_on_with_mock_data(self, mock_coordinator, mock_client, device_info):
        """Test PWM switch is_on property with mock data."""
        # Add PWM data to mock coordinator
        mock_coordinator.data["out-a:pwm-enabled"] = "true"
        mock_coordinator.data["switch-12v:pwm-enabled"] = "false"
        
        # Test output PWM switch
        definition = {"key": "out-a:pwm-enabled", "name": "Out A PWM Enabled"}
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        assert switch.is_on is True
        
        # Test power rail PWM switch
        definition = {"key": "switch-12v:pwm-enabled", "name": "12V Switch PWM Enabled"}
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        assert switch.is_on is False

    @pytest.mark.asyncio
    async def test_pwm_switch_turn_on(self, mock_coordinator, mock_client, device_info):
        """Test PWM switch turn_on functionality."""
        definition = {"key": "out-a:pwm-enabled", "name": "Out A PWM Enabled"}
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        await switch.async_turn_on()
        
        mock_client.set_value.assert_called_once_with("out-a:pwm-enabled", True)
        mock_coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_pwm_switch_turn_off(self, mock_coordinator, mock_client, device_info):
        """Test PWM switch turn_off functionality."""
        definition = {"key": "out-a:pwm-enabled", "name": "Out A PWM Enabled"}
        switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
        
        await switch.async_turn_off()
        
        mock_client.set_value.assert_called_once_with("out-a:pwm-enabled", False)
        mock_coordinator.async_request_refresh.assert_called_once()


class TestPWMEntityUnits:
    """Test PWM entity units and ranges."""

    def test_all_pwm_duty_cycle_entities_have_percentage_unit(self, mock_coordinator, mock_client, device_info):
        """Test that all PWM duty cycle entities use percentage unit."""
        duty_cycle_definitions = [
            def_ for def_ in NUMBER_DEFINITIONS
            if "duty-cycle" in def_["key"]
        ]
        
        from homeassistant.const import PERCENTAGE
        
        for definition in duty_cycle_definitions:
            number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
            assert number._attr_native_unit_of_measurement == PERCENTAGE
            assert number._attr_native_min_value == 0.0
            assert number._attr_native_max_value == 100.0

    def test_all_pwm_frequency_entities_have_hertz_unit(self, mock_coordinator, mock_client, device_info):
        """Test that all PWM frequency entities use hertz unit."""
        frequency_definitions = [
            def_ for def_ in NUMBER_DEFINITIONS
            if "pwm-frequency" in def_["key"]
        ]
        
        from homeassistant.const import UnitOfFrequency
        
        for definition in frequency_definitions:
            number = CresControlNumber(mock_coordinator, mock_client, device_info, definition)
            assert number._attr_native_unit_of_measurement == UnitOfFrequency.HERTZ
            assert number._attr_native_min_value == 0.0
            assert number._attr_native_max_value == 1000.0

    def test_all_pwm_enabled_switches_have_config_category(self, mock_coordinator, mock_client, device_info):
        """Test that all PWM enabled switches are categorized as config."""
        pwm_enabled_definitions = [
            def_ for def_ in SWITCH_DEFINITIONS
            if "pwm-enabled" in def_["key"]
        ]
        
        for definition in pwm_enabled_definitions:
            switch = CresControlSwitch(mock_coordinator, mock_client, device_info, definition)
            assert switch._attr_entity_category == EntityCategory.CONFIG