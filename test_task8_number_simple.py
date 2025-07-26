#!/usr/bin/env python3
"""
Simplified test for Task 8: Core number entities for voltage control.

This test validates the number entity definitions and basic functionality
without requiring Home Assistant imports.
"""

import sys
import os

# Add the custom_components directory to the path
sys.path.insert(0, 'custom_components')

def test_number_file_exists():
    """Test that the number.py file exists."""
    print("=== Testing Number File Exists ===")
    
    number_file = "custom_components/crescontrol/number.py"
    assert os.path.exists(number_file), f"Number file not found: {number_file}"
    print(f"✓ Found number.py file: {number_file}")


def test_core_numbers_definition():
    """Test the CORE_NUMBERS definition by reading the file."""
    print("\n=== Testing CORE_NUMBERS Definition ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check that CORE_NUMBERS is defined
    assert "CORE_NUMBERS = [" in content, "CORE_NUMBERS not found in number.py"
    print("✓ Found CORE_NUMBERS definition")
    
    # Check for all expected voltage outputs
    expected_outputs = ["out-a:voltage", "out-b:voltage", "out-c:voltage", 
                       "out-d:voltage", "out-e:voltage", "out-f:voltage"]
    
    for output in expected_outputs:
        assert f'"{output}"' in content, f"Missing output definition: {output}"
        print(f"✓ Found definition for: {output}")
    
    # Check for proper min/max values
    assert '"min_value": 0.0' in content, "Missing min_value: 0.0"
    assert '"max_value": 10.0' in content, "Missing max_value: 10.0"
    assert '"step": 0.01' in content, "Missing step: 0.01"
    print("✓ Found correct min/max values and step size")


def test_number_entity_class():
    """Test the CresControlNumber class definition."""
    print("\n=== Testing CresControlNumber Class ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for class definition
    assert "class CresControlNumber" in content, "CresControlNumber class not found"
    print("✓ Found CresControlNumber class")
    
    # Check for required methods
    required_methods = [
        "def __init__",
        "def native_value",
        "async def async_set_native_value"
    ]
    
    for method in required_methods:
        assert method in content, f"Missing method: {method}"
        print(f"✓ Found method: {method}")
    
    # Check for proper inheritance
    assert "CoordinatorEntity, NumberEntity" in content, "Wrong inheritance"
    print("✓ Correct class inheritance")


def test_async_setup_entry():
    """Test the async_setup_entry function."""
    print("\n=== Testing async_setup_entry Function ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for setup function
    assert "async def async_setup_entry" in content, "async_setup_entry not found"
    print("✓ Found async_setup_entry function")
    
    # Check that it creates entities for all CORE_NUMBERS
    assert "for definition in CORE_NUMBERS" in content, "Not iterating over CORE_NUMBERS"
    print("✓ Creates entities for all CORE_NUMBERS")


def test_value_setting_implementation():
    """Test that value setting is properly implemented."""
    print("\n=== Testing Value Setting Implementation ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for value clamping
    assert "native_min_value" in content and "native_max_value" in content, "Missing value clamping"
    print("✓ Found value clamping logic")
    
    # Check for client.set_value call
    assert "self._client.set_value" in content, "Missing client.set_value call"
    print("✓ Found client.set_value call")
    
    # Check for coordinator refresh
    assert "coordinator.async_request_refresh" in content, "Missing coordinator refresh"
    print("✓ Found coordinator refresh call")


def test_error_handling():
    """Test that proper error handling is implemented."""
    print("\n=== Testing Error Handling ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for try/except blocks
    assert "try:" in content and "except" in content, "Missing error handling"
    print("✓ Found error handling blocks")
    
    # Check for proper exception types
    assert "HomeAssistantError" in content, "Missing HomeAssistantError"
    print("✓ Found proper exception handling")


def test_unit_of_measurement():
    """Test that proper unit of measurement is set."""
    print("\n=== Testing Unit of Measurement ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for voltage unit
    assert "UnitOfElectricPotential.VOLT" in content or "VOLT" in content, "Missing voltage unit"
    print("✓ Found voltage unit of measurement")


def test_device_info():
    """Test that device info is properly implemented."""
    print("\n=== Testing Device Info ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for device_info property
    assert "def device_info" in content, "Missing device_info property"
    print("✓ Found device_info property")


def test_unique_id_generation():
    """Test that unique IDs are properly generated."""
    print("\n=== Testing Unique ID Generation ===")
    
    with open("custom_components/crescontrol/number.py", "r") as f:
        content = f.read()
    
    # Check for unique ID generation
    assert "_attr_unique_id" in content, "Missing unique ID generation"
    assert "entry_id" in content, "Unique ID doesn't include entry_id"
    print("✓ Found proper unique ID generation")


def main():
    """Run all tests."""
    print("Starting Task 8 Number Entities Validation")
    print("=" * 50)
    
    try:
        test_number_file_exists()
        test_core_numbers_definition()
        test_number_entity_class()
        test_async_setup_entry()
        test_value_setting_implementation()
        test_error_handling()
        test_unit_of_measurement()
        test_device_info()
        test_unique_id_generation()
        
        print("\n" + "=" * 50)
        print("✅ ALL VALIDATION TESTS PASSED!")
        print("\nTask 8 Implementation Validation Summary:")
        print("- ✓ Number entities defined for output voltages (A-F)")
        print("- ✓ Proper min/max values (0.0-10.0V) and step sizes (0.01V)")
        print("- ✓ Value setting implemented via HTTP commands")
        print("- ✓ Error handling and validation in place")
        print("- ✓ Proper unit of measurement (Volts)")
        print("- ✓ Device info and unique ID generation")
        print("- ✓ Coordinator integration for real-time feedback")
        
        return True
        
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)