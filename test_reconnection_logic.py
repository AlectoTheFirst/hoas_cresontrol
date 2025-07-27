#!/usr/bin/env python3
"""
Test the WebSocket reconnection logic to ensure it handles disconnections properly.
This is a simplified test that doesn't require Home Assistant dependencies.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Dict, Set, Callable, Optional, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simplified WebSocket client for testing (without Home Assistant dependencies)
class SimpleWebSocketClient:
    """Simplified WebSocket client for testing reconnection logic."""
    
    def __init__(self, host: str, session: aiohttp.ClientSession):
        self._host = host
        self._ws_url = f"ws://{host}:81/websocket"
        self._session = session
        self._websocket = None
        self._connected = False
        self._should_reconnect = True
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 2
        self._max_reconnect_delay = 30
        self._connection_task = None
        self._reconnect_task = None
        self._data_handlers = set()
        self._messages_received = 0
        self._total_reconnects = 0
    
    async def connect(self):
        """Connect with reconnection logic."""
        if self._websocket and not self._websocket.closed:
            return True
        
        try:
            logger.info(f"Connecting to {self._ws_url} (attempt {self._reconnect_attempts + 1})")
            self._websocket = await self._session.ws_connect(self._ws_url, timeout=10, heartbeat=30)
            self._connected = True
            
            if self._reconnect_attempts > 0:
                logger.info(f"Reconnected after {self._reconnect_attempts} attempts")
                self._total_reconnects += 1
            
            self._reconnect_attempts = 0
            self._connection_task = asyncio.create_task(self._handle_messages())
            
            # Send test commands
            await self._websocket.send_str('extension:climate-2011:temperature')
            await self._websocket.send_str('extension:co2-2006:co2-concentration')
            
            return True
            
        except Exception as e:
            self._connected = False
            self._reconnect_attempts += 1
            
            if self._reconnect_attempts <= self._max_reconnect_attempts:
                logger.warning(f"Connection failed (attempt {self._reconnect_attempts}): {e}")
                if self._should_reconnect and not self._reconnect_task:
                    self._reconnect_task = asyncio.create_task(self._reconnect_loop())
                return False
            else:
                logger.error(f"Failed to connect after {self._max_reconnect_attempts} attempts")
                raise
    
    async def _reconnect_loop(self):
        """Reconnection loop with exponential backoff."""
        while self._should_reconnect and self._reconnect_attempts <= self._max_reconnect_attempts:
            delay = min(self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)), self._max_reconnect_delay)
            logger.info(f"Reconnecting in {delay} seconds...")
            await asyncio.sleep(delay)
            
            if not self._should_reconnect:
                break
            
            success = await self.connect()
            if success:
                break
        
        self._reconnect_task = None
    
    async def _handle_messages(self):
        """Handle WebSocket messages."""
        try:
            async for msg in self._websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._messages_received += 1
                    data = msg.data.strip()
                    
                    if "::" in data:
                        param, value = data.split("::", 1)
                        update = {param.strip(): value.strip()}
                        
                        for handler in self._data_handlers:
                            try:
                                handler(update)
                            except Exception as e:
                                logger.error(f"Handler error: {e}")
                
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    logger.info("WebSocket closed by server")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self._websocket.exception()}")
                    break
        
        except Exception as e:
            logger.error(f"Message handler error: {e}")
        
        finally:
            self._connected = False
            if self._should_reconnect and not self._reconnect_task:
                logger.info("Connection lost, starting reconnection")
                self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    def add_data_handler(self, handler):
        """Add data handler."""
        self._data_handlers.add(handler)
    
    async def disconnect(self):
        """Disconnect and stop reconnection."""
        self._should_reconnect = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
        
        if self._connection_task:
            self._connection_task.cancel()
        
        if self._websocket and not self._websocket.closed:
            await self._websocket.close()
        
        self._connected = False
    
    @property
    def is_connected(self):
        return self._connected and self._websocket and not self._websocket.closed
    
    def get_stats(self):
        return {
            "connected": self.is_connected,
            "messages_received": self._messages_received,
            "reconnect_attempts": self._reconnect_attempts,
            "total_reconnects": self._total_reconnects,
        }

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestDataHandler:
    """Test data handler to collect WebSocket updates."""
    
    def __init__(self):
        self.received_data = []
        self.update_count = 0
    
    def handle_data(self, data):
        """Handle incoming data updates."""
        self.received_data.append(data)
        self.update_count += 1
        logger.info(f"Received data update #{self.update_count}: {data}")

async def test_websocket_reconnection():
    """Test WebSocket reconnection logic."""
    
    print("Testing WebSocket Reconnection Logic")
    print("Device: 192.168.105.15:81")
    print("=" * 60)
    
    handler = TestDataHandler()
    
    async with aiohttp.ClientSession() as session:
        client = SimpleWebSocketClient("192.168.105.15", session)
        client.add_data_handler(handler.handle_data)
        
        try:
            # Test 1: Initial connection
            print("\nTest 1: Initial connection")
            print("-" * 30)
            
            success = await client.connect()
            if success:
                print("✅ Initial connection successful")
                
                # Wait for some data
                await asyncio.sleep(10)
                print(f"Received {handler.update_count} updates")
                
                # Print statistics
                stats = client.get_stats()
                print(f"Connection stats: {stats}")
                
            else:
                print("❌ Initial connection failed")
                return
            
            # Test 2: Simulate disconnection by closing WebSocket
            print("\nTest 2: Simulating disconnection")
            print("-" * 30)
            
            if client._websocket and not client._websocket.closed:
                await client._websocket.close()
                print("✅ WebSocket connection closed")
                
                # Wait for reconnection logic to kick in
                print("Waiting for automatic reconnection...")
                await asyncio.sleep(15)
                
                # Check if reconnected
                if client.is_connected:
                    print("✅ Automatic reconnection successful")
                else:
                    print("❌ Automatic reconnection failed")
                
                # Print updated statistics
                stats = client.get_stats()
                print(f"Reconnection stats: {stats}")
            
            # Test 3: Monitor for continued updates
            print("\nTest 3: Monitoring continued updates")
            print("-" * 30)
            
            initial_count = handler.update_count
            await asyncio.sleep(20)
            final_count = handler.update_count
            
            updates_received = final_count - initial_count
            print(f"Received {updates_received} updates after reconnection")
            
            if updates_received > 0:
                print("✅ Data updates resumed after reconnection")
            else:
                print("❌ No data updates after reconnection")
            
        except Exception as e:
            print(f"Test error: {e}")
            
        finally:
            # Clean shutdown
            print("\nShutting down...")
            await client.disconnect()
            print("✅ Clean shutdown complete")

async def test_connection_resilience():
    """Test connection resilience with multiple disconnections."""
    
    print("\n" + "=" * 60)
    print("Testing Connection Resilience")
    print("=" * 60)
    
    handler = TestDataHandler()
    
    async with aiohttp.ClientSession() as session:
        client = SimpleWebSocketClient("192.168.105.15", session)
        client.add_data_handler(handler.handle_data)
        
        try:
            # Connect initially
            await client.connect()
            
            # Simulate multiple disconnections
            for i in range(3):
                print(f"\nDisconnection test {i+1}/3")
                print("-" * 20)
                
                # Force disconnect
                if client._websocket and not client._websocket.closed:
                    await client._websocket.close()
                    print("Connection closed")
                
                # Wait for reconnection
                await asyncio.sleep(10)
                
                if client.is_connected:
                    print("✅ Reconnected successfully")
                else:
                    print("❌ Reconnection failed")
                
                # Brief data collection period
                initial_count = handler.update_count
                await asyncio.sleep(5)
                updates = handler.update_count - initial_count
                print(f"Received {updates} updates")
            
            # Final statistics
            stats = client.get_stats()
            print(f"\nFinal statistics:")
            print(f"  Total reconnects: {stats.get('total_reconnects', 0)}")
            print(f"  Messages received: {stats.get('messages_received', 0)}")
            print(f"  Currently connected: {stats.get('connected', False)}")
            
        except Exception as e:
            print(f"Resilience test error: {e}")
            
        finally:
            await client.disconnect()

async def main():
    """Run all reconnection tests."""
    try:
        await test_websocket_reconnection()
        await test_connection_resilience()
        
        print("\n" + "=" * 60)
        print("RECONNECTION TEST CONCLUSIONS")
        print("=" * 60)
        print("\nIf reconnection works properly:")
        print("1. WebSocket should automatically reconnect after disconnection")
        print("2. Data updates should resume after reconnection")
        print("3. Statistics should show reconnection attempts and successes")
        print("\nThis will fix the stale data issue in Home Assistant by:")
        print("- Maintaining continuous WebSocket connection")
        print("- Automatically recovering from network interruptions")
        print("- Falling back to HTTP polling when WebSocket fails")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(main())