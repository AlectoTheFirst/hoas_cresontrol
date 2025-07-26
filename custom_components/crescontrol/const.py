"""
Constants for the CresControl Home Assistant integration.

This module defines the domain under which the integration operates and
the default polling interval. The polling interval is kept short by
default to provide reasonably up‑to‑date values while keeping the load
on the CresControl device low. Adjust this value in `__init__.py` if
you find that a different interval better suits your installation.
"""

from datetime import timedelta


# The domain of the integration. This is used throughout Home Assistant to
# store and access data related to this integration.
DOMAIN: str = "crescontrol"

# Update interval configuration constants
MIN_UPDATE_INTERVAL: int = 5  # Minimum update interval in seconds
MAX_UPDATE_INTERVAL: int = 300  # Maximum update interval in seconds (5 minutes)
DEFAULT_UPDATE_INTERVAL_SECONDS: int = 10  # Default update interval in seconds

# Default interval to poll the CresControl device for new data. 10 seconds
# strikes a balance between timely updates and network overhead. For faster
# changing systems you may wish to lower this value. Conversely, you can
# increase it if your application is slow to change.
DEFAULT_UPDATE_INTERVAL: timedelta = timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS)

# Configuration field names
CONF_UPDATE_INTERVAL: str = "update_interval"
CONF_WEBSOCKET_ENABLED: str = "websocket_enabled"
CONF_WEBSOCKET_PORT: str = "websocket_port"
CONF_WEBSOCKET_PATH: str = "websocket_path"

# WebSocket configuration defaults
DEFAULT_WEBSOCKET_ENABLED: bool = True
DEFAULT_WEBSOCKET_PORT: int = 81
DEFAULT_WEBSOCKET_PATH: str = "/websocket"

# =============================================================================
# Error Handling and Recovery Constants
# =============================================================================

# Retry and backoff configuration
RETRY_MAX_ATTEMPTS: int = 3  # Maximum retry attempts for failed requests
RETRY_INITIAL_DELAY: float = 1.0  # Initial retry delay in seconds
RETRY_BACKOFF_MULTIPLIER: float = 2.0  # Exponential backoff multiplier
RETRY_MAX_DELAY: float = 30.0  # Maximum retry delay in seconds
RETRY_JITTER_MAX: float = 0.1  # Maximum jitter to add to retry delays (10%)

# Network timeout configuration
DEFAULT_TIMEOUT: int = 30  # Default HTTP request timeout in seconds
CONNECT_TIMEOUT: int = 10  # Connection timeout in seconds
READ_TIMEOUT: int = 30  # Read timeout in seconds
TOTAL_TIMEOUT: int = 45  # Total timeout including retries

# Config flow constants
CONFIG_FLOW_RETRY_ATTEMPTS: int = 2
CONFIG_FLOW_RETRY_DELAY: float = 1.0
CONFIG_FLOW_TIMEOUT: int = 15
CONNECTION_TEST_TIMEOUT: int = 10

# Progressive timeout configuration for degraded connections
TIMEOUT_PROGRESSIVE_MULTIPLIER: float = 1.5  # Multiplier for progressive timeouts
TIMEOUT_PROGRESSIVE_MAX: int = 60  # Maximum progressive timeout in seconds

# Health monitoring configuration
HEALTH_CHECK_INTERVAL: timedelta = timedelta(seconds=60)  # Health check frequency
HEALTH_FAILURE_THRESHOLD: int = 3  # Consecutive failures before marking unhealthy
HEALTH_RECOVERY_THRESHOLD: int = 2  # Consecutive successes before marking healthy
HEALTH_DEGRADED_UPDATE_INTERVAL: timedelta = timedelta(seconds=30)  # Slower polling when degraded

# Connection pool configuration
CONNECTION_POOL_SIZE: int = 10  # Maximum connections in pool
CONNECTION_POOL_TTL: int = 300  # Connection TTL in seconds (5 minutes)
CONNECTION_KEEPALIVE_TIMEOUT: int = 30  # Keep-alive timeout in seconds

# Error pattern tracking
ERROR_PATTERN_WINDOW: timedelta = timedelta(minutes=10)  # Window for tracking error patterns
ERROR_PATTERN_THRESHOLD: int = 5  # Errors in window before adjusting behavior
ERROR_RECOVERY_COOLDOWN: timedelta = timedelta(minutes=5)  # Cooldown before retry after recovery

# Entity availability and state preservation
ENTITY_UNAVAILABLE_THRESHOLD: timedelta = timedelta(minutes=2)  # Time before marking entity unavailable
STATE_PRESERVATION_DURATION: timedelta = timedelta(minutes=10)  # How long to preserve last known state
AVAILABILITY_GRACE_PERIOD: timedelta = timedelta(seconds=30)  # Grace period for temporary failures

# Configuration flow resilience
CONFIG_FLOW_RETRY_ATTEMPTS: int = 2  # Retry attempts during configuration
CONFIG_FLOW_RETRY_DELAY: float = 2.0  # Delay between configuration retries
CONFIG_FLOW_TIMEOUT: int = 15  # Timeout for configuration validation requests

# Diagnostic and monitoring
DIAGNOSTIC_UPDATE_INTERVAL: timedelta = timedelta(seconds=30)  # Diagnostic entity update frequency
CONNECTION_TEST_TIMEOUT: int = 5  # Quick connection test timeout
STARTUP_HEALTH_CHECK_TIMEOUT: int = 60  # Extended timeout for initial health check

# Device status constants
DEVICE_STATUS_ONLINE: str = "online"
DEVICE_STATUS_OFFLINE: str = "offline"
DEVICE_STATUS_DEGRADED: str = "degraded"
DEVICE_STATUS_UNKNOWN: str = "unknown"

# Error severity levels for logging and diagnostics
ERROR_SEVERITY_LOW: str = "low"
ERROR_SEVERITY_MEDIUM: str = "medium"
ERROR_SEVERITY_HIGH: str = "high"
ERROR_SEVERITY_CRITICAL: str = "critical"

# =============================================================================
# WebSocket Configuration Constants
# =============================================================================

# WebSocket connection settings (based on actual device testing)
DEFAULT_WEBSOCKET_PORT: int = 81  # Default WebSocket port (same as HTTP port)
DEFAULT_WEBSOCKET_PATH: str = "/websocket"  # Default WebSocket endpoint path (confirmed working)
DEFAULT_WEBSOCKET_ENABLED: bool = False  # WebSocket disabled by default for backward compatibility

# WebSocket connection timeouts and limits
WEBSOCKET_CONNECT_TIMEOUT: int = 10  # WebSocket connection timeout in seconds
WEBSOCKET_PING_INTERVAL: int = 30  # WebSocket ping interval in seconds
WEBSOCKET_PING_TIMEOUT: int = 10  # WebSocket ping timeout in seconds
WEBSOCKET_CLOSE_TIMEOUT: int = 5  # WebSocket close timeout in seconds
WEBSOCKET_MAX_SIZE: int = 1024 * 1024  # Maximum WebSocket message size (1MB)
WEBSOCKET_MAX_QUEUE: int = 32  # Maximum queued messages

# WebSocket reconnection settings
WEBSOCKET_RECONNECT_DELAY: float = 2.0  # Initial reconnection delay in seconds
WEBSOCKET_RECONNECT_MAX_DELAY: float = 60.0  # Maximum reconnection delay
WEBSOCKET_RECONNECT_MULTIPLIER: float = 1.5  # Backoff multiplier for reconnection delays
WEBSOCKET_RECONNECT_MAX_ATTEMPTS: int = 0  # Maximum reconnection attempts (0 = unlimited)
WEBSOCKET_RECONNECT_JITTER: float = 0.1  # Random jitter factor for reconnection delays

# WebSocket health monitoring
WEBSOCKET_HEARTBEAT_INTERVAL: int = 60  # Heartbeat interval in seconds
WEBSOCKET_HEALTH_CHECK_TIMEOUT: int = 5  # Health check timeout in seconds
WEBSOCKET_CONNECTION_GRACE_PERIOD: int = 30  # Grace period before marking connection as failed

# WebSocket message types and protocols
WEBSOCKET_MESSAGE_TYPE_STATUS: str = "status"
WEBSOCKET_MESSAGE_TYPE_DATA: str = "data"
WEBSOCKET_MESSAGE_TYPE_ERROR: str = "error"
WEBSOCKET_MESSAGE_TYPE_PING: str = "ping"
WEBSOCKET_MESSAGE_TYPE_PONG: str = "pong"
WEBSOCKET_MESSAGE_TYPE_SUBSCRIBE: str = "subscribe"
WEBSOCKET_MESSAGE_TYPE_UNSUBSCRIBE: str = "unsubscribe"

# WebSocket subscription topics
WEBSOCKET_TOPIC_ALL: str = "all"
WEBSOCKET_TOPIC_FAN: str = "fan"
WEBSOCKET_TOPIC_OUTPUTS: str = "outputs"
WEBSOCKET_TOPIC_INPUTS: str = "inputs"
WEBSOCKET_TOPIC_SWITCHES: str = "switches"
WEBSOCKET_TOPIC_PWM: str = "pwm"

# WebSocket status constants
WEBSOCKET_STATUS_CONNECTING: str = "connecting"
WEBSOCKET_STATUS_CONNECTED: str = "connected"
WEBSOCKET_STATUS_DISCONNECTED: str = "disconnected"
WEBSOCKET_STATUS_RECONNECTING: str = "reconnecting"
WEBSOCKET_STATUS_ERROR: str = "error"
WEBSOCKET_STATUS_DISABLED: str = "disabled"

# WebSocket error codes
WEBSOCKET_ERROR_CONNECTION_FAILED: str = "connection_failed"
WEBSOCKET_ERROR_AUTHENTICATION_FAILED: str = "authentication_failed"
WEBSOCKET_ERROR_PROTOCOL_ERROR: str = "protocol_error"
WEBSOCKET_ERROR_MESSAGE_TOO_LARGE: str = "message_too_large"
WEBSOCKET_ERROR_INVALID_MESSAGE: str = "invalid_message"
WEBSOCKET_ERROR_SUBSCRIPTION_FAILED: str = "subscription_failed"

# WebSocket performance and optimization
WEBSOCKET_COMPRESSION_ENABLED: bool = True  # Enable WebSocket compression
WEBSOCKET_BUFFER_SIZE: int = 8192  # WebSocket buffer size
WEBSOCKET_READ_TIMEOUT: int = 30  # Read timeout for WebSocket messages
WEBSOCKET_WRITE_TIMEOUT: int = 10  # Write timeout for WebSocket messages

# WebSocket fallback behavior
WEBSOCKET_FALLBACK_TO_HTTP: bool = True  # Fall back to HTTP polling if WebSocket fails
WEBSOCKET_FALLBACK_DELAY: int = 60  # Delay before trying WebSocket again after fallback
WEBSOCKET_HTTP_HYBRID_MODE: bool = True  # Allow both WebSocket and HTTP polling simultaneously

# =============================================================================
# Fan Entity Constants
# =============================================================================

# Fan parameter names
FAN_PARAM_ENABLED: str = "fan:enabled"
FAN_PARAM_DUTY_CYCLE: str = "fan:duty-cycle"
FAN_PARAM_DUTY_CYCLE_MIN: str = "fan:duty-cycle-min"
FAN_PARAM_RPM: str = "fan:rpm"

# Fan duty cycle limits and validation
FAN_DUTY_CYCLE_MIN: float = 0.0  # Minimum duty cycle percentage
FAN_DUTY_CYCLE_MAX: float = 100.0  # Maximum duty cycle percentage
FAN_DUTY_CYCLE_DEFAULT_MIN: float = 20.0  # Default minimum for startup reliability
FAN_DUTY_CYCLE_STEP: float = 1.0  # Step size for duty cycle adjustments

# Fan speed presets (percentage values)
FAN_SPEED_OFF: int = 0
FAN_SPEED_LOW: int = 25
FAN_SPEED_MEDIUM: int = 50
FAN_SPEED_HIGH: int = 75
FAN_SPEED_MAXIMUM: int = 100

# Fan validation limits
FAN_RPM_MAX: int = 10000  # Maximum reasonable RPM for validation
FAN_DUTY_CYCLE_TOLERANCE: float = 0.1  # Tolerance for duty cycle comparisons

# Fan device information
FAN_DEVICE_CLASS: str = "fan"
FAN_ICON: str = "mdi:fan"
FAN_ICON_OFF: str = "mdi:fan-off"

# =============================================================================
# PWM Control Constants
# =============================================================================

# PWM parameter names for outputs A-B (only outputs A-B support PWM)
PWM_PARAM_OUT_A_ENABLED: str = "out-a:pwm-enabled"
PWM_PARAM_OUT_B_ENABLED: str = "out-b:pwm-enabled"
PWM_PARAM_OUT_A_DUTY_CYCLE: str = "out-a:duty-cycle"
PWM_PARAM_OUT_B_DUTY_CYCLE: str = "out-b:duty-cycle"
PWM_PARAM_OUT_A_FREQUENCY: str = "out-a:pwm-frequency"
PWM_PARAM_OUT_B_FREQUENCY: str = "out-b:pwm-frequency"

# PWM parameter names for switches (12V, 24V-A, 24V-B support PWM)
PWM_PARAM_SWITCH_12V_ENABLED: str = "switch-12v:pwm-enabled"
PWM_PARAM_SWITCH_24V_A_ENABLED: str = "switch-24v-a:pwm-enabled"
PWM_PARAM_SWITCH_24V_B_ENABLED: str = "switch-24v-b:pwm-enabled"
PWM_PARAM_SWITCH_12V_DUTY_CYCLE: str = "switch-12v:duty-cycle"
PWM_PARAM_SWITCH_24V_A_DUTY_CYCLE: str = "switch-24v-a:duty-cycle"
PWM_PARAM_SWITCH_24V_B_DUTY_CYCLE: str = "switch-24v-b:duty-cycle"
PWM_PARAM_SWITCH_12V_FREQUENCY: str = "switch-12v:pwm-frequency"
PWM_PARAM_SWITCH_24V_A_FREQUENCY: str = "switch-24v-a:pwm-frequency"
PWM_PARAM_SWITCH_24V_B_FREQUENCY: str = "switch-24v-b:pwm-frequency"

# PWM duty cycle limits and validation
PWM_DUTY_CYCLE_MIN: float = 0.0  # Minimum duty cycle percentage
PWM_DUTY_CYCLE_MAX: float = 100.0  # Maximum duty cycle percentage
PWM_DUTY_CYCLE_STEP: float = 0.1  # Step size for duty cycle adjustments
PWM_DUTY_CYCLE_DEFAULT: float = 0.0  # Default duty cycle when PWM is enabled

# PWM frequency limits and validation (based on crescontrol-0.2)
PWM_FREQUENCY_MIN: float = 0.0  # Minimum PWM frequency in Hz
PWM_FREQUENCY_MAX: float = 1000.0  # Maximum PWM frequency in Hz (1kHz)
PWM_FREQUENCY_STEP: float = 1.0  # Step size for frequency adjustments
PWM_FREQUENCY_DEFAULT: float = 100.0  # Default PWM frequency (100Hz)

# PWM validation tolerances
PWM_DUTY_CYCLE_TOLERANCE: float = 0.1  # Tolerance for duty cycle comparisons
PWM_FREQUENCY_TOLERANCE: float = 1.0  # Tolerance for frequency comparisons

# PWM device capability lists (only certain outputs and switches support PWM)
PWM_CAPABLE_OUTPUTS: list[str] = ["out-a", "out-b"]  # Only outputs A-B support PWM
PWM_CAPABLE_SWITCHES: list[str] = ["switch-12v", "switch-24v-a", "switch-24v-b"]  # All switches support PWM

# PWM icon assignments
PWM_ICON_ENABLED: str = "mdi:toggle-switch"
PWM_ICON_DUTY_CYCLE: str = "mdi:pulse"
PWM_ICON_FREQUENCY: str = "mdi:sine-wave"

# PWM error messages
PWM_ERROR_INVALID_DUTY_CYCLE: str = "PWM duty cycle must be between 0 and 100 percent"
PWM_ERROR_INVALID_FREQUENCY: str = "PWM frequency must be between 0 and 1000 Hz"
PWM_ERROR_OUTPUT_NOT_CAPABLE: str = "Output does not support PWM control"
PWM_ERROR_SWITCH_NOT_CAPABLE: str = "Switch does not support PWM control"
PWM_ERROR_PWM_NOT_ENABLED: str = "PWM mode must be enabled before setting duty cycle or frequency"

# PWM safety and validation constants
PWM_MAX_BATCH_OPERATIONS: int = 10  # Maximum PWM operations in a single batch
PWM_VALIDATION_TIMEOUT: float = 5.0  # Timeout for PWM parameter validation
PWM_SETTLE_TIME: float = 0.1  # Time to wait for PWM settings to settle (100ms)
