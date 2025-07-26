#!/usr/bin/env python3
"""
Test switch operations for task 7.
"""

import asyncio
import sys
import os

# Add the custom_components directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

class MockCoordinator:
    """Mock coordinator for testing."""
    def __init__(self):
        self.data = {
            "fan:enabled": "1",
            "switch-12v:enabled": "0", 
            "switch-24v-a:enabled": "1",
            "switch-24v-b:enabled": "0",
            "out-a:enabled": "1",
            "out-b:enabled": "0",
            "out-c:enabled": "1", 
            "out-d:enabled": "0",
            "out-e:enabled": "1",
            "out-f:enabled": "0"
        }
        self.config_entry = MockConfigEntry()
    
    async def async_request_refresh(self):
        """Mock refresh method."""
        pass

class MockConfigEntry:
    """Mock config entry for testing."""
    def __init__(self):
        self.entry_id = "test_entry"

class MockClient:
    """Mock API client for testing."""
    def __init__(self):
        self.commands_sent = []
        self.values_set = []
    
    async def set_value(self, key, value):
        """Mock set_value method."""
        self.values_set.append((key, value))
        print(f"Mock: Setting {key} = {value}")
        return value

def test_switch_state_parsing():
    """Test switch state parsing logic."""
    
    # Import the switch module
    from crescontrol.switch import CresControlSwitch
    
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"name": "Test Device"}
    
    # Test different switch definitions
    test_switches = [
        {"key": "fan:enabled", "name": "Fan", "icon": "mdi:fan"},
        {"key": "switch-12v:enabled", "name": "12V Switch", "icon": "mdi:electric-switch"},
        {"key": "out-a:enabled", "name": "Output A Enabled", "icon": "mdi:tune"}
    ]
    
    for switch_def in test_switches:
        switch = CresControlSwitch(coordinator, client, device_info, switch_def)
        
        # Test state parsing
        state = switch.is_on
        print(f"Switch {switch_def['key']}: state = {state}")
        
        # Verify the state is parsed correctly
        expected_state = coordinator.data[switch_def['key']] == "1"
        assert state == expected_state, f"State mismatch for {switch_def['key']}: got {state}, expected {expected_state}"
    
    print("✓ Switch state parsing works correctly")

async def test_switch_operations():
    """Test switch turn on/off operations."""
    
    from crescontrol.switch import CresControlSwitch
    
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"name": "Test Device"}
    
    # Test fan switch
    fan_switch_def = {"key": "fan:enabled", "name": "Fan", "icon": "mdi:fan"}
    fan_switch = CresControlSwitch(coordinator, client, device_info, fan_switch_def)
    
    # Test turning on
    await fan_switch.async_turn_on()
    assert ("fan:enabled", True) in client.values_set, "Turn on command not sent"
    
    # Test turning off  
    await fan_switch.async_turn_off()
    assert ("fan:enabled", False) in client.values_set, "Turn off command not sent"
    
    print("✓ Switch operations work correctly")

async def test_all_core_switches():
    """Test that all core switches can be created and operated."""
    
    from crescontrol.switch import CORE_SWITCHES, CresControlSwitch
    
    coordinator = MockCoordinator()
    client = MockClient()
    device_info = {"name": "Test Device"}
    
    switches = []
    for switch_def in CORE_SWITCHES:
        switch = CresControlSwitch(coordinator, client, device_info, switch_def)
        switches.append(switch)
        
        # Test that switch has proper attributes
        assert hasattr(switch, '_key'), f"Switch {switch_def['key']} missing _key attribute"
        assert hasattr(switch, '_attr_name'), f"Switch {switch_def['key']} missing _attr_name attribute"
        assert hasattr(switch, '_attr_unique_id'), f"Switch {switch_def['key']} missing _attr_unique_id attribute"
        
        # Test state reading
        state = switch.is_on
        print(f"Switch {switch_def['key']}: {switch._attr_name} = {state}")
    
    print(f"✓ All {len(CORE_SWITCHES)} core switches created successfully")
    
    # Test operations on a few switches
    for switch in switches[:3]:  # Test first 3 switches
        await switch.async_turn_on()
        await switch.async_turn_off()
    
    print("✓ Switch operations tested successfully")

async def main():
    """Run all tests."""
    print("Testing switch implementation for task 7...")
    
    test_switch_state_parsing()
    await test_switch_operations()
    await test_all_core_switches()
    
    print("\n✅ All switch tests passed!")

if __name__ == "__main__":
    asyncio.run(main())