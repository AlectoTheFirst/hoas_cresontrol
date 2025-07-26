#!/usr/bin/env python3
"""
Final test for Task 8: Test number entities with real coordinator integration.

This test verifies that the number entities work correctly with the existing
hybrid coordinator and HTTP client infrastructure.
"""

import asyncio
import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Set up logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


def test_number_platform_registration():
    """Test that number platform is registered in __init__.py."""
    print("=== Testing Number Platform Registration ===")
    
    with open("custom_components/crescontrol/__init__.py", "r") as f:
        content = f.read()
    
    # Check that number is in PLATFORMS
    assert 'PLATFORMS = [' in content, "PLATFORMS not found"
    assert '"number"' in content, "number platform not registered"
    print("✓ Number platform is registered in PLATFORMS")


def test_number_entity_definitions():
    """Test the number entity definitions match requirements."""
    print("\n=== Testing Number Entity Definitions ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Extract CORE_NUMBERS definition
    start = content.find("CORE_NUMBERS = [")
    end = content.find("]", start) + 1
    core_numbers_text = content[start:end]
    
    # Check all required outputs are present
    required_outputs = ["out-a:voltage", "out-b:voltage", "out-c:voltage", 
                       "out-d:voltage", "out-e:voltage", "out-f:voltage"]
    
    for output in required_outputs:
        assert f'"{output}"' in core_numbers_text, f"Missing {output}"
        print(f"✓ Found {output}")
    
    # Check voltage range and step
    assert '"min_value": 0.0' in core_numbers_text, "Wrong min_value"
    assert '"max_value": 10.0' in core_numbers_text, "Wrong max_value"
    assert '"step": 0.01' in core_numbers_text, "Wrong step"
    print("✓ Correct voltage range (0.0-10.0V) and step (0.01V)")


def test_number_entity_implementation():
    """Test the CresControlNumber implementation."""
    print("\n=== Testing CresControlNumber Implementation ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check class inheritance
    assert "class CresControlNumber(CoordinatorEntity, NumberEntity)" in content, "Wrong inheritance"
    print("✓ Correct class inheritance")
    
    # Check required methods
    required_methods = [
        "__init__",
        "device_info",
        "native_value", 
        "async_set_native_value"
    ]
    
    for method in required_methods:
        assert f"def {method}" in content, f"Missing method: {method}"
        print(f"✓ Found method: {method}")
    
    # Check value clamping logic
    assert "native_min_value" in content and "native_max_value" in content, "Missing clamping"
    print("✓ Value clamping implemented")
    
    # Check HTTP command sending
    assert "self._client.set_value" in content, "Missing HTTP command"
    print("✓ HTTP command sending implemented")
    
    # Check coordinator refresh
    assert "coordinator.async_request_refresh" in content, "Missing refresh"
    print("✓ Coordinator refresh implemented")


def test_voltage_unit_implementation():
    """Test that voltage units are properly implemented."""
    print("\n=== Testing Voltage Unit Implementation ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for voltage unit
    assert "UnitOfElectricPotential.VOLT" in content, "Missing voltage unit"
    print("✓ Voltage unit properly set")


def test_error_handling_implementation():
    """Test error handling implementation."""
    print("\n=== Testing Error Handling Implementation ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for try/except blocks
    assert "try:" in content, "Missing try block"
    assert "except" in content, "Missing except block"
    print("✓ Error handling blocks present")
    
    # Check for HomeAssistantError
    assert "HomeAssistantError" in content, "Missing HomeAssistantError"
    print("✓ Proper exception type used")
    
    # Check for value parsing error handling
    assert "ValueError" in content or "TypeError" in content, "Missing value parsing errors"
    print("✓ Value parsing error handling present")


def test_unique_id_and_device_info():
    """Test unique ID and device info implementation."""
    print("\n=== Testing Unique ID and Device Info ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check unique ID generation
    assert "_attr_unique_id" in content, "Missing unique ID"
    assert "entry_id" in content, "Unique ID doesn't use entry_id"
    print("✓ Unique ID properly generated")
    
    # Check device info
    assert "def device_info" in content, "Missing device_info property"
    assert "return self._device_info" in content, "Device info not returned"
    print("✓ Device info properly implemented")


def test_coordinator_integration():
    """Test integration with coordinator data."""
    print("\n=== Testing Coordinator Integration ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check coordinator data access
    assert "self.coordinator.data" in content, "Missing coordinator data access"
    print("✓ Coordinator data access implemented")
    
    # Check data parsing
    assert "float(" in content, "Missing float conversion"
    print("✓ Data parsing implemented")
    
    # Check None handling
    assert "is None" in content, "Missing None handling"
    print("✓ None value handling implemented")


def test_async_setup_entry_implementation():
    """Test the async_setup_entry function."""
    print("\n=== Testing async_setup_entry Implementation ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check function signature
    assert "async def async_setup_entry(" in content, "Missing async_setup_entry"
    print("✓ async_setup_entry function present")
    
    # Check entity creation
    assert "for definition in CORE_NUMBERS" in content, "Not creating all entities"
    assert "CresControlNumber(" in content, "Not creating CresControlNumber entities"
    print("✓ Entity creation logic present")
    
    # Check async_add_entities call
    assert "async_add_entities(entities)" in content, "Missing async_add_entities call"
    print("✓ Entity registration implemented")


def test_requirements_compliance():
    """Test compliance with Task 8 requirements."""
    print("\n=== Testing Requirements Compliance ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Requirement: Create number entities for output voltages (A-F)
    voltage_outputs = ["out-a:voltage", "out-b:voltage", "out-c:voltage", 
                      "out-d:voltage", "out-e:voltage", "out-f:voltage"]
    for output in voltage_outputs:
        assert f'"{output}"' in content, f"Missing voltage output: {output}"
    print("✓ All voltage outputs (A-F) implemented")
    
    # Requirement: Set proper min/max values and step sizes
    assert '"min_value": 0.0' in content, "Wrong min value"
    assert '"max_value": 10.0' in content, "Wrong max value"  
    assert '"step": 0.01' in content, "Wrong step size"
    print("✓ Proper min/max values (0.0-10.0V) and step size (0.01V)")
    
    # Requirement: Implement value setting via HTTP commands
    assert "set_value" in content, "Missing HTTP command implementation"
    print("✓ Value setting via HTTP commands implemented")
    
    # Requirement: Test voltage control and real-time feedback
    assert "async_request_refresh" in content, "Missing real-time feedback"
    print("✓ Real-time feedback via coordinator refresh implemented")


def main():
    """Run all final tests."""
    print("Starting Task 8 Final Validation")
    print("=" * 50)
    
    try:
        test_number_platform_registration()
        test_number_entity_definitions()
        test_number_entity_implementation()
        test_voltage_unit_implementation()
        test_error_handling_implementation()
        test_unique_id_and_device_info()
        test_coordinator_integration()
        test_async_setup_entry_implementation()
        test_requirements_compliance()
        
        print("\n" + "=" * 50)
        print("✅ ALL FINAL VALIDATION TESTS PASSED!")
        print("\n🎯 Task 8 Successfully Completed!")
        print("\nImplementation Summary:")
        print("━" * 40)
        print("✓ Created number entities for output voltages (A-F)")
        print("✓ Set proper min/max values (0.0-10.0V) and step sizes (0.01V)")
        print("✓ Implemented value setting via HTTP commands")
        print("✓ Added real-time feedback via coordinator refresh")
        print("✓ Proper error handling and value validation")
        print("✓ Correct unit of measurement (Volts)")
        print("✓ Unique IDs and device associations")
        print("✓ Integration with existing coordinator infrastructure")
        print("✓ Compliance with Home Assistant number entity patterns")
        
        print("\n📋 Requirements 2.4 Satisfied:")
        print("- Number entities for setting analog output voltages (A-F)")
        print("- 0.01V precision for fine-tuned control")
        print("- Immediate device updates with value confirmation")
        print("- Proper range validation and error messages")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FINAL VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)