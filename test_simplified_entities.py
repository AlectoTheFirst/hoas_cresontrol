#!/usr/bin/env python3
"""
Test script to verify simplified entity implementations.
"""

import sys
import os

# Add the custom_components directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

def test_entity_definitions():
    """Test that entity definitions are properly structured."""
    
    # Test sensor definitions
    from crescontrol.sensor import CORE_SENSORS
    print(f"Core sensors: {len(CORE_SENSORS)}")
    for sensor in CORE_SENSORS:
        print(f"  - {sensor['key']}: {sensor['name']}")
        assert 'key' in sensor
        assert 'name' in sensor
        assert 'unit' in sensor
        assert 'device_class' in sensor
        assert 'icon' in sensor
    
    # Test switch definitions
    from crescontrol.switch import CORE_SWITCHES
    print(f"Core switches: {len(CORE_SWITCHES)}")
    for switch in CORE_SWITCHES:
        print(f"  - {switch['key']}: {switch['name']}")
        assert 'key' in switch
        assert 'name' in switch
        assert 'icon' in switch
    
    # Test number definitions
    from crescontrol.number import CORE_NUMBERS
    print(f"Core numbers: {len(CORE_NUMBERS)}")
    for number in CORE_NUMBERS:
        print(f"  - {number['key']}: {number['name']}")
        assert 'key' in number
        assert 'name' in number
        assert 'icon' in number
        assert 'min_value' in number
        assert 'max_value' in number
        assert 'step' in number
    
    print("✓ All entity definitions are valid")

def test_entity_keys():
    """Test that entity keys follow expected patterns."""
    
    from crescontrol.sensor import CORE_SENSORS
    from crescontrol.switch import CORE_SWITCHES
    from crescontrol.number import CORE_NUMBERS
    
    # Expected sensor keys
    expected_sensors = {"in-a:voltage", "in-b:voltage", "fan:rpm"}
    sensor_keys = {s['key'] for s in CORE_SENSORS}
    assert sensor_keys == expected_sensors, f"Sensor keys mismatch: {sensor_keys} != {expected_sensors}"
    
    # Expected switch keys
    expected_switches = {
        "fan:enabled", "switch-12v:enabled", "switch-24v-a:enabled", "switch-24v-b:enabled",
        "out-a:enabled", "out-b:enabled", "out-c:enabled", "out-d:enabled", "out-e:enabled", "out-f:enabled"
    }
    switch_keys = {s['key'] for s in CORE_SWITCHES}
    assert switch_keys == expected_switches, f"Switch keys mismatch: {switch_keys} != {expected_switches}"
    
    # Expected number keys
    expected_numbers = {
        "out-a:voltage", "out-b:voltage", "out-c:voltage", "out-d:voltage", "out-e:voltage", "out-f:voltage"
    }
    number_keys = {n['key'] for n in CORE_NUMBERS}
    assert number_keys == expected_numbers, f"Number keys mismatch: {number_keys} != {expected_numbers}"
    
    print("✓ All entity keys match expected patterns")

if __name__ == "__main__":
    print("Testing simplified entity implementations...")
    test_entity_definitions()
    test_entity_keys()
    print("✓ All tests passed!")