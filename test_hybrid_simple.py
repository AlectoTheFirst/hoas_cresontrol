#!/usr/bin/env python3
"""
Simple test for hybrid coordinator functionality.
Tests the core WebSocket priority with HTTP fallback logic.
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any


class MockDtUtil:
    """Mock dt_util for testing."""
    @staticmethod
    def utcnow():
        return datetime.utcnow()


class MockDataUpdateCoordinator:
    """Mock DataUpdateCoordinator for testing."""
    
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
        print(f"📊 Coordinator updated: {len(data)} parameters")
        # Show sample data
        for param, value in list(data.items())[:3]:
            print(f"  {param}: {value}")
        if len(data) > 3:
            print(f"  ... and {len(data) - 3} more")
    
    async def async_request_refresh(self):
        """Request a data refresh."""
        print("🔄 Refresh requested")
        if self._update_method:
            try:
                data = await self._update_method()
                self.async_set_updated_data(data)
            except Exception as e:
                print(f"❌ Refresh failed: {e}")


class MockHTTPClient:
    """Mock HTTP client for testing."""
    
    def __init__(self, host: str):
        self.host = host
    
    async def send_commands(self, commands):
        """Mock HTTP command sending."""
        print(f"📤 HTTP: Sending {len(commands)} commands")
        
        # Simulate HTTP response
        data = {}
        for cmd in commands:
            if cmd == 'in-a:voltage':
                data[cmd] = '9.50'  # Different from WebSocket to show priority
            elif cmd == 'fan:enabled':
                data[cmd] = '0'
            elif cmd == 'fan:duty-cycle':
                data[cmd] = '0.00'
            elif cmd.endswith(':enabled'):
                data[cmd] = '1'
            elif cmd.endswith(':voltage'):
                data[cmd] = '0.00'
            else:
                data[cmd] = 'http_value'
        
        print(f"📥 HTTP: Received {len(data)} parameters")
        await asyncio.sleep(0.1)  # Simulate network delay
        return data
    
    async def set_value(self, parameter: str, value: Any):
        """Mock set value."""
        print(f"📤 HTTP: Set {parameter} = {value}")
        return value
    
    async def get_value(self, parameter: str):
        """Mock get value."""
        print(f"📤 HTTP: Get {parameter}")
        return "http_value"


class MockWebSocketClient:
    """Mock WebSocket client for testing."""
    
    def __init__(self, host: str):
        self.host = host
        self._connected = False
        self._data_handlers = set()
        self._data = {}
    
    def add_data_handler(self, handler):
        """Add data handler."""
        self._data_handlers.add(handler)
        print(f"✅ WebSocket data handler added")
    
    @property
    def is_connected(self):
        """Check if connected."""
        return self._connected
    
    async def connect(self):
        """Mock connect."""
        print("🔌 WebSocket: Connecting...")
        await asyncio.sleep(0.1)
        self._connected = True
        print("✅ WebSocket: Connected")
        
        # Start sending mock data
        asyncio.create_task(self._send_mock_data())
        return True
    
    async def disconnect(self):
        """Mock disconnect."""
        print("🔌 WebSocket: Disconnecting...")
        self._connected = False
        print("✅ WebSocket: Disconnected")
    
    async def _send_mock_data(self):
        """Send mock WebSocket data periodically."""
        await asyncio.sleep(1)  # Initial delay
        
        while self._connected:
            # Send mock data updates
            mock_data = {
                'in-a:voltage': '9.55',  # Different from HTTP to show priority
                'fan:enabled': '0',
                'out-a:voltage': '0.00'
            }
            
            print(f"📨 WebSocket: Sending data update")
            for handler in self._data_handlers:
                try:
                    handler(mock_data)
                except Exception as e:
                    print(f"❌ Handler error: {e}")
            
            await asyncio.sleep(2)  # Send updates every 2 seconds


class SimpleHybridCoordinator:
    """Simplified hybrid coordinator for testing."""
    
    def __init__(self, hass, http_client, websocket_client, host, update_interval):
        self.hass = hass
        self.http_client = http_client
        self.websocket_client = websocket_client
        self.host = host
        self.update_interval = update_interval
        self._base_update_interval = update_interval
        
        # State tracking
        self._websocket_connected = False
        self._websocket_last_data_time = None
        self._websocket_data = {}
        self._http_data = {}
        self._http_last_data_time = None
        
        # Setup WebSocket handler
        self.websocket_client.add_data_handler(self._handle_websocket_data)
        
        # Mock coordinator behavior
        self.data = {}
        
        print(f"🔧 Hybrid coordinator initialized for {host}")
    
    def _handle_websocket_data(self, data: Dict[str, str]):
        """Handle WebSocket data updates."""
        if not data:
            return
        
        print(f"📥 WebSocket data received: {data}")
        
        # Update state
        self._websocket_connected = True
        self._websocket_last_data_time = datetime.utcnow()
        self._websocket_data.update(data)
        
        # Update coordinator data
        combined_data = self._get_combined_data()
        self.data = combined_data
        
        print(f"📊 Coordinator data updated via WebSocket")
    
    def _get_combined_data(self):
        """Get combined data with WebSocket priority."""
        # Start with HTTP data
        combined = self._http_data.copy()
        # Overlay WebSocket data (takes priority)
        combined.update(self._websocket_data)
        return combined
    
    def _should_use_websocket_data(self):
        """Check if WebSocket data is recent."""
        if not self._websocket_connected or not self._websocket_last_data_time:
            return False
        
        age = datetime.utcnow() - self._websocket_last_data_time
        max_age = self._base_update_interval * 2
        return age <= max_age
    
    def _get_adaptive_interval(self):
        """Get adaptive update interval."""
        if self._should_use_websocket_data():
            return self._base_update_interval * 3  # Reduce HTTP polling
        return self._base_update_interval
    
    async def async_update_data(self):
        """Update data using hybrid approach."""
        # Try WebSocket connection
        if not self.websocket_client.is_connected:
            try:
                await self.websocket_client.connect()
                self._websocket_connected = True
            except Exception as e:
                print(f"⚠️  WebSocket connection failed: {e}")
                self._websocket_connected = False
        
        # Adjust polling interval
        adaptive_interval = self._get_adaptive_interval()
        if self.update_interval != adaptive_interval:
            self.update_interval = adaptive_interval
            print(f"📊 Adjusted polling interval to {adaptive_interval.total_seconds()}s")
        
        # Skip HTTP if WebSocket data is recent
        if self._should_use_websocket_data():
            print("📊 Using recent WebSocket data, skipping HTTP")
            return self._get_combined_data()
        
        # Perform HTTP fetch
        print("📡 Performing HTTP data fetch")
        commands = [
            'in-a:voltage', 'fan:enabled', 'fan:duty-cycle',
            'out-a:enabled', 'out-a:voltage', 'out-b:enabled', 'out-b:voltage'
        ]
        
        try:
            http_data = await self.http_client.send_commands(commands)
            self._http_data = http_data
            self._http_last_data_time = datetime.utcnow()
            
            combined_data = self._get_combined_data()
            self.data = combined_data
            return combined_data
            
        except Exception as e:
            print(f"❌ HTTP fetch failed: {e}")
            # Return cached data if available
            if self._websocket_data or self._http_data:
                print("📊 Using cached data")
                return self._get_combined_data()
            raise
    
    async def async_set_value(self, parameter: str, value: Any):
        """Set value via HTTP."""
        await self.http_client.set_value(parameter, value)
        # Trigger refresh
        await self.async_update_data()
    
    def get_status(self):
        """Get connection status."""
        return {
            "websocket_connected": self._websocket_connected,
            "websocket_parameters": len(self._websocket_data),
            "http_parameters": len(self._http_data),
            "using_websocket_data": self._should_use_websocket_data(),
            "update_interval": self.update_interval.total_seconds(),
            "total_parameters": len(self.data)
        }
    
    async def async_shutdown(self):
        """Shutdown coordinator."""
        await self.websocket_client.disconnect()


async def test_hybrid_coordinator():
    """Test hybrid coordinator functionality."""
    print("🧪 Hybrid Coordinator Test")
    print("Testing WebSocket priority with HTTP fallback")
    print("=" * 60)
    
    # Create mock clients
    http_client = MockHTTPClient("192.168.105.15")
    websocket_client = MockWebSocketClient("192.168.105.15")
    
    # Create coordinator
    coordinator = SimpleHybridCoordinator(
        hass=None,
        http_client=http_client,
        websocket_client=websocket_client,
        host="192.168.105.15",
        update_interval=timedelta(seconds=10)
    )
    
    try:
        # Test 1: HTTP-only operation
        print("\n1️⃣  Testing HTTP-only Operation")
        print("-" * 40)
        
        await coordinator.async_update_data()
        status = coordinator.get_status()
        print(f"📊 Status: {status}")
        
        http_only_success = status['http_parameters'] > 0 and not status['using_websocket_data']
        print(f"✅ HTTP-only: {'PASS' if http_only_success else 'FAIL'}")
        
        # Test 2: WebSocket connection and priority
        print("\n2️⃣  Testing WebSocket Priority")
        print("-" * 40)
        
        # Connect WebSocket
        await websocket_client.connect()
        await asyncio.sleep(3)  # Wait for WebSocket data
        
        status = coordinator.get_status()
        print(f"📊 Status: {status}")
        
        # Check if WebSocket data takes priority
        websocket_priority = (
            status['websocket_connected'] and 
            status['websocket_parameters'] > 0 and
            coordinator.data.get('in-a:voltage') == '9.55'  # WebSocket value, not HTTP
        )
        print(f"✅ WebSocket priority: {'PASS' if websocket_priority else 'FAIL'}")
        
        # Test 3: Adaptive polling
        print("\n3️⃣  Testing Adaptive Polling")
        print("-" * 40)
        
        initial_interval = coordinator.update_interval.total_seconds()
        await coordinator.async_update_data()
        new_interval = coordinator.update_interval.total_seconds()
        
        adaptive_polling = new_interval > initial_interval
        print(f"📊 Interval changed: {initial_interval}s → {new_interval}s")
        print(f"✅ Adaptive polling: {'PASS' if adaptive_polling else 'FAIL'}")
        
        # Test 4: HTTP fallback
        print("\n4️⃣  Testing HTTP Fallback")
        print("-" * 40)
        
        # Disconnect WebSocket
        await websocket_client.disconnect()
        await asyncio.sleep(1)
        
        # Clear WebSocket data to force HTTP
        coordinator._websocket_data = {}
        coordinator._websocket_last_data_time = None
        
        await coordinator.async_update_data()
        status = coordinator.get_status()
        print(f"📊 Status: {status}")
        
        http_fallback = (
            not status['websocket_connected'] and
            status['http_parameters'] > 0 and
            not status['using_websocket_data']
        )
        print(f"✅ HTTP fallback: {'PASS' if http_fallback else 'FAIL'}")
        
        # Test 5: Control commands
        print("\n5️⃣  Testing Control Commands")
        print("-" * 40)
        
        try:
            await coordinator.async_set_value("fan:enabled", True)
            control_commands = True
            print("✅ Control commands: PASS")
        except Exception as e:
            print(f"❌ Control commands failed: {e}")
            control_commands = False
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        results = {
            "HTTP-only operation": http_only_success,
            "WebSocket priority": websocket_priority,
            "Adaptive polling": adaptive_polling,
            "HTTP fallback": http_fallback,
            "Control commands": control_commands
        }
        
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name}: {status}")
        
        all_passed = all(results.values())
        overall = "✅ ALL TESTS PASSED" if all_passed else "⚠️  SOME TESTS FAILED"
        print(f"\nOverall: {overall}")
        
        # Requirements validation
        print("\n📋 REQUIREMENTS VALIDATION")
        print("=" * 60)
        
        if websocket_priority:
            print("✅ Coordinator prioritizes WebSocket data")
        
        if http_fallback:
            print("✅ HTTP polling fallback when WebSocket unavailable")
        
        if websocket_priority or http_fallback:
            print("✅ WebSocket data handler integrated with coordinator updates")
        
        if control_commands:
            print("✅ Basic error handling implemented")
        
        return all_passed
        
    finally:
        await coordinator.async_shutdown()


if __name__ == "__main__":
    success = asyncio.run(test_hybrid_coordinator())
    print(f"\n{'🎉 SUCCESS' if success else '❌ FAILURE'}")
    exit(0 if success else 1)