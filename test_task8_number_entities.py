#!/usr/bin/env python3
"""
Test script for Task 8: Core number entities for voltage control.

This test validates:
1. Number entities are created for output voltages (A-F)
2. Proper min/max values and step sizes are set
3. Value setting via HTTP commands works
4. Real-time feedback is functional
"""

import asyncio
import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Add the custom_components directory to the path
sys.path.insert(0, 'custom_components')

from crescontrol.number import (
    CORE_NUMBERS,
    CresControlNumber,
    async_setup_entry
)
from crescontrol.const import DOMAIN

# Set up logging
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class MockHomeAssistant:
    """Mock Home Assistant instance."""
    
    def __init__(self):
        self.data = {DOMAIN: {}}


class MockConfigEntry:
    """Mock config entry."""
    
    def __init__(self, entry_id: str = "test_entry"):
        self.entry_id = entry_id


class MockCoordinator:
    """Mock coordinator with test data."""
    
    def __init__(self):
        self.config_entry = MockConfigEntry()
        self.data = {
            "out-a:voltage": "5.25",
            "out-b:voltage": "3.30",
            "out-c:voltage": "0.00",
            "out-d:voltage": "7.50",
            "out-e:voltage": "2.10",
            "out-f:voltage": "9.99",
        }
        
    async def async_request_refresh(self):
        """Mock refresh method."""
        pass


class MockClient:
    """Mock API client."""
    
    def __init__(self):
        self.set_commands = []
        
    async def set_value(self, parameter: str, value: float):
        """Mock set_value method."""
        self.set_commands.append((parameter, value))
        _LOGGER.info(f"Mock set_value called: {parameter} = {value}")


async def test_core_numbers_definition():
    """Test that CORE_NUMBERS contains all expected voltage outputs."""
    print("\n=== Testing CORE_NUMBERS Definition ===")
    
    expected_outputs = ["out-a:voltage", "out-b:voltage", "out-c:voltage", 
                       "out-d:voltage", "out-e:voltage", "out-f:voltage"]
    
    # Check that all expected outputs are defined
    defined_keys = [num["key"] for num in CORE_NUMBERS]
    print(f"Defined number entities: {defined_keys}")
    
    for expected in expected_outputs:
        assert expected in defined_keys, f"Missing number entity: {expected}"
        print(f"✓ Found number entity: {expected}")
    
    # Check properties of each number definition
    for num_def in CORE_NUMBERS:
        print(f"\nChecking {num_def['key']}:")
        
        # Check required properties
        assert "name" in num_def, f"Missing 'name' for {num_def['key']}"
        assert "min_value" in num_def, f"Missing 'min_value' for {num_def['key']}"
        assert "max_value" in num_def, f"Missing 'max_value' for {num_def['key']}"
        assert "step" in num_def, f"Missing 'step' for {num_def['key']}"
        
        # Check value ranges
        assert num_def["min_value"] == 0.0, f"Wrong min_value for {num_def['key']}: {num_def['min_value']}"
        assert num_def["max_value"] == 10.0, f"Wrong max_value for {num_def['key']}: {num_def['max_value']}"
        assert num_def["step"] == 0.01, f"Wrong step for {num_def['key']}: {num_def['step']}"
        
        print(f"  ✓ Name: {num_def['name']}")
        print(f"  ✓ Range: {num_def['min_value']} - {num_def['max_value']}")
        print(f"  ✓ Step: {num_def['step']}")
    
    print("\n✓ All CORE_NUMBERS definitions are correct")


async def test_number_entity_creation():
    """Test creating CresControlNumber entities."""
    print("\n=== Testing Number Entity Creation ===")
    
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"identifiers": {(DOMAIN, "test_host")}}
    
    # Test creating a number entity
    num_def = CORE_NUMBERS[0]  # out-a:voltage
    entity = CresControlNumber(coordinator, client, device_info, num_def)
    
    print(f"Created entity for: {num_def['key']}")
    print(f"Entity name: {entity.name}")
    print(f"Entity unique_id: {entity.unique_id}")
    print(f"Min value: {entity.native_min_value}")
    print(f"Max value: {entity.native_max_value}")
    print(f"Step: {entity.native_step}")
    print(f"Unit: {entity.native_unit_of_measurement}")
    
    # Verify properties
    assert entity.name == f"CresControl {num_def['name']}"
    assert entity.unique_id == f"{coordinator.config_entry.entry_id}_{num_def['key']}"
    assert entity.native_min_value == 0.0
    assert entity.native_max_value == 10.0
    assert entity.native_step == 0.01
    assert entity.native_unit_of_measurement == "V"
    
    print("✓ Number entity created successfully with correct properties")


async def test_number_entity_value_reading():
    """Test reading values from number entities."""
    print("\n=== Testing Number Entity Value Reading ===")
    
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"identifiers": {(DOMAIN, "test_host")}}
    
    # Test each number entity
    for num_def in CORE_NUMBERS:
        entity = CresControlNumber(coordinator, client, device_info, num_def)
        value = entity.native_value
        expected_value = float(coordinator.data[num_def["key"]])
        
        print(f"{num_def['key']}: {value} (expected: {expected_value})")
        assert value == expected_value, f"Wrong value for {num_def['key']}: {value} != {expected_value}"
        print(f"  ✓ Value correctly parsed: {value}")
    
    print("✓ All number entities read values correctly")


async def test_number_entity_value_setting():
    """Test setting values through number entities."""
    print("\n=== Testing Number Entity Value Setting ===")
    
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"identifiers": {(DOMAIN, "test_host")}}
    
    # Test setting values
    entity = CresControlNumber(coordinator, client, device_info, CORE_NUMBERS[0])
    
    test_values = [0.0, 5.25, 10.0, 3.14]
    
    for test_value in test_values:
        print(f"Setting value: {test_value}")
        await entity.async_set_native_value(test_value)
        
        # Check that set_value was called correctly
        assert len(client.set_commands) > 0, "set_value was not called"
        last_command = client.set_commands[-1]
        assert last_command[0] == "out-a:voltage", f"Wrong parameter: {last_command[0]}"
        assert last_command[1] == test_value, f"Wrong value: {last_command[1]} != {test_value}"
        
        print(f"  ✓ set_value called with: {last_command[0]} = {last_command[1]}")
    
    print("✓ Value setting works correctly")


async def test_number_entity_value_clamping():
    """Test that values are clamped to min/max range."""
    print("\n=== Testing Number Entity Value Clamping ===")
    
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"identifiers": {(DOMAIN, "test_host")}}
    
    entity = CresControlNumber(coordinator, client, device_info, CORE_NUMBERS[0])
    
    # Test values outside range
    test_cases = [
        (-1.0, 0.0),   # Below minimum
        (15.0, 10.0),  # Above maximum
        (5.0, 5.0),    # Within range
    ]
    
    for input_value, expected_value in test_cases:
        print(f"Testing input: {input_value}, expected clamped: {expected_value}")
        
        initial_commands = len(client.set_commands)
        await entity.async_set_native_value(input_value)
        
        # Check that the clamped value was sent
        assert len(client.set_commands) > initial_commands, "set_value was not called"
        last_command = client.set_commands[-1]
        assert last_command[1] == expected_value, f"Value not clamped correctly: {last_command[1]} != {expected_value}"
        
        print(f"  ✓ Value clamped correctly: {input_value} -> {last_command[1]}")
    
    print("✓ Value clamping works correctly")


async def test_async_setup_entry():
    """Test the async_setup_entry function."""
    print("\n=== Testing async_setup_entry ===")
    
    hass = MockHomeAssistant()
    entry = MockConfigEntry()
    
    # Mock the data that would be set up by __init__.py
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"identifiers": {(DOMAIN, "test_host")}}
    
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "device_info": device_info,
    }
    
    # Mock async_add_entities
    added_entities = []
    
    def mock_add_entities(entities):
        added_entities.extend(entities)
    
    # Call async_setup_entry
    await async_setup_entry(hass, entry, mock_add_entities)
    
    # Verify entities were created
    assert len(added_entities) == len(CORE_NUMBERS), f"Wrong number of entities: {len(added_entities)} != {len(CORE_NUMBERS)}"
    
    print(f"Created {len(added_entities)} number entities:")
    for entity in added_entities:
        print(f"  - {entity.name} ({entity.unique_id})")
        assert isinstance(entity, CresControlNumber), f"Wrong entity type: {type(entity)}"
    
    print("✓ async_setup_entry works correctly")


async def test_error_handling():
    """Test error handling in number entities."""
    print("\n=== Testing Error Handling ===")
    
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"identifiers": {(DOMAIN, "test_host")}}
    
    # Test with invalid data
    coordinator.data = {
        "out-a:voltage": "invalid",
        "out-b:voltage": "",
        "out-c:voltage": None,
    }
    
    for i, num_def in enumerate(CORE_NUMBERS[:3]):
        entity = CresControlNumber(coordinator, client, device_info, num_def)
        value = entity.native_value
        
        print(f"{num_def['key']}: {value} (from invalid data)")
        assert value is None, f"Should return None for invalid data: {value}"
        print(f"  ✓ Correctly handled invalid data")
    
    # Test with no coordinator data
    coordinator.data = None
    entity = CresControlNumber(coordinator, client, device_info, CORE_NUMBERS[0])
    value = entity.native_value
    assert value is None, f"Should return None when no coordinator data: {value}"
    print("  ✓ Correctly handled missing coordinator data")
    
    print("✓ Error handling works correctly")


async def main():
    """Run all tests."""
    print("Starting Task 8 Number Entities Tests")
    print("=" * 50)
    
    try:
        await test_core_numbers_definition()
        await test_number_entity_creation()
        await test_number_entity_value_reading()
        await test_number_entity_value_setting()
        await test_number_entity_value_clamping()
        await test_async_setup_entry()
        await test_error_handling()
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED!")
        print("\nTask 8 Implementation Summary:")
        print("- ✓ Created number entities for output voltages (A-F)")
        print("- ✓ Set proper min/max values (0.0-10.0V) and step sizes (0.01V)")
        print("- ✓ Implemented value setting via HTTP commands")
        print("- ✓ Added proper error handling and value validation")
        print("- ✓ Entities support real-time feedback via coordinator")
        print("- ✓ All entities have proper unique IDs and device associations")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)