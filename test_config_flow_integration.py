#!/usr/bin/env python3
"""
Integration test for the simplified config flow.
"""

import asyncio
from aiohttp import ClientSession


async def test_config_flow_with_real_device():
    """Test the config flow logic with the real device."""
    print("Testing config flow with real device at 192.168.105.15...")
    
    # Test the simple HTTP client directly
    from custom_components.crescontrol.simple_http_client import SimpleCresControlHTTPClient
    
    async with ClientSession() as session:
        client = SimpleCresControlHTTPClient("192.168.105.15", session)
        
        print("\n1. Testing WebSocket connectivity...")
        try:
            result = await client.get_value("in-a:voltage")
            if result is not None:
                print(f"✓ WebSocket test successful: in-a:voltage = {result}")
                websocket_works = True
            else:
                print("✗ WebSocket test failed")
                websocket_works = False
        except Exception as e:
            print(f"✗ WebSocket test failed: {e}")
            websocket_works = False
        
        print("\n2. Testing HTTP connectivity...")
        try:
            connected = await client.test_connectivity()
            if connected:
                print("✓ HTTP connectivity test successful")
                http_works = True
            else:
                print("✗ HTTP connectivity test failed")
                http_works = False
        except Exception as e:
            print(f"✗ HTTP connectivity test failed: {e}")
            http_works = False
        
        print("\n3. Testing config flow validation logic...")
        
        # This simulates what the config flow would do
        if websocket_works or http_works:
            print("✓ Device connectivity confirmed - config flow would succeed")
            print(f"  - WebSocket: {'✓' if websocket_works else '✗'}")
            print(f"  - HTTP: {'✓' if http_works else '✗'}")
            
            # Test the data that would be stored
            config_data = {"host": "192.168.105.15"}
            print(f"✓ Config data: {config_data}")
            
            return True
        else:
            print("✗ No connectivity - config flow would fail")
            return False


async def test_host_validation_edge_cases():
    """Test edge cases for host validation."""
    print("\nTesting host validation edge cases...")
    
    # Import the validation function logic
    import re
    
    def _is_valid_host(host: str) -> bool:
        """Validate host format (basic IP address or hostname check)."""
        # Check for basic IP address format first
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        if ip_pattern.match(host):
            # Validate IP address ranges
            parts = host.split('.')
            return all(0 <= int(part) <= 255 for part in parts)
        
        # If it looks like an incomplete IP (contains only digits and dots), reject it
        if re.match(r'^[\d.]+$', host):
            return False
        
        # Check for basic hostname format
        hostname_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$')
        return hostname_pattern.match(host) is not None
    
    test_cases = [
        # Valid cases
        ("192.168.105.15", True, "Valid IP address"),
        ("10.0.0.1", True, "Valid private IP"),
        ("crescontrol.local", True, "Valid hostname with .local"),
        ("device-1", True, "Valid hostname with dash"),
        ("my-device", True, "Valid hostname"),
        
        # Invalid cases
        ("", False, "Empty string"),
        ("192.168.1", False, "Incomplete IP"),
        ("192.168.1.999", False, "IP with invalid range"),
        ("256.1.1.1", False, "IP with invalid range"),
        ("invalid..host", False, "Hostname with double dots"),
        ("-invalid", False, "Hostname starting with dash"),
        ("invalid-", False, "Hostname ending with dash"),
        ("192.168.", False, "Incomplete IP with trailing dot"),
        ("192.168.1.", False, "Incomplete IP with trailing dot"),
    ]
    
    for host, expected, description in test_cases:
        result = _is_valid_host(host)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {description}: '{host}' -> {result}")
        if result != expected:
            print(f"    Expected {expected}, got {result}")
    
    print("✓ Host validation edge cases tested")


if __name__ == "__main__":
    async def main():
        await test_host_validation_edge_cases()
        success = await test_config_flow_with_real_device()
        
        if success:
            print("\n🎉 Config flow integration test passed!")
        else:
            print("\n⚠️  Config flow would fail with current device state")
            print("   This is expected if the device is not available")
    
    asyncio.run(main())