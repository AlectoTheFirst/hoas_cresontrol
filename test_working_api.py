#!/usr/bin/env python3
"""
Test to find the working HTTP API format for CresControl device.
Based on command reference and connectivity tests.
"""

import asyncio
import aiohttp
import json


async def test_websocket_commands():
    """Test WebSocket commands to confirm the device responds correctly."""
    print("🔌 Testing WebSocket commands (known to work)...")
    
    host = "192.168.105.15"
    ws_url = f"ws://{host}:81/websocket"
    
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.ws_connect(ws_url, timeout=30) as ws:
                print(f"✅ Connected to WebSocket: {ws_url}")
                
                # Test READ-ONLY commands from command reference
                test_commands = [
                    "in-a:voltage",    # Analog input A voltage (read-only)
                    "in-b:voltage",    # Analog input B voltage (read-only) 
                    "fan:rpm",         # Fan RPM (read-only)
                    "fan:enabled",     # Fan enabled state (read-write, but we're just reading)
                ]
                
                results = {}
                
                for command in test_commands:
                    try:
                        await ws.send_str(command)
                        print(f"📤 Sent: {command}")
                        
                        # Wait for response
                        msg = await asyncio.wait_for(ws.receive(), timeout=5)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            response = msg.data
                            print(f"📥 Received: {response}")
                            
                            if "::" in response:
                                param, value = response.split("::", 1)
                                results[param.strip()] = value.strip()
                                print(f"✅ Parsed: {param.strip()} = {value.strip()}")
                            else:
                                print(f"⚠️  Unexpected format: {response}")
                                results[command] = response
                        
                    except asyncio.TimeoutError:
                        print(f"⏰ No response for {command}")
                        results[command] = None
                    except Exception as e:
                        print(f"❌ Error with {command}: {e}")
                        results[command] = None
                
                return results
                
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return {}


async def test_http_on_websocket_port():
    """Test if there's an HTTP API hidden on the WebSocket port."""
    print("\n🔍 Testing HTTP endpoints on WebSocket port (81)...")
    
    host = "192.168.105.15"
    base_url = f"http://{host}:81"
    
    # Try different paths that might work
    test_paths = [
        "/command",
        "/api",
        "/cmd", 
        "/query",
        "/http",
        "/rest",
        "/api/command",
        "/api/query"
    ]
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for path in test_paths:
            url = f"{base_url}{path}"
            
            try:
                # Test with query parameter (like existing code expects)
                async with session.get(
                    url,
                    params={"query": "in-a:voltage"},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    status = response.status
                    text = await response.text()
                    
                    if status == 200 and "::" in text:
                        print(f"✅ FOUND WORKING HTTP API: {url}")
                        print(f"   Response: {text}")
                        return url, "query"
                    elif status != 400:  # 400 is "WebSocket server only"
                        print(f"   {path}: HTTP {status} - {text[:50]}...")
                        
            except Exception as e:
                print(f"   {path}: ERROR - {e}")
    
    print("❌ No HTTP API found on port 81")
    return None, None


async def test_http_on_web_port():
    """Test if there's an HTTP API on the web interface port (80)."""
    print("\n🌐 Testing HTTP API on web interface port (80)...")
    
    host = "192.168.105.15"
    base_url = f"http://{host}:80"
    
    # Try different API paths
    test_paths = [
        "/command",
        "/api",
        "/api/command",
        "/cmd",
        "/query",
        "/api/query",
        "/cgi-bin/command",
        "/rest/command"
    ]
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        for path in test_paths:
            url = f"{base_url}{path}"
            
            try:
                # Test with query parameter
                async with session.get(
                    url,
                    params={"query": "in-a:voltage"},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    status = response.status
                    text = await response.text()
                    
                    if status == 200 and "::" in text:
                        print(f"✅ FOUND WORKING HTTP API: {url}")
                        print(f"   Response: {text}")
                        return url, "query"
                    elif status == 200 and not text.startswith("<!DOCTYPE"):
                        print(f"   {path}: HTTP {status} - {text[:100]}...")
                        
            except Exception as e:
                print(f"   {path}: ERROR - {e}")
    
    print("❌ No HTTP API found on port 80")
    return None, None


async def main():
    """Main test function."""
    print("🧪 CresControl API Discovery Test")
    print("=" * 50)
    
    # Test 1: Confirm WebSocket works (baseline)
    ws_results = await test_websocket_commands()
    
    # Test 2: Look for HTTP API on WebSocket port
    http_ws_url, http_ws_param = await test_http_on_websocket_port()
    
    # Test 3: Look for HTTP API on web port
    http_web_url, http_web_param = await test_http_on_web_port()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 DISCOVERY RESULTS")
    print("=" * 50)
    
    if ws_results:
        print(f"✅ WebSocket API works on port 81:")
        for cmd, value in ws_results.items():
            if value:
                print(f"   • {cmd} = {value}")
    
    if http_ws_url:
        print(f"✅ HTTP API found: {http_ws_url}")
        print(f"   Parameter: {http_ws_param}")
        print(f"   Recommendation: Update API client to use this endpoint")
    elif http_web_url:
        print(f"✅ HTTP API found: {http_web_url}")
        print(f"   Parameter: {http_web_param}")
        print(f"   Recommendation: Update API client to use port 80")
    else:
        print(f"❌ No HTTP API found")
        print(f"💡 Recommendation: Use WebSocket-only approach")
        print(f"   • WebSocket works on port 81 at /websocket")
        print(f"   • Send commands as simple strings (e.g., 'in-a:voltage')")
        print(f"   • Receive responses in format 'parameter::value'")
    
    # Implementation guidance
    print(f"\n💡 IMPLEMENTATION GUIDANCE:")
    if http_ws_url or http_web_url:
        working_url = http_ws_url or http_web_url
        working_param = http_ws_param or http_web_param
        print(f"   1. Update CresControlClient base URL to use correct port")
        print(f"   2. Ensure endpoint is: {working_url.split('/')[-1]}")
        print(f"   3. Use parameter name: {working_param}")
        print(f"   4. Keep WebSocket on port 81 for real-time data")
    else:
        print(f"   1. Modify CresControlClient to use WebSocket-only approach")
        print(f"   2. Remove HTTP polling, use WebSocket for all communication")
        print(f"   3. WebSocket URL: ws://192.168.105.15:81/websocket")
        print(f"   4. Send commands as strings, parse 'param::value' responses")


if __name__ == "__main__":
    asyncio.run(main())