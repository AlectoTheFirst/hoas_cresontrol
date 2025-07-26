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
