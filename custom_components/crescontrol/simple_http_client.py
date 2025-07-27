"""
Simplified HTTP client for CresControl device.
This replaces the complex API client with a working implementation.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from aiohttp import ClientSession, ClientTimeout, ClientError

_LOGGER = logging.getLogger(__name__)


class SimpleCresControlHTTPClient:
    """Simplified HTTP client that actually works with CresControl device."""
    
    def __init__(self, host: str, session: ClientSession, port: int = 80):
        """Initialize the client.
        
        Args:
            host: Device IP address
            session: aiohttp ClientSession  
            port: HTTP port (80 for web interface, 81 is WebSocket only)
        """
        self.host = host
        self.port = port
        self.session = session
        self.base_url = f"http://{host}:{port}"
        
    async def test_connectivity(self) -> bool:
        """Test if we can connect to the device.
        
        Returns:
            True if device is reachable, False otherwise
        """
        try:
            async with self.session.get(
                self.base_url,
                timeout=ClientTimeout(total=5)
            ) as response:
                return response.status == 200
        except Exception as e:
            _LOGGER.warning("Connectivity test failed: %s", e)
            return False
    
    async def send_command_via_websocket(self, command: str) -> Optional[str]:
        """Send command via WebSocket (the working method).
        
        This is a fallback method that uses WebSocket since HTTP API
        may not be available on this device.
        
        Args:
            command: Command to send (e.g., "in-a:voltage")
            
        Returns:
            Response value or None if failed
        """
        ws_url = f"ws://{self.host}:81/websocket"
        
        try:
            async with self.session.ws_connect(ws_url, timeout=30) as ws:
                # Send command
                await ws.send_str(command)
                
                # Wait for response
                msg = await asyncio.wait_for(ws.receive(), timeout=5)
                if msg.type.name == 'TEXT':
                    response = msg.data
                    
                    # Parse CresControl format: "parameter::value"
                    if "::" in response:
                        param, value = response.split("::", 1)
                        if param.strip() == command:
                            return value.strip()
                    
                    return response
                    
        except Exception as e:
            _LOGGER.error("WebSocket command failed: %s", e)
            return None
    
    async def get_value(self, parameter: str) -> Optional[str]:
        """Get a parameter value from the device.
        
        Args:
            parameter: Parameter name (e.g., "in-a:voltage")
            
        Returns:
            Parameter value or None if failed
        """
        # For now, use WebSocket since HTTP API endpoint is unclear
        return await self.send_command_via_websocket(parameter)
    
    async def set_value(self, parameter: str, value: Any) -> bool:
        """Set a parameter value on the device.
        
        Args:
            parameter: Parameter name (e.g., "fan:enabled")
            value: Value to set
            
        Returns:
            True if successful, False otherwise
        """
        # Convert value to string format expected by device
        if isinstance(value, bool):
            value_str = "1" if value else "0"
        else:
            value_str = str(value)
        
        command = f"{parameter}={value_str}"
        result = await self.send_command_via_websocket(command)
        return result is not None
    
    async def get_multiple_values(self, parameters: list[str]) -> Dict[str, str]:
        """Get multiple parameter values efficiently.
        
        Args:
            parameters: List of parameter names
            
        Returns:
            Dict mapping parameter names to values
        """
        results = {}
        
        # For WebSocket, we need to send commands one by one
        for param in parameters:
            value = await self.get_value(param)
            if value is not None:
                results[param] = value
                
        return results


async def test_simple_client():
    """Test the simplified client."""
    async with ClientSession() as session:
        client = SimpleCresControlHTTPClient("192.168.105.15", session)
        
        print("Testing connectivity...")
        connected = await client.test_connectivity()
        print(f"HTTP connectivity: {connected}")
        
        print("\nTesting WebSocket commands...")
        test_commands = [
            "in-a:voltage",
            "in-b:voltage", 
            "fan:enabled",
            "fan:rpm"
        ]
        
        for cmd in test_commands:
            result = await client.get_value(cmd)
            print(f"{cmd}: {result}")


if __name__ == "__main__":
    asyncio.run(test_simple_client())