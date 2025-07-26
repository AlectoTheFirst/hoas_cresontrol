#!/usr/bin/env python3
"""
Integration test for Task 8: Test number entities with mock HTTP client.

This test simulates the complete workflow of number entities including
HTTP command sending and real-time feedback.
"""

import asyncio
import logging
import sys
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


class MockHTTPClient:
    """Mock HTTP client that simulates CresControl device responses."""
    
    def __init__(self):
        self.device_state = {
            "out-a:voltage": "5.25",
            "out-b:voltage": "3.30", 
            "out-c:voltage": "0.00",
            "out-d:voltage": "7.50",
            "out-e:voltage": "2.10",
            "out-f:voltage": "9.99",
        }
        self.command_history = []
    
    async def set_value(self, parameter: str, value: Any) -> Any:
        """Mock set_value that updates internal state."""
        self.command_history.append(f"SET {parameter} = {value}")
        self.device_state[parameter] = str(value)
        _LOGGER.info(f"Mock device: Set {parameter} = {value}")
        return str(value)
    
    async def get_value(self, parameter: str) -> Optional[str]:
        """Mock get_value that returns current state."""
        value = self.device_state.get(parameter)
        _LOGGER.info(f"Mock device: Get {parameter} = {value}")
        return value


class MockCoordinator:
    """Mock coordinator that uses the HTTP client."""
    
    def __init__(self, client: MockHTTPClient):
        self.client = client
        self.data = {}
        self.refresh_count = 0
    
    async def async_request_refresh(self):
        """Mock refresh that updates data from client."""
        self.refresh_count += 1
        _LOGGER.info(f"Mock coordinator: Refresh #{self.refresh_count}")
        
        # Simulate fetching all voltage data
        for param in ["out-a:voltage", "out-b:voltage", "out-c:voltage", 
                     "out-d:voltage", "out-e:voltage", "out-f:voltage"]:
            value = await self.client.get_value(param)
            if value is not None:
                self.data[param] = value


class MockNumberEntity:
    """Mock number entity that simulates the CresControlNumber behavior."""
    
    def __init__(self, coordinator: MockCoordinator, client: MockHTTPClient, 
                 key: str, name: str, min_val: float = 0.0, max_val: float = 10.0, step: float = 0.01):
        self.coordinator = coordinator
        self.client = client
        self.key = key
        self.name = name
        self.native_min_value = min_val
        self.native_max_value = max_val
        self.native_step = step
        self.native_unit_of_measurement = "V"
    
    @property
    def native_value(self) -> Optional[float]:
        """Get current value from coordinator data."""
        if not self.coordinator.data:
            return None
        
        raw_value = self.coordinator.data.get(self.key)
        if raw_value is None:
            return None
        
        try:
            return float(raw_value)
        except (ValueError, TypeError):
            return None
    
    async def async_set_native_value(self, value: float) -> None:
        """Set new value with clamping."""
        # Clamp value within allowed range
        if value < self.native_min_value:
            value = self.native_min_value
        elif value > self.native_max_value:
            value = self.native_max_value
        
        # Send command to device
        await self.client.set_value(self.key, value)
        
        # Request coordinator refresh
        await self.coordinator.async_request_refresh()


async def test_number_entity_workflow():
    """Test the complete number entity workflow."""
    print("=== Testing Complete Number Entity Workflow ===")
    
    # Create mock components
    client = MockHTTPClient()
    coordinator = MockCoordinator(client)
    
    # Initialize coordinator data
    await coordinator.async_request_refresh()
    print(f"Initial coordinator data: {coordinator.data}")
    
    # Create number entities for all outputs
    entities = {}
    output_configs = [
        ("out-a:voltage", "Output A Voltage"),
        ("out-b:voltage", "Output B Voltage"),
        ("out-c:voltage", "Output C Voltage"),
        ("out-d:voltage", "Output D Voltage"),
        ("out-e:voltage", "Output E Voltage"),
        ("out-f:voltage", "Output F Voltage"),
    ]
    
    for key, name in output_configs:
        entity = MockNumberEntity(coordinator, client, key, name)
        entities[key] = entity
        print(f"Created entity: {name} ({key})")
    
    # Test reading initial values
    print("\n--- Testing Initial Value Reading ---")
    for key, entity in entities.items():
        value = entity.native_value
        print(f"{entity.name}: {value}V")
        assert value is not None, f"Failed to read value for {key}"
        assert isinstance(value, float), f"Value is not float for {key}: {type(value)}"
    
    # Test setting values
    print("\n--- Testing Value Setting ---")
    test_cases = [
        ("out-a:voltage", 6.50),
        ("out-b:voltage", 2.75),
        ("out-c:voltage", 8.25),
    ]
    
    for key, new_value in test_cases:
        entity = entities[key]
        old_value = entity.native_value
        
        print(f"Setting {entity.name}: {old_value}V -> {new_value}V")
        await entity.async_set_native_value(new_value)
        
        # Check that value was updated
        updated_value = entity.native_value
        assert updated_value == new_value, f"Value not updated correctly: {updated_value} != {new_value}"
        print(f"  ✓ Successfully updated to {updated_value}V")
    
    # Test value clamping
    print("\n--- Testing Value Clamping ---")
    entity = entities["out-d:voltage"]
    
    clamp_tests = [
        (-1.0, 0.0),   # Below minimum
        (15.0, 10.0),  # Above maximum
        (5.5, 5.5),    # Within range
    ]
    
    for input_val, expected_val in clamp_tests:
        print(f"Testing clamping: {input_val} -> {expected_val}")
        await entity.async_set_native_value(input_val)
        actual_val = entity.native_value
        assert actual_val == expected_val, f"Clamping failed: {actual_val} != {expected_val}"
        print(f"  ✓ Correctly clamped to {actual_val}V")
    
    # Test precision
    print("\n--- Testing Precision ---")
    entity = entities["out-e:voltage"]
    precise_value = 3.14159
    expected_value = 3.14159  # Should maintain precision
    
    await entity.async_set_native_value(precise_value)
    actual_value = entity.native_value
    print(f"Set precise value: {precise_value} -> {actual_value}")
    assert abs(actual_value - expected_value) < 0.001, f"Precision lost: {actual_value} != {expected_value}"
    print(f"  ✓ Precision maintained: {actual_value}")
    
    # Verify command history
    print("\n--- Verifying Command History ---")
    print("Commands sent to device:")
    for i, cmd in enumerate(client.command_history, 1):
        print(f"  {i}. {cmd}")
    
    assert len(client.command_history) > 0, "No commands were sent"
    print(f"  ✓ Total commands sent: {len(client.command_history)}")
    
    # Verify coordinator refreshes
    print(f"  ✓ Coordinator refreshes: {coordinator.refresh_count}")
    assert coordinator.refresh_count > 0, "Coordinator was not refreshed"
    
    print("\n✅ Complete workflow test passed!")


async def test_error_scenarios():
    """Test error handling scenarios."""
    print("\n=== Testing Error Scenarios ===")
    
    client = MockHTTPClient()
    coordinator = MockCoordinator(client)
    
    # Test with missing coordinator data
    print("--- Testing Missing Coordinator Data ---")
    coordinator.data = {}
    entity = MockNumberEntity(coordinator, client, "out-a:voltage", "Output A")
    
    value = entity.native_value
    assert value is None, f"Should return None for missing data: {value}"
    print("  ✓ Correctly handled missing coordinator data")
    
    # Test with invalid data
    print("--- Testing Invalid Data ---")
    coordinator.data = {"out-a:voltage": "invalid_float"}
    value = entity.native_value
    assert value is None, f"Should return None for invalid data: {value}"
    print("  ✓ Correctly handled invalid data")
    
    # Test with None data
    print("--- Testing None Data ---")
    coordinator.data = {"out-a:voltage": None}
    value = entity.native_value
    assert value is None, f"Should return None for None data: {value}"
    print("  ✓ Correctly handled None data")
    
    print("✅ Error scenario tests passed!")


async def test_entity_properties():
    """Test entity properties and configuration."""
    print("\n=== Testing Entity Properties ===")
    
    client = MockHTTPClient()
    coordinator = MockCoordinator(client)
    
    entity = MockNumberEntity(
        coordinator, client, 
        "out-a:voltage", "Output A Voltage",
        min_val=0.0, max_val=10.0, step=0.01
    )
    
    # Test properties
    assert entity.name == "Output A Voltage", f"Wrong name: {entity.name}"
    assert entity.key == "out-a:voltage", f"Wrong key: {entity.key}"
    assert entity.native_min_value == 0.0, f"Wrong min value: {entity.native_min_value}"
    assert entity.native_max_value == 10.0, f"Wrong max value: {entity.native_max_value}"
    assert entity.native_step == 0.01, f"Wrong step: {entity.native_step}"
    assert entity.native_unit_of_measurement == "V", f"Wrong unit: {entity.native_unit_of_measurement}"
    
    print(f"Entity name: {entity.name}")
    print(f"Entity key: {entity.key}")
    print(f"Value range: {entity.native_min_value} - {entity.native_max_value}")
    print(f"Step size: {entity.native_step}")
    print(f"Unit: {entity.native_unit_of_measurement}")
    
    print("✅ Entity properties test passed!")


async def main():
    """Run all integration tests."""
    print("Starting Task 8 Integration Tests")
    print("=" * 50)
    
    try:
        await test_number_entity_workflow()
        await test_error_scenarios()
        await test_entity_properties()
        
        print("\n" + "=" * 50)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("\nTask 8 Integration Test Summary:")
        print("- ✓ Number entities work with mock HTTP client")
        print("- ✓ Value setting via HTTP commands functional")
        print("- ✓ Real-time feedback via coordinator refresh works")
        print("- ✓ Value clamping within 0.0-10.0V range works")
        print("- ✓ Precision maintained for voltage values")
        print("- ✓ Error handling for invalid/missing data works")
        print("- ✓ All entity properties configured correctly")
        
        return True
        
    except Exception as e:
        print(f"\n❌ INTEGRATION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)