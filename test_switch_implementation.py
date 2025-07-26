#!/usr/bin/env python3
"""
Test switch implementation for task 7.
"""

def test_switch_definitions():
    """Test that switch definitions are properly structured."""
    
    # Read the switch file directly
    with open('custom_components/crescontrol/switch.py', 'r') as f:
        content = f.read()
    
    # Check that CORE_SWITCHES is defined
    assert 'CORE_SWITCHES = [' in content, "CORE_SWITCHES not found"
    
    # Check for required switch keys (only working parameters)
    required_switches = [
        "fan:enabled",
        "out-a:enabled",
        "out-b:enabled", 
        "out-c:enabled",
        "out-d:enabled"
    ]
    
    for switch_key in required_switches:
        assert f'"{switch_key}"' in content, f"Switch key '{switch_key}' not found in switch.py"
    
    print("✓ All required switch definitions found")

def test_switch_structure():
    """Test that switches have proper structure."""
    
    with open('custom_components/crescontrol/switch.py', 'r') as f:
        content = f.read()
    
    # Check that each switch has required fields
    required_fields = ['key', 'name', 'icon']
    for field in required_fields:
        assert f'"{field}":' in content, f"Required field '{field}' not found in switch definitions"
    
    print("✓ Switch structure is correct")

if __name__ == "__main__":
    test_switch_definitions()
    test_switch_structure()
    print("All switch tests passed!")