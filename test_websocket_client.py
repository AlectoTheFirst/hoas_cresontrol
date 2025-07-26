#!/usr/bin/env python3
"""
Test script for the simplified CresControl WebSocket client.
Tests against a real CresControl device at 192.168.105.15:81
"""

import asyncio
import aiohttp
import logging
from typing import Dict

# Set up logging
logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

# Import our WebSocket client
from custom_components.crescontrol.websocket_client import CresControlWebSocketClient, CresControlWebSocketError


class WebSocketTester:
    """Test harness for WebSocket client functionality."""
    
    def __init__(self, host: str = "192.168.105.15"):
        self.host = host
        self.session: aiohttp.ClientSession = None
        self.ws_client: CresControlWebSocketClient = None
        self.received_data: Dict[str, str] = {}
        self.message_count = 0
    
    async def setup(self):
        """Set up test environment."""
        self.session = aiohttp.ClientSession()
        self.ws_client = CresControlWebSocketClient(
            host=self.host,
            session=self.session,
            port=81,
            path="/websocket"
        )
        
        # Add data handler to collect received data
        self.ws_client.add_data_handler(self._data_handler)
    
    async def teardown(self):
        """Clean up test environment."""
        if self.ws_client:
            await self.ws_client.disconnect()
        if self.session:
            await self.session.close()
    
    def _data_handler(self, data: Dict[str, str]):
        """Handle incoming data updates."""
        self.message_count += 1
        self.received_data.update(data)
        for param, value in data.items():
            print(f"📨 Data update #{self.message_count}: {param} = {value}")
    
    async def test_connection(self) -> bool:
        """Test WebSocket connection."""
        print("\n🔌 Testing WebSocket Connection")
        print("=" * 50)
        
        try:
            success = await self.ws_client.connect()
            if success:
                print("✅ WebSocket connection successful")
                
                # Check connection status
                stats = self.ws_client.get_statistics()
                print(f"📊 Connection URL: {stats['url']}")
                print(f"📊 Connected: {stats['connected']}")
                
                return True
            else:
                print("❌ WebSocket connection failed")
                return False
                
        except CresControlWebSocketError as e:
            print(f"❌ WebSocket connection error: {e}")
            return False
    
    async def test_send_commands(self) -> bool:
        """Test sending commands via WebSocket."""
        print("\n📤 Testing Command Sending")
        print("=" * 50)
        
        if not self.ws_client.is_connected:
            print("❌ WebSocket not connected")
            return False
        
        test_commands = [
            "in-a:voltage",
            "in-b:voltage", 
            "out-a:voltage",
            "fan:enabled",
            "switch-12v:enabled"
        ]
        
        try:
            for cmd in test_commands:
                await self.ws_client.send_command(cmd)
                print(f"✅ Sent command: {cmd}")
                await asyncio.sleep(0.2)  # Small delay between commands
            
            return True
            
        except CresControlWebSocketError as e:
            print(f"❌ Command sending error: {e}")
            return False
    
    async def test_data_reception(self, duration: int = 10) -> bool:
        """Test receiving data updates."""
        print(f"\n📥 Testing Data Reception ({duration}s)")
        print("=" * 50)
        
        if not self.ws_client.is_connected:
            print("❌ WebSocket not connected")
            return False
        
        initial_count = self.message_count
        print(f"Listening for {duration} seconds...")
        
        # Wait for messages
        await asyncio.sleep(duration)
        
        messages_received = self.message_count - initial_count
        print(f"\n📊 Messages received: {messages_received}")
        print(f"📊 Unique parameters: {len(self.received_data)}")
        
        if messages_received > 0:
            print("✅ Data reception successful")
            
            # Show some received data
            print("\n📋 Sample received data:")
            for param, value in list(self.received_data.items())[:5]:
                print(f"  {param}: {value}")
            
            return True
        else:
            print("❌ No data received")
            return False
    
    async def test_statistics(self) -> bool:
        """Test statistics reporting."""
        print("\n📊 Testing Statistics")
        print("=" * 50)
        
        stats = self.ws_client.get_statistics()
        
        print(f"Host: {stats['host']}")
        print(f"Port: {stats['port']}")
        print(f"Path: {stats['path']}")
        print(f"Connected: {stats['connected']}")
        print(f"Messages sent: {stats['messages_sent']}")
        print(f"Messages received: {stats['messages_received']}")
        print(f"Data handlers: {stats['data_handlers']}")
        print(f"Last data count: {stats['last_data_count']}")
        
        if stats['connection_time']:
            print(f"Connection time: {stats['connection_time']}")
            print(f"Uptime: {stats['uptime_seconds']:.1f}s")
        
        return True
    
    async def test_multiple_parameters(self) -> bool:
        """Test subscription to multiple parameters."""
        print("\n🔄 Testing Multiple Parameter Subscription")
        print("=" * 50)
        
        if not self.ws_client.is_connected:
            print("❌ WebSocket not connected")
            return False
        
        # Test parameters from requirements
        test_params = [
            "in-a:voltage",      # Requirement 2.1
            "in-b:voltage",      # Requirement 2.1
            "fan:enabled",       # Requirement 2.2
            "fan:duty-cycle",    # Requirement 2.2
            "out-a:enabled",     # Requirement 2.3
            "out-a:voltage",     # Requirement 2.4
            "out-b:enabled",     # Requirement 2.3
            "out-b:voltage",     # Requirement 2.4
            "switch-12v:enabled", # Requirement 2.5
            "switch-24v-a:enabled", # Requirement 2.5
        ]
        
        print(f"Testing {len(test_params)} parameters...")
        
        # Send all test commands
        for param in test_params:
            try:
                await self.ws_client.send_command(param)
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"⚠️  Failed to send {param}: {e}")
        
        # Wait for responses
        await asyncio.sleep(5)
        
        # Check which parameters we received data for
        received_params = set(self.received_data.keys())
        test_param_set = set(test_params)
        
        successful_params = received_params.intersection(test_param_set)
        missing_params = test_param_set - received_params
        
        print(f"✅ Received data for {len(successful_params)} parameters:")
        for param in sorted(successful_params):
            print(f"  {param}: {self.received_data[param]}")
        
        if missing_params:
            print(f"⚠️  Missing data for {len(missing_params)} parameters:")
            for param in sorted(missing_params):
                print(f"  {param}")
        
        return len(successful_params) > 0


async def main():
    """Main test function."""
    print("🧪 CresControl WebSocket Client Test")
    print("Testing against device: 192.168.105.15:81")
    
    tester = WebSocketTester()
    
    try:
        await tester.setup()
        
        # Run tests
        results = {}
        
        # Test 1: Connection
        results['connection'] = await tester.test_connection()
        
        if results['connection']:
            # Test 2: Command sending
            results['commands'] = await tester.test_send_commands()
            
            # Test 3: Data reception
            results['data_reception'] = await tester.test_data_reception(10)
            
            # Test 4: Multiple parameters
            results['multiple_params'] = await tester.test_multiple_parameters()
            
            # Test 5: Statistics
            results['statistics'] = await tester.test_statistics()
        else:
            # Skip other tests if connection failed
            results.update({
                'commands': False,
                'data_reception': False,
                'multiple_params': False,
                'statistics': False
            })
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
        
        all_passed = all(results.values())
        overall_status = "✅ ALL TESTS PASSED" if all_passed else "⚠️  SOME TESTS FAILED"
        print(f"\nOverall: {overall_status}")
        
        # Requirements validation
        print("\n📋 REQUIREMENTS VALIDATION")
        print("=" * 60)
        
        if results['connection']:
            print("✅ WebSocket connects to ws://host:81/websocket")
        
        if results['data_reception']:
            print("✅ Message parsing for parameter::value format works")
        
        if results['multiple_params']:
            print("✅ Subscription to multiple parameters works")
        
        if results['connection'] and results['data_reception']:
            print("✅ Data handler callbacks for coordinator integration ready")
        
        return all_passed
        
    finally:
        await tester.teardown()


if __name__ == "__main__":
    asyncio.run(main())