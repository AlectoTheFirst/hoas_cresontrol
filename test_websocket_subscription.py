#!/usr/bin/env python3
"""
Test WebSocket subscription to see if it provides continuous updates.
"""

import asyncio
import aiohttp

async def test_websocket_subscription():
    """Test if WebSocket provides continuous updates without manual requests."""
    
    print("Testing WebSocket Subscription for Continuous Updates")
    print("Device: 192.168.105.15:81")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect('ws://192.168.105.15:81/websocket', timeout=10) as ws:
                
                # Test 1: Check if device sends automatic updates
                print("Test 1: Waiting for automatic updates (30 seconds)...")
                print("(If WebSocket subscription works, we should see periodic updates)")
                print("-" * 50)
                
                update_count = 0
                for i in range(30):  # Wait 30 seconds
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=1)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            response = msg.data.strip()
                            if "::" in response:
                                param, value = response.split("::", 1)
                                print(f"[{i:2d}s] Auto update: {param.strip()} = {value.strip()}")
                                update_count += 1
                    except asyncio.TimeoutError:
                        print(f"[{i:2d}s] No update")
                
                print(f"\nReceived {update_count} automatic updates in 30 seconds")
                
                # Test 2: Try subscription command
                print("\nTest 2: Testing subscription command...")
                await ws.send_str('subscription:subscribe()')
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=5)
                    print(f"Subscription response: {msg.data}")
                except asyncio.TimeoutError:
                    print("No subscription response")
                
                # Test 3: Wait for subscription updates
                print("\nTest 3: Waiting for subscription updates (30 seconds)...")
                print("-" * 50)
                
                subscription_updates = 0
                for i in range(30):
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=1)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            response = msg.data.strip()
                            if "::" in response:
                                param, value = response.split("::", 1)
                                print(f"[{i:2d}s] Subscription: {param.strip()} = {value.strip()}")
                                subscription_updates += 1
                    except asyncio.TimeoutError:
                        print(f"[{i:2d}s] No subscription update")
                
                print(f"\nReceived {subscription_updates} subscription updates in 30 seconds")
                
                # Test 4: Manual parameter requests
                print("\nTest 4: Testing manual parameter requests...")
                test_params = [
                    'extension:climate-2011:temperature',
                    'extension:climate-2011:humidity',
                    'extension:co2-2006:co2-concentration',
                    'extension:co2-2006:temperature'
                ]
                
                for param in test_params:
                    await ws.send_str(param)
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=3)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            response = msg.data.strip()
                            print(f"Manual request: {response}")
                    except asyncio.TimeoutError:
                        print(f"Manual request timeout: {param}")
                    
                    await asyncio.sleep(0.5)
                
        except Exception as e:
            print(f"WebSocket connection error: {e}")

async def test_http_vs_websocket():
    """Compare HTTP vs WebSocket data freshness."""
    
    print("\n" + "=" * 60)
    print("HTTP vs WebSocket Data Freshness Test")
    print("=" * 60)
    
    # Test HTTP requests
    print("\nHTTP requests (should always return fresh data):")
    async with aiohttp.ClientSession() as session:
        for i in range(3):
            try:
                url = "http://192.168.105.15/command?query=extension:climate-2011:temperature"
                async with session.get(url, timeout=5) as response:
                    text = await response.text()
                    print(f"HTTP {i+1}: {text}")
            except Exception as e:
                print(f"HTTP {i+1}: Error - {e}")
            
            await asyncio.sleep(2)
    
    # Test WebSocket requests
    print("\nWebSocket requests:")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect('ws://192.168.105.15:81/websocket', timeout=10) as ws:
                for i in range(3):
                    await ws.send_str('extension:climate-2011:temperature')
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=3)
                        print(f"WebSocket {i+1}: {msg.data}")
                    except asyncio.TimeoutError:
                        print(f"WebSocket {i+1}: Timeout")
                    
                    await asyncio.sleep(2)
        except Exception as e:
            print(f"WebSocket error: {e}")

async def main():
    """Run WebSocket subscription tests."""
    await test_websocket_subscription()
    await test_http_vs_websocket()
    
    print("\n" + "=" * 60)
    print("CONCLUSIONS")
    print("=" * 60)
    print("\nBased on the test results:")
    print("1. If no automatic updates: WebSocket subscription is NOT supported")
    print("2. If manual requests work: Use HTTP polling instead")
    print("3. If subscription works: WebSocket is properly configured")
    print("\nFor Home Assistant integration:")
    print("- If WebSocket subscription doesn't work, disable WebSocket")
    print("- Use HTTP polling with appropriate intervals (10-30 seconds)")
    print("- This will ensure fresh data updates in Home Assistant")

if __name__ == "__main__":
    asyncio.run(main())