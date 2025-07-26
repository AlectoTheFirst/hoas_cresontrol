# CresControl Home Assistant Integration

This custom integration adds support for the [CresControl cannabis grow controller](https://wiki.cre.science/de/crescontrol/crescontrol-api) to Home Assistant.  It exposes the controller’s analog inputs and outputs, fan and auxiliary power rails as native Home Assistant entities.  You can monitor voltages, control output levels and toggle switches directly from the Home Assistant UI.

## Features

* **Sensors**: report the voltages of the two analog inputs (`in‑a` and `in‑b`) and the fan rotation speed (`fan:rpm`).
* **Switches**: toggle the internal fan, 12 V rail, 24 V rails A/B and enable or disable each analog output channel (A–F).
* **Numbers**: set the output voltage of each analog output (A–F) with a resolution of 0.01 V.  The default range is 0–10 V; adjust this in `number.py` if your CresControl is configured differently.

The integration communicates with the device over its HTTP API using the `/command` endpoint.  It polls all required parameters in a single request every 10 seconds by default.  When you change a value from Home Assistant, the new value is written back immediately and a refresh is triggered to keep all entities in sync.

## Installation via HACS

1. Copy the `custom_components/crescontrol` folder from this repository into the `custom_components` directory of your Home Assistant configuration.  If you are using HACS, you can add this repository as a custom integration and HACS will handle installation for you.
2. Restart Home Assistant to discover the new integration.
3. Navigate to **Settings → Devices & Services → Add Integration** and search for “CresControl”.  Enter the IP address or hostname of your CresControl device when prompted.  Home Assistant will verify the connection and create the entities.

## Known limitations

* The integration uses HTTP polling rather than WebSockets.  Real‑time updates via the CresControl subscription feature are not yet implemented.
* Authentication is not currently supported.  If future CresControl firmware requires tokens or credentials, this integration will need to be extended.
* Only a subset of the available CresControl parameters are exposed.  You can add additional sensors, switches or numbers by editing `SENSOR_DEFINITIONS`, `SWITCH_DEFINITIONS` and `NUMBER_DEFINITIONS` in the respective platform modules.

## Contributing

Contributions are welcome!  Please open issues or pull requests on [GitHub](https://github.com/cre-science/crescontrol-homeassistant) if you encounter problems or have suggestions for improvements.

## Credits

This integration was developed based on the CresControl API documentation【26746980507384†L60-L109】 and the Home Assistant developer guidelines【303200071509333†L83-L116】.  Thanks to the Crescience team for providing an open API and to the Home Assistant community for excellent documentation and tooling.
