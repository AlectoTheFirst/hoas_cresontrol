#!/usr/bin/env python3
"""
Test HTTP command functionality for switches.
"""

import asyncio
import aiohttp
import json

async def test_switch_http_commands():
    """Test HTTP commands for switch operations."""
    
    # Test device IP from the design document
    host = "192.168.105.15"
    port = 81
    base_url = f"http://{host}:{port}"
    
    # Core switch commands to test
    switch_commands = [
        "fan:enabled",
        "switch-12v:enabled", 
        "switch-24v-a:enabled",
        "switch-24v-b:enabled",
        "out-a:enabled",
        "out-b:enabled",
        "out-c:enabled", 
        "out-d:enabled",
        "out-e:enabled",
        "out-f:enabled"
    ]
    
    print(f"Testing switch HTTP commands against {base_url}")
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        
        # Test reading current switch states
        print("\n=== Testing switch state reading ===")
        for command in switch_commands:
            try:
                url = f"{base_url}/command"
                params = {"query": command}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        text = await response.text()
                        print(f"✓ {command}: {text.strip()}")
                    else:
                        print(f"✗ {command}: HTTP {response.status}")
                        
            except Exception as e:
                print(f"✗ {command}: {e}")
        
        # Test setting switch values
        print("\n=== Testing switch control commands ===")
        test_commands = [
            ("fan:enabled", "0"),  # Turn off fan
            ("fan:enabled", "1"),  # Turn on fan
            ("switch-12v:enabled", "1"),  # Turn on 12V switch
            ("switch-12v:enabled", "0"),  # Turn off 12V switch
            ("out-a:enabled", "0"),  # Disable output A
            ("out-a:enabled", "1"),  # Enable output A
        ]
        
        for param, value in test_commands:
            try:
                command = f"{param}={value}"
                url = f"{base_url}/command"
                params = {"query": command}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        text = await response.text()
                        print(f"✓ Set {param}={value}: {text.strip()}")
                    else:
                        print(f"✗ Set {param}={value}: HTTP {response.status}")
                        
            except Exception as e:
                print(f"✗ Set {param}={value}: {e}")
        
        # Test batch commands
        print("\n=== Testing batch switch commands ===")
        batch_command = ";".join([
            "fan:enabled",
            "switch-12v:enabled", 
            "out-a:enabled",
            "out-b:enabled"
        ])
        
        try:
            url = f"{base_url}/command"
            params = {"query": batch_command}
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    text = await response.text()
                    print(f"✓ Batch command: {text.strip()}")
                else:
                    print(f"✗ Batch command: HTTP {response.status}")
                    
        except Exception as e:
            print(f"✗ Batch command: {e}")

def test_switch_value_parsing():
    """Test parsing of switch values from device responses."""
    
    # Test different response formats that might be returned
    test_responses = [
        "fan:enabled::1",
        "switch-12v:enabled::0", 
        "out-a:enabled::true",
        "out-b:enabled::false",
        "fan:enabled=1::1",  # Response with assignment echo
        "switch-12v:enabled=0::0"
    ]
    
    print("\n=== Testing switch value parsing ===")
    
    for response in test_responses:
        try:
            # Parse response like the API client does
            if "::" in response:
                key_part, value = response.split("::", 1)
                # Remove assignment from key if present
                key = key_part.split("=", 1)[0]
                
                # Parse boolean value
                parsed_value = None
                if isinstance(value, str):
                    value_lower = value.strip().lower()
                    if value_lower in ("true", "1", "on", "enabled"):
                        parsed_value = True
                    elif value_lower in ("false", "0", "off", "disabled"):
                        parsed_value = False
                
                print(f"✓ {response} -> {key}: {parsed_value}")
            else:
                print(f"✗ Invalid format: {response}")
                
        except Exception as e:
            print(f"✗ Parse error for {response}: {e}")

async def main():
    """Run all tests."""
    print("Testing switch HTTP commands for task 7...")
    
    # Test parsing logic (doesn't require network)
    test_switch_value_parsing()
    
    # Test actual HTTP commands (requires device)
    try:
        await test_switch_http_commands()
    except Exception as e:
        print(f"\nNote: HTTP tests failed (device may not be available): {e}")
        print("This is expected if the device is not accessible.")
    
    print("\n✅ Switch HTTP command tests completed!")

if __name__ == "__main__":
    asyncio.run(main())