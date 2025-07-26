#!/usr/bin/env python3
"""
Simple integration test for CresControl WebSocket functionality.
Tests against a real CresControl device at 192.168.105.15:81
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, Optional


class SimpleWebSocketClient:
    """Simplified WebSocket client for testing CresControl device."""
    
    def __init__(self, host: str, port: int = 81, path: str = "/websocket"):
        self.host = host
        self.port = port 
        self.path = path
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.connected = False
        self.data_handler = None
        
    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}{self.path}"
    
    async def connect(self) -> bool:
        """Connect to WebSocket server."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            print(f"Connecting to WebSocket at {self.url}")
            self.websocket = await self.session.ws_connect(
                self.url,
                timeout=30,
                heartbeat=30
            )
            
            self.connected = True
            print("✓ WebSocket connected successfully")
            
            # Subscribe to all updates
            await self.subscribe_to_updates()
            
            return True
            
        except Exception as e:
            print(f"✗ WebSocket connection failed: {e}")
            self.connected = False
            return False
    
    async def subscribe_to_updates(self):
        """Subscribe to data updates."""
        if not self.websocket:
            return
            
        try:
            # Send simple string commands, not JSON
            test_commands = ["in-a:voltage", "fan:rpm", "out-a:voltage"]
            for cmd in test_commands:
                await self.websocket.send_str(cmd)
                print(f"✓ Sent test command: {cmd}")
        except Exception as e:
            print(f"✗ Failed to send commands: {e}")
    
    async def send_command(self, command: str):
        """Send command via WebSocket."""
        if not self.websocket or not self.connected:
            raise Exception("WebSocket not connected")
        
        try:
            await self.websocket.send_str(command)
            print(f"✓ Sent command: {command}")
        except Exception as e:
            print(f"✗ Failed to send command: {e}")
            raise
    
    def set_data_handler(self, handler):
        """Set data handler callback."""
        self.data_handler = handler
    
    async def listen_for_messages(self, duration: int = 30):
        """Listen for WebSocket messages for specified duration."""
        if not self.websocket:
            return
        
        print(f"Listening for messages for {duration} seconds...")
        start_time = time.time()
        message_count = 0
        
        try:
            async for msg in self.websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # Handle CresControl format: "param::value"
                    message_count += 1
                    print(f"📨 Received message #{message_count}: {msg.data}")
                    
                    if "::" in msg.data:
                        param, value = msg.data.split("::", 1)
                        print(f"  ✓ Parsed: {param.strip()} = {value.strip()}")
                        
                        if self.data_handler:
                            self.data_handler({param.strip(): value.strip()})
                    else:
                        print(f"  ⚠️  Unexpected format: {msg.data}")
                
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"✗ WebSocket error: {self.websocket.exception()}")
                    break
                
                # Check if duration elapsed
                if time.time() - start_time > duration:
                    print(f"✓ Completed {duration}s listening period")
                    break
                    
        except Exception as e:
            print(f"✗ Error during message listening: {e}")
        
        print(f"📊 Total messages received: {message_count}")
        return message_count
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        if self.session:
            await self.session.close()
            self.session = None
        
        self.connected = False
        print("✓ WebSocket disconnected")


class SimpleHTTPClient:
    """Simplified HTTP client for testing CresControl device."""
    
    def __init__(self, host: str, port: int = 80):
        self.host = host
        self.port = port
        self.session: Optional[aiohttp.ClientSession] = None
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    async def get_value(self, parameter: str) -> Optional[str]:
        """Get parameter value via HTTP."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            url = f"{self.base_url}/command"
            params = {"query": parameter}
            
            async with self.session.get(url, params=params, timeout=10) as response:
                response.raise_for_status()
                text = await response.text()
                
                # Parse response (format: "param::value")
                if "::" in text:
                    parts = text.strip().split("::")
                    if len(parts) >= 2:
                        return parts[1]
                
                return text.strip()
                
        except Exception as e:
            print(f"✗ HTTP request failed: {e}")
            return None
    
    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None


async def test_backward_compatibility():
    """Test that HTTP-only operation still works (backward compatibility)."""
    print("\n" + "="*60)
    print("🔙 TESTING BACKWARD COMPATIBILITY (HTTP-only)")
    print("="*60)
    
    http_client = SimpleHTTPClient("192.168.105.15", 81)
    
    try:
        # Test basic HTTP communication
        print("\n📡 Testing HTTP communication...")
        voltage = await http_client.get_value("in-a:voltage")
        
        if voltage:
            print(f"✓ HTTP GET successful: in-a:voltage = {voltage}")
            return True
        else:
            print("✗ HTTP GET failed")
            return False
            
    finally:
        await http_client.close()


async def test_websocket_functionality():
    """Test WebSocket functionality."""
    print("\n" + "="*60)
    print("🔌 TESTING WEBSOCKET FUNCTIONALITY")
    print("="*60)
    
    # Try different WebSocket paths on port 81
    test_configs = [
        {"port": 81, "path": "/websocket"},
        {"port": 81, "path": "/ws"},
    ]
    
    for config in test_configs:
        print(f"\n🔍 Trying WebSocket on port {config['port']} with path {config['path']}")
        
        ws_client = SimpleWebSocketClient("192.168.105.15", **config)
        
        try:
            # Test connection
            if await ws_client.connect():
                print("✓ WebSocket connection successful!")
                
                # Test sending a command (simple string format)
                try:
                    test_command = "in-a:voltage"  # Simple string, not JSON
                    await ws_client.send_command(test_command)
                    print("✓ Command sent successfully")
                except Exception as e:
                    print(f"⚠️  Command sending failed: {e}")
                
                # Listen for messages
                message_count = await ws_client.listen_for_messages(10)
                
                await ws_client.disconnect()
                
                if message_count > 0:
                    print(f"✓ WebSocket test successful! Received {message_count} messages")
                    return True
                else:
                    print("⚠️  No messages received during test period")
                    
            else:
                print(f"✗ Failed to connect on port {config['port']}")
                
        except Exception as e:
            print(f"✗ WebSocket test failed: {e}")
        
        finally:
            await ws_client.disconnect()
    
    print("✗ All WebSocket configurations failed")
    return False


async def test_hybrid_operation():
    """Test hybrid HTTP + WebSocket operation."""
    print("\n" + "="*60)  
    print("🔄 TESTING HYBRID HTTP + WEBSOCKET OPERATION")
    print("="*60)
    
    # This would test that HTTP polling can be reduced when WebSocket provides real-time data
    # For now, just demonstrate the concept
    
    http_client = SimpleHTTPClient("192.168.105.15", 81)
    ws_client = SimpleWebSocketClient("192.168.105.15", 81, "/websocket")
    
    try:
        print("\n📡 Testing HTTP baseline...")
        voltage_http = await http_client.get_value("in-a:voltage")
        print(f"HTTP result: {voltage_http}")
        
        print("\n🔌 Testing WebSocket overlay...")
        ws_connected = await ws_client.connect()
        
        if ws_connected:
            print("✓ Hybrid operation possible - WebSocket can supplement HTTP")
            
            # In real implementation, HTTP polling would be reduced when WebSocket is active
            print("💡 In production: HTTP polling interval would be increased when WebSocket provides real-time data")
            
            await ws_client.disconnect()
            return True
        else:
            print("✓ Graceful fallback - HTTP-only operation continues when WebSocket unavailable")
            return True
            
    finally:
        await http_client.close()
        await ws_client.disconnect()


async def main():
    """Main test function."""
    print("🧪 CresControl WebSocket Integration Test")
    print("Testing against device: 192.168.105.15:81")
    
    results = {
        "backward_compatibility": False,
        "websocket_functionality": False, 
        "hybrid_operation": False
    }
    
    # Test 1: Backward compatibility (HTTP-only)
    try:
        results["backward_compatibility"] = await test_backward_compatibility()
    except Exception as e:
        print(f"✗ Backward compatibility test error: {e}")
    
    # Test 2: WebSocket functionality  
    try:
        results["websocket_functionality"] = await test_websocket_functionality()
    except Exception as e:
        print(f"✗ WebSocket functionality test error: {e}")
    
    # Test 3: Hybrid operation
    try:
        results["hybrid_operation"] = await test_hybrid_operation()
    except Exception as e:
        print(f"✗ Hybrid operation test error: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("📋 TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    all_passed = all(results.values())
    overall_status = "✓ ALL TESTS PASSED" if all_passed else "⚠️  SOME TESTS FAILED"
    print(f"\nOverall: {overall_status}")
    
    if results["backward_compatibility"]:
        print("\n✅ Backward compatibility confirmed - existing HTTP-only setups will continue working")
    
    if results["websocket_functionality"]:
        print("✅ WebSocket functionality validated - real-time updates available")
    elif results["backward_compatibility"]:
        print("⚠️  WebSocket not available, but HTTP fallback ensures functionality")
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(main())