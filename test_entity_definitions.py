#!/usr/bin/env python3
"""
Test script to verify entity definitions by parsing the files directly.
"""

import re

def extract_definitions(file_path, definition_name):
    """Extract entity definitions from a Python file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the definition list
    pattern = rf'{definition_name}\s*=\s*\[(.*?)\]'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []
    
    # Count dictionary entries
    dict_content = match.group(1)
    dict_count = dict_content.count('"key":')
    return dict_count

def test_entity_counts():
    """Test that we have the expected number of core entities."""
    
    # Test sensor definitions
    sensor_count = extract_definitions('custom_components/crescontrol/sensor.py', 'CORE_SENSORS')
    print(f"Core sensors: {sensor_count}")
    assert sensor_count == 3, f"Expected 3 core sensors, got {sensor_count}"
    
    # Test switch definitions  
    switch_count = extract_definitions('custom_components/crescontrol/switch.py', 'CORE_SWITCHES')
    print(f"Core switches: {switch_count}")
    assert switch_count == 10, f"Expected 10 core switches, got {switch_count}"
    
    # Test number definitions
    number_count = extract_definitions('custom_components/crescontrol/number.py', 'CORE_NUMBERS')
    print(f"Core numbers: {number_count}")
    assert number_count == 6, f"Expected 6 core numbers, got {number_count}"
    
    print("✓ All entity counts are correct")

def test_entity_keys():
    """Test that entity keys are present in the files."""
    
    # Check sensor keys
    with open('custom_components/crescontrol/sensor.py', 'r') as f:
        sensor_content = f.read()
    
    expected_sensor_keys = ["in-a:voltage", "in-b:voltage", "fan:rpm"]
    for key in expected_sensor_keys:
        assert key in sensor_content, f"Sensor key '{key}' not found"
    
    # Check switch keys
    with open('custom_components/crescontrol/switch.py', 'r') as f:
        switch_content = f.read()
    
    expected_switch_keys = [
        "fan:enabled", "switch-12v:enabled", "switch-24v-a:enabled", "switch-24v-b:enabled",
        "out-a:enabled", "out-b:enabled", "out-c:enabled", "out-d:enabled", "out-e:enabled", "out-f:enabled"
    ]
    for key in expected_switch_keys:
        assert key in switch_content, f"Switch key '{key}' not found"
    
    # Check number keys
    with open('custom_components/crescontrol/number.py', 'r') as f:
        number_content = f.read()
    
    expected_number_keys = [
        "out-a:voltage", "out-b:voltage", "out-c:voltage", "out-d:voltage", "out-e:voltage", "out-f:voltage"
    ]
    for key in expected_number_keys:
        assert key in number_content, f"Number key '{key}' not found"
    
    print("✓ All expected entity keys are present")

def test_simplified_structure():
    """Test that complex features have been removed."""
    
    files_to_check = [
        'custom_components/crescontrol/sensor.py',
        'custom_components/crescontrol/switch.py', 
        'custom_components/crescontrol/number.py',
        'custom_components/crescontrol/fan.py'
    ]
    
    # These should not be present in simplified implementations
    complex_patterns = [
        'SYSTEM_SENSOR_DEFINITIONS',
        'DIAGNOSTIC_SENSOR_DEFINITIONS',
        'STATE_PRESERVATION_DURATION',
        'AVAILABILITY_GRACE_PERIOD',
        '_should_preserve_last_state',
        '_consecutive_failures',
        'health_tracker',
        'grace_period_start'
    ]
    
    for file_path in files_to_check:
        with open(file_path, 'r') as f:
            content = f.read()
        
        for pattern in complex_patterns:
            assert pattern not in content, f"Complex pattern '{pattern}' found in {file_path}"
    
    print("✓ Complex error handling and state preservation removed")

if __name__ == "__main__":
    print("Testing simplified entity implementations...")
    test_entity_counts()
    test_entity_keys()
    test_simplified_structure()
    print("✓ All tests passed!")