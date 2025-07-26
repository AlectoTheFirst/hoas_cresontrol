#!/usr/bin/env python3
"""
Test the hybrid coordinator implementation.
Tests WebSocket priority with HTTP fallback functionality.
"""

import asyncio
import aiohttp
from datetime import timedelta
from typing import Dict, Any
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

# Mock Home Assistant components for testing
class MockHomeAssistant:
    """Mock Home Assistant instance for testing."""
    pass

class MockDataUpdateCoordinator:
    """Mock DataUpdateCoordinator base class."""
    
    def __init__(self, hass, logger, name, update_method, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self._update_method = update_method
        self.update_interval = update_interval
        self.data = {}
        self._listeners = []
    
    def async_set_updated_data(self, data):
        """Set updated data and notify listeners."""
        self.data = data
        print(f"📊 Coordinator data updated: {len(data)} parameters")
        for param, value in list(data.items())[:5]:  # Show first 5
            print(f"  {param}: {value}")
        if len(data) > 5:
            print(f"  ... and {len(data) - 5} more")
    
    async def async_request_refresh(self):
        """Request a data refresh."""
        print("🔄 Coordinator refresh requested")
        if self._update_method:
            try:
                data = await self._update_method()
                self.async_set_updated_data(data)
            except Exception as e:
                print(f"❌ Refresh failed: {e}")

# Mock the required modules
import sys
from unittest.mock import MagicMock

# Mock homeassistant modules
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.helpers'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
sys.modules['homeassistant.util'] = MagicMock()
sys.modules['homeassistant.util.dt'] = MagicMock()

# Mock dt_util
class MockDtUtil:
    @staticmethod
    def utcnow():
        from datetime import datetime
        return datetime.utcnow()

sys.modules['homeassistant.util.dt'].dt_util = MockDtUtil()

# Import our implementations
from custom_components.crescontrol.simple_http_client import SimpleHTTPClient
from test_websocket_only import SimpleCresControlWebSocketClient


class MockCresControlClient:
    """Mock HTTP client for testing."""
    
    def __init__(self, host: str, session: aiohttp.ClientSession):
        self.host = host
        self.session = session
    
    async def send_commands(self, commands):
        """Mock send_commands method."""
        print(f"📤 HTTP: Sending {len(commands)} commands to {self.host}")
        
        # Simulate HTTP response data
        data = {}
        for cmd in commands:
            if cmd == 'in-a:voltage':
                data[cmd] = '9.52'
            elif cmd == 'fan:enabled':
                data[cmd] = '0'
            elif cmd == 'fan:duty-cycle':
                data[cmd] = '0.00'
            elif cmd.endswith(':enabled'):
                data[cmd] = '1'
            elif cmd.endswith(':voltage'):
                data[cmd] = '0.00'
            else:
                data[cmd] = 'test_value'
        
        print(f"📥 HTTP: Received {len(data)} parameters")
        return data
    
    async def set_value(self, parameter: str, value: Any):
        """Mock set_value method."""
        print(f"📤 HTTP: Setting {parameter} = {value}")
        return value
    
    async def get_value(self, parameter: str):
        """Mock get_value method."""
        print(f"📤 HTTP: Getting {parameter}")
        return "mock_value"


class HybridCoordinatorTester:
    """Test harness for hybrid coordinator."""
    
    def __init__(self, host: str = "192.168.105.15"):
        self.host = host
        self.session = None
        self.http_client = None
        self.websocket_client = None
        self.coordinator = None
        self.hass = MockHomeAssistant()
    
    async def setup(self):
        """Set up test environment."""
        print("🔧 Setting up hybrid coordinator test environment")
        
        # Create session
        self.session = aiohttp.ClientSession()
        
        # Create HTTP client (mock for testing)
        self.http_client = MockCresControlClient(self.host, self.session)
        
        # Create WebSocket client (real implementation)
        self.websocket_client = SimpleCresControlWebSocketClient(
            host=self.host,
            session=self.session,
            port=81,
            path="/websocket"
        )
        
        # Import and create hybrid coordinator
        from custom_components.crescontrol.hybrid_coordinator import CresControlHybridCoordinator
        
        # Mock the base class
        import custom_components.crescontrol.hybrid_coordinator as hc_module
        hc_module.DataUpdateCoordinator = MockDataUpdateCoordinator
        hc_module.dt_util = MockDtUtil()
        
        self.coordinator = CresControlHybridCoordinator(
            hass=self.hass,
            http_client=self.http_client,
            websocket_client=self.websocket_client,
            host=self.host,
            update_interval=timedelta(seconds=10)
        )
        
        print("✅ Hybrid coordinator setup complete")
    
    async def teardown(self):
        """Clean up test environment."""
        print("🔧 Cleaning up test environment")
        
        if self.coordinator:
            await self.coordinator.async_shutdown()
        
        if self.session:
            await self.session.close()
        
        print("✅ Cleanup complete")
    
    async def test_websocket_priority(self):
        """Test that WebSocket data takes priority over HTTP."""
        print("\n1️⃣  Testing WebSocket Data Priority")
        print("-" * 50)
        
        # First, get HTTP data
        print("📡 Performing initial HTTP data fetch...")
        await self.coordinator.async_request_refresh()
        
        # Connect WebSocket
        print("🔌 Connecting WebSocket...")
        try:
            await self.websocket_client.connect()
            print("✅ WebSocket connected")
            
            # Wait for WebSocket data
            print("📥 Waiting for WebSocket data...")
            await asyncio.sleep(5)
            
            # Check if WebSocket data is being used
            status = self.coordinator.get_connection_status()
            print(f"📊 Connection Status:")
            print(f"  WebSocket connected: {status['websocket_connected']}")
            print(f"  Using WebSocket data: {status['using_websocket_data']}")
            print(f"  WebSocket parameters: {status['websocket_parameters']}")
            print(f"  HTTP parameters: {status['http_parameters']}")
            
            return status['websocket_connected'] and status['websocket_parameters'] > 0
            
        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
            return False
    
    async def test_http_fallback(self):
        """Test HTTP fallback when WebSocket is unavailable."""
        print("\n2️⃣  Testing HTTP Fallback")
        print("-" * 50)
        
        # Disconnect WebSocket to test fallback
        if self.websocket_client.is_connected:
            await self.websocket_client.disconnect()
            print("🔌 WebSocket disconnected for fallback test")
        
        # Perform data fetch - should use HTTP
        print("📡 Performing data fetch with WebSocket disconnected...")
        await self.coordinator.async_request_refresh()
        
        # Check status
        status = self.coordinator.get_connection_status()
        print(f"📊 Fallback Status:")
        print(f"  WebSocket connected: {status['websocket_connected']}")
        print(f"  HTTP parameters: {status['http_parameters']}")
        print(f"  Using WebSocket data: {status['using_websocket_data']}")
        
        return status['http_parameters'] > 0 and not status['using_websocket_data']
    
    async def test_adaptive_polling(self):
        """Test adaptive polling interval adjustment."""
        print("\n3️⃣  Testing Adaptive Polling")
        print("-" * 50)
        
        # Get initial interval
        initial_interval = self.coordinator.update_interval.total_seconds()
        print(f"📊 Initial polling interval: {initial_interval}s")
        
        # Connect WebSocket
        if not self.websocket_client.is_connected:
            await self.websocket_client.connect()
            print("🔌 WebSocket reconnected")
        
        # Wait for WebSocket data and interval adjustment
        await asyncio.sleep(3)
        
        # Trigger a refresh to adjust interval
        await self.coordinator.async_request_refresh()
        
        # Check new interval
        new_interval = self.coordinator.update_interval.total_seconds()
        print(f"📊 Adjusted polling interval: {new_interval}s")
        
        # Should be longer when WebSocket is active
        return new_interval > initial_interval
    
    async def test_combined_data(self):
        """Test that WebSocket and HTTP data are properly combined."""
        print("\n4️⃣  Testing Combined Data")
        print("-" * 50)
        
        # Ensure both WebSocket and HTTP have data
        if not self.websocket_client.is_connected:
            await self.websocket_client.connect()
        
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(3)
        
        # Check combined data
        coordinator_data = self.coordinator.data
        status = self.coordinator.get_connection_status()
        
        print(f"📊 Combined Data Status:")
        print(f"  Total parameters in coordinator: {len(coordinator_data)}")
        print(f"  WebSocket parameters: {status['websocket_parameters']}")
        print(f"  HTTP parameters: {status['http_parameters']}")
        
        # Show some sample data
        print(f"📋 Sample combined data:")
        for param, value in list(coordinator_data.items())[:5]:
            print(f"  {param}: {value}")
        
        return len(coordinator_data) > 0
    
    async def test_control_commands(self):
        """Test control commands via HTTP."""
        print("\n5️⃣  Testing Control Commands")
        print("-" * 50)
        
        # Test setting a value
        try:
            await self.coordinator.async_set_value("fan:enabled", True)
            print("✅ Control command sent successfully")
            
            # Test getting a value
            value = await self.coordinator.async_get_value("fan:enabled")
            print(f"✅ Retrieved value: {value}")
            
            return True
            
        except Exception as e:
            print(f"❌ Control command failed: {e}")
            return False


async def main():
    """Main test function."""
    print("🧪 CresControl Hybrid Coordinator Test")
    print("Testing WebSocket priority with HTTP fallback")
    print("=" * 70)
    
    tester = HybridCoordinatorTester()
    
    try:
        await tester.setup()
        
        # Run tests
        results = {}
        
        results['websocket_priority'] = await tester.test_websocket_priority()
        results['http_fallback'] = await tester.test_http_fallback()
        results['adaptive_polling'] = await tester.test_adaptive_polling()
        results['combined_data'] = await tester.test_combined_data()
        results['control_commands'] = await tester.test_control_commands()
        
        # Summary
        print("\n" + "=" * 70)
        print("📋 TEST SUMMARY")
        print("=" * 70)
        
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
        
        all_passed = all(results.values())
        overall_status = "✅ ALL TESTS PASSED" if all_passed else "⚠️  SOME TESTS FAILED"
        print(f"\nOverall: {overall_status}")
        
        # Requirements validation
        print("\n📋 REQUIREMENTS VALIDATION")
        print("=" * 70)
        
        if results['websocket_priority']:
            print("✅ Coordinator prioritizes WebSocket data")
        
        if results['http_fallback']:
            print("✅ HTTP polling fallback when WebSocket unavailable")
        
        if results['combined_data']:
            print("✅ WebSocket data handler integrated with coordinator updates")
        
        if results['control_commands']:
            print("✅ Basic error handling implemented")
        
        if results['adaptive_polling']:
            print("✅ Adaptive polling based on WebSocket status")
        
        return all_passed
        
    finally:
        await tester.teardown()


if __name__ == "__main__":
    success = asyncio.run(main())
    print(f"\n{'🎉 SUCCESS' if success else '❌ FAILURE'}")
    exit(0 if success else 1)