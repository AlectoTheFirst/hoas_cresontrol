#!/usr/bin/env python3
"""
Test the periodic refresh functionality to ensure continuous data updates.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCollector:
    """Collect and analyze data updates."""
    
    def __init__(self):
        self.updates = []
        self.parameter_counts = {}
    
    def handle_data(self, data):
        """Handle incoming data updates."""
        timestamp = datetime.now()
        self.updates.append((timestamp, data))
        
        for param in data:
            self.parameter_counts[param] = self.parameter_counts.get(param, 0) + 1
        
        logger.info(f"[{timestamp.strftime('%H:%M:%S')}] Data: {data}")
    
    def get_summary(self):
        """Get summary of collected data."""
        return {
            "total_updates": len(self.updates),
            "parameter_counts": self.parameter_counts,
            "unique_parameters": len(self.parameter_counts),
            "time_span": (
                (self.updates[-1][0] - self.updates[0][0]).total_seconds()
                if len(self.updates) > 1 else 0
            )
        }

# Simplified WebSocket client with periodic refresh
class RefreshingWebSocketClient:
    """WebSocket client with periodic refresh for testing."""
    
    def __init__(self, host: str, session: aiohttp.ClientSession):
        self._host = host
        self._ws_url = f"ws://{host}:81/websocket"
        self._session = session
        self._websocket = None
        self._connected = False
        self._should_run = True
        self._connection_task = None
        self._refresh_task = None
        self._refresh_interval = 8  # Refresh every 8 seconds
        self._data_handlers = set()
        self._subscribed_parameters = {
            'extension:climate-2011:temperature',
            'extension:climate-2011:humidity',
            'extension:co2-2006:co2-concentration',
            'extension:co2-2006:temperature',
            'in-a:voltage',
            'fan:rpm',
        }
    
    async def connect(self):
        """Connect to WebSocket."""
        try:
            logger.info(f"Connecting to {self._ws_url}")
            self._websocket = await self._session.ws_connect(self._ws_url, timeout=10, heartbeat=30)
            self._connected = True
            
            # Start tasks
            self._connection_task = asyncio.create_task(self._handle_messages())
            self._refresh_task = asyncio.create_task(self._periodic_refresh())
            
            # Initial data request
            await self._request_all_parameters()
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def _handle_messages(self):
        """Handle WebSocket messages."""
        try:
            async for msg in self._websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.data.strip()
                    
                    if "::" in data:
                        param, value = data.split("::", 1)
                        update = {param.strip(): value.strip()}
                        
                        for handler in self._data_handlers:
                            try:
                                handler(update)
                            except Exception as e:
                                logger.error(f"Handler error: {e}")
                
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    logger.info("WebSocket connection closed")
                    break
        
        except Exception as e:
            logger.error(f"Message handler error: {e}")
        
        finally:
            self._connected = False
    
    async def _periodic_refresh(self):
        """Periodically request fresh data."""
        while self._should_run and self._connected:
            try:
                await asyncio.sleep(self._refresh_interval)
                
                if not self._connected:
                    break
                
                logger.info("Requesting fresh data...")
                await self._request_all_parameters()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Refresh error: {e}")
    
    async def _request_all_parameters(self):
        """Request all subscribed parameters."""
        for param in self._subscribed_parameters:
            try:
                await self._websocket.send_str(param)
                await asyncio.sleep(0.1)  # Small delay
            except Exception as e:
                logger.debug(f"Failed to request {param}: {e}")
    
    def add_data_handler(self, handler):
        """Add data handler."""
        self._data_handlers.add(handler)
    
    async def disconnect(self):
        """Disconnect and cleanup."""
        self._should_run = False
        
        if self._refresh_task:
            self._refresh_task.cancel()
        
        if self._connection_task:
            self._connection_task.cancel()
        
        if self._websocket and not self._websocket.closed:
            await self._websocket.close()
        
        self._connected = False

async def test_periodic_refresh():
    """Test periodic refresh functionality."""
    
    print("Testing Periodic Data Refresh")
    print("Device: 192.168.105.15:81")
    print("=" * 50)
    
    collector = DataCollector()
    
    async with aiohttp.ClientSession() as session:
        client = RefreshingWebSocketClient("192.168.105.15", session)
        client.add_data_handler(collector.handle_data)
        
        try:
            # Connect
            success = await client.connect()
            if not success:
                print("❌ Connection failed")
                return
            
            print("✅ Connected successfully")
            print("Collecting data for 60 seconds...")
            print("-" * 30)
            
            # Collect data for 60 seconds
            await asyncio.sleep(60)
            
            # Analyze results
            summary = collector.get_summary()
            
            print("\n" + "=" * 50)
            print("RESULTS")
            print("=" * 50)
            print(f"Total updates received: {summary['total_updates']}")
            print(f"Unique parameters: {summary['unique_parameters']}")
            print(f"Time span: {summary['time_span']:.1f} seconds")
            print(f"Average update rate: {summary['total_updates'] / max(summary['time_span'], 1):.2f} updates/second")
            
            print("\nParameter update counts:")
            for param, count in summary['parameter_counts'].items():
                print(f"  {param}: {count} updates")
            
            # Evaluate success
            if summary['total_updates'] > 10:
                print("\n✅ Periodic refresh is working - receiving regular updates")
            else:
                print("\n❌ Periodic refresh may not be working - few updates received")
            
            if summary['unique_parameters'] >= 4:
                print("✅ Multiple parameters are being updated")
            else:
                print("❌ Limited parameter diversity")
            
        except Exception as e:
            print(f"Test error: {e}")
        
        finally:
            await client.disconnect()
            print("\n✅ Test completed")

async def main():
    """Run periodic refresh test."""
    try:
        await test_periodic_refresh()
        
        print("\n" + "=" * 50)
        print("CONCLUSIONS")
        print("=" * 50)
        print("\nIf periodic refresh works:")
        print("1. You should see regular data updates every ~8 seconds")
        print("2. Multiple parameters should be updated")
        print("3. This will solve the stale data issue in Home Assistant")
        print("\nThe periodic refresh ensures:")
        print("- Fresh data is requested regularly")
        print("- Home Assistant entities stay up-to-date")
        print("- No more stale sensor values")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())