# Implementation Plan

- [x] 1. Fix HTTP API client and test connectivity
  - Create simplified HTTP client that works with the device
  - Test different endpoint formats to find working API path
  - Implement basic command sending and response parsing
  - _Requirements: 1.1, 1.4_

- [x] 2. Implement working WebSocket client for real-time data
  - Create WebSocket client that connects to ws://host:81/websocket
  - Implement message parsing for parameter::value format
  - Add data handler callbacks for coordinator integration
  - Test subscription to multiple parameters
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Create hybrid coordinator using WebSocket data with HTTP fallback
  - Implement coordinator that prioritizes WebSocket data
  - Add HTTP polling fallback when WebSocket unavailable
  - Integrate WebSocket data handler with coordinator updates
  - Implement basic error handling without complex health monitoring
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 4. Simplify and fix entity platform implementations
  - Reduce sensor definitions to core parameters only
  - Remove complex error handling and state preservation from entities
  - Fix entity unique IDs and device associations
  - Ensure entities use standard Home Assistant patterns
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 6.3_

- [ ] 5. Fix configuration flow and device setup
  - Simplify config flow to basic host validation
  - Remove complex WebSocket testing from config flow
  - Test connectivity using simple HTTP or WebSocket ping
  - Ensure proper device registry integration
  - _Requirements: 1.1, 1.4, 6.4_

- [ ] 6. Implement core sensor entities
  - Create sensors for in-a:voltage, in-b:voltage
  - Add fan RPM sensor (handle error responses gracefully)
  - Implement proper value parsing and validation
  - Test real-time updates via WebSocket
  - _Requirements: 2.1_

- [ ] 7. Implement core switch entities
  - Create switches for fan:enabled, switch-12v:enabled
  - Add switches for 24V rails and output enables
  - Implement proper state reading and command sending
  - Test switch operations via HTTP commands
  - _Requirements: 2.3_

- [ ] 8. Implement core number entities for voltage control
  - Create number entities for output voltages (A-F)
  - Set proper min/max values and step sizes
  - Implement value setting via HTTP commands
  - Test voltage control and real-time feedback
  - _Requirements: 2.4_

- [ ] 9. Fix integration loading and HACS compatibility
  - Review manifest.json for proper dependencies
  - Ensure all imports are available in Home Assistant OS
  - Remove any problematic dependencies or complex features
  - Test integration loading in clean Home Assistant environment
  - _Requirements: 1.1, 1.2, 1.3, 6.1, 6.2_

- [ ] 10. Add basic error handling and logging
  - Implement simple retry logic for HTTP requests
  - Add proper exception handling for WebSocket connections
  - Include debug logging for troubleshooting
  - Ensure graceful degradation when device unavailable
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 11. Test complete integration functionality
  - Test integration installation via HACS
  - Verify all entities appear and function correctly
  - Test real-time updates via WebSocket
  - Test control commands via HTTP
  - Validate against real device at 192.168.105.15:81
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 12. Add WebSocket reconnection and fallback logic
  - Implement automatic WebSocket reconnection on disconnect
  - Add proper fallback to HTTP polling when WebSocket fails
  - Handle WebSocket connection errors gracefully
  - Test resilience during network interruptions
  - _Requirements: 5.1, 5.2, 5.3, 5.5_

- [ ] 13. Optimize entity definitions and reduce complexity
  - Remove diagnostic and system entities that may cause loading issues
  - Simplify entity attribute handling
  - Remove complex state preservation logic
  - Focus on core functionality only
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 14. Add comprehensive testing against real device
  - Test all HTTP command formats and endpoints
  - Validate WebSocket message parsing and subscriptions
  - Test entity state updates and control commands
  - Verify integration stability over extended periods
  - _Requirements: 1.4, 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 15. Document working API endpoints and message formats
  - Document confirmed working HTTP endpoints
  - Document WebSocket message formats and subscription methods
  - Create troubleshooting guide for common issues
  - Add examples of working configurations
  - _Requirements: 6.1, 6.2_