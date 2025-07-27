#!/usr/bin/env python3
"""
Final test of all discovered CO2 and climate sensor parameters.
"""

import asyncio
import aiohttp

async def test_all_sensors():
    """Test all discovered sensor parameters."""
    
    print("Final CO2 and Climate Sensor Test")
    print("Device: 192.168.105.15:81")
    print("=" * 50)
    
    # All discovered working parameters
    sensor_params = [
        ("extension:climate-2011:temperature", "Climate Temperature", "°C"),
        ("extension:climate-2011:humidity", "Climate Humidity", "%"),
        ("extension:co2-2006:co2-concentration", "CO2 Concentration", "ppm"),
        ("extension:co2-2006:temperature", "CO2 Temperature", "°C"),
    ]
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect('ws://192.168.105.15:81/websocket', timeout=10) as ws:
            
            print("Testing individual parameters:")
            print("-" * 30)
            
            working_params = []
            
            for param, name, unit in sensor_params:
                await ws.send_str(param)
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=3)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        response = msg.data.strip()
                        
                        if "::" in response:
                            _, value = response.split("::", 1)
                            value = value.strip()
                            
                            if not (value.startswith('{"error"') or 
                                   value.lower() in ['error', 'n/a', 'unknown']):
                                print(f"✅ {name:<20}: {value} {unit}")
                                working_params.append((param, value, unit))
                            else:
                                print(f"❌ {name:<20}: {value}")
                        
                except asyncio.TimeoutError:
                    print(f"⏱️ {name:<20}: TIMEOUT")
                
                await asyncio.sleep(0.3)
            
            # Test combined query
            print(f"\nTesting combined query:")
            print("-" * 30)
            
            combined_query = ";".join([param for param, _, _ in sensor_params])
            await ws.send_str(combined_query)
            
            try:
                msg = await asyncio.wait_for(ws.receive(), timeout=5)
                response = msg.data.strip()
                print(f"Combined response: {response}")
                
                if "::" in response:
                    # Parse combined response
                    _, values = response.split("::", 1)
                    value_list = values.split(";")
                    
                    print(f"\nParsed combined values:")
                    for i, (param, name, unit) in enumerate(sensor_params):
                        if i < len(value_list):
                            value = value_list[i].strip()
                            if not (value.startswith('{"error"') or 
                                   value.lower() in ['error', 'n/a', 'unknown']):
                                print(f"  {name}: {value} {unit}")
                            else:
                                print(f"  {name}: ERROR")
                
            except asyncio.TimeoutError:
                print("Combined query timeout")
            
            return working_params

async def main():
    """Run final sensor test."""
    working_params = await test_all_sensors()
    
    print("\n" + "=" * 50)
    print("INTEGRATION UPDATE SUMMARY")
    print("=" * 50)
    
    if working_params:
        print(f"\n✅ Found {len(working_params)} working sensor parameters:")
        print("\nUpdate custom_components/crescontrol/sensor.py with:")
        print("```python")
        print("CORE_SENSORS = [")
        print("    # Existing sensors...")
        print("    ")
        
        for param, value, unit in working_params:
            param_parts = param.split(":")
            sensor_name = param_parts[-1].replace("-", " ").title()
            device_class = ""
            state_class = "SensorStateClass.MEASUREMENT"
            icon = "mdi:help"
            
            if "temperature" in param:
                device_class = "SensorDeviceClass.TEMPERATURE"
                unit_const = "UnitOfTemperature.CELSIUS"
                icon = "mdi:thermometer"
            elif "humidity" in param:
                device_class = "SensorDeviceClass.HUMIDITY" 
                unit_const = "PERCENTAGE"
                icon = "mdi:water-percent"
            elif "co2" in param:
                device_class = "SensorDeviceClass.CO2"
                unit_const = "CONCENTRATION_PARTS_PER_MILLION"
                icon = "mdi:molecule-co2"
            
            print(f'    {{')
            print(f'        "key": "{param}",')
            print(f'        "name": "{sensor_name}",')
            print(f'        "unit": {unit_const},')
            print(f'        "device_class": {device_class},')
            print(f'        "state_class": {state_class},')
            print(f'        "icon": "{icon}",')
            print(f'    }},')
        
        print("]")
        print("```")
        
        print(f"\nAlso update websocket_client.py to subscribe to these parameters:")
        print("```python")
        for param, _, _ in working_params:
            print(f"                '{param}',")
        print("```")
        
    else:
        print("\n❌ No working parameters found.")

if __name__ == "__main__":
    asyncio.run(main())