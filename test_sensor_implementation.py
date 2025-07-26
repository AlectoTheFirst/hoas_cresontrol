#!/usr/bin/env python3
"""
Test script for sensor implementation.

This script tests the core sensor entities implementation for task 6.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Add the custom_components path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components', 'crescontrol'))

# Mock Home Assistant modules for testing
class MockSensorDeviceClass:
    VOLTAGE = "voltage"

class MockSensorStateClass:
    MEASUREMENT = "measurement"

class MockUnitOfElectricPotential:
    VOLT = "V"

REVOLUTIONS_PER_MINUTE = "rpm"

# Mock the Home Assistant imports
sys.modules['homeassistant.components.sensor'] = type('MockModule', (), {
    'SensorDeviceClass': MockSensorDeviceClass,
    'SensorEntity': object,
    'SensorStateClass': MockSensorStateClass,
})()

sys.modules['homeassistant.const'] = type('MockModule', (), {
    'UnitOfElectricPotential': MockUnitOfElectricPotential,
    'REVOLUTIONS_PER_MINUTE': REVOLUTIONS_PER_MINUTE,
})()

sys.modules['homeassistant.core'] = type('MockModule', (), {
    'HomeAssistant': object,
})()

sys.modules['homeassistant.helpers.update_coordinator'] = type('MockModule', (), {
    'CoordinatorEntity': object,
})()

sys.modules['homeassistant.config_entries'] = type('MockModule', (), {
    'ConfigEntry': object,
})()

# Mock the const module
sys.modules['const'] = type('MockModule', (), {
    'DOMAIN': 'crescontrol',
})()

# Now import the sensor module
import sensor
CORE_SENSORS = sensor.CORE_SENSORS
CresControlSensor = sensor.CresControlSensor

def test_core_sensors():
    """Test the core sensor definitions."""
    print("=== Testing Core Sensor Definitions ===")
    
    expected_sensors = [
        "in-a:voltage",
        "in-b:voltage", 
        "fan:rpm"
    ]
    
    print(f"Expected sensors: {expected_sensors}")
    print(f"Defined sensors: {[s['key'] for s in CORE_SENSORS]}")
    
    # Check that all expected sensors are defined
    defined_keys = [sensor['key'] for sensor in CORE_SENSORS]
    for expected in expected_sensors:
        if expected in defined_keys:
            print(f"✅ {expected} - Found")
        else:
            print(f"❌ {expected} - Missing")
    
    # Check sensor definitions
    for sensor in CORE_SENSORS:
        print(f"\nSensor: {sensor['key']}")
        print(f"  Name: {sensor['name']}")
        print(f"  Unit: {sensor.get('unit', 'None')}")
        print(f"  Device Class: {sensor.get('device_class', 'None')}")
        print(f"  State Class: {sensor.get('state_class', 'None')}")
        print(f"  Icon: {sensor.get('icon', 'None')}")

def test_sensor_value_parsing():
    """Test sensor value parsing logic."""
    print("\n=== Testing Sensor Value Parsing ===")
    
    # Mock coordinator data
    test_data = {
        "in-a:voltage": "9.50",
        "in-b:voltage": "0.00", 
        "fan:rpm": "1200",
        "fan:rpm_error": '{"error": "Fan not connected"}',  # Error response
        "empty_value": "",
        "invalid_value": "not_a_number"
    }
    
    # Mock coordinator
    class MockCoordinator:
        def __init__(self, data):
            self.data = data
            self.config_entry = type('MockEntry', (), {'entry_id': 'test_entry'})()
    
    # Mock device info
    device_info = {
        "identifiers": {("crescontrol", "test_device")},
        "name": "Test CresControl",
        "manufacturer": "CresControl",
        "model": "Test Model"
    }
    
    # Test each sensor type
    for sensor_def in CORE_SENSORS:
        print(f"\nTesting sensor: {sensor_def['key']}")
        
        coordinator = MockCoordinator(test_data)
        sensor = CresControlSensor(coordinator, device_info, sensor_def)
        
        # Test normal value parsing
        value = sensor.native_value
        print(f"  Parsed value: {value} (type: {type(value).__name__})")
        
        # Test with error response
        if sensor_def['key'] == 'fan:rpm':
            coordinator.data = {"fan:rpm": '{"error": "Fan not connected"}'}
            sensor = CresControlSensor(coordinator, device_info, sensor_def)
            error_value = sensor.native_value
            print(f"  Error response value: {error_value}")
        
        # Test with empty data
        coordinator.data = {}
        sensor = CresControlSensor(coordinator, device_info, sensor_def)
        empty_value = sensor.native_value
        print(f"  Empty data value: {empty_value}")

def test_websocket_integration():
    """Test WebSocket data integration."""
    print("\n=== Testing WebSocket Integration ===")
    
    # Simulate WebSocket data updates
    websocket_data = {
        "in-a:voltage": "8.75",
        "fan:rpm": "1500"
    }
    
    print("WebSocket data format (parameter::value):")
    for param, value in websocket_data.items():
        websocket_message = f"{param}::{value}"
        print(f"  {websocket_message}")
    
    print("\nParsed data would be:")
    for param, value in websocket_data.items():
        print(f"  {param} = {value}")

if __name__ == "__main__":
    print("CresControl Sensor Implementation Test")
    print("=" * 50)
    
    test_core_sensors()
    test_sensor_value_parsing()
    test_websocket_integration()
    
    print("\n" + "=" * 50)
    print("Test completed!")