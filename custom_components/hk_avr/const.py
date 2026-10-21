"""Constants for the AVR 151S integration."""

DOMAIN = "hk_avr"
DEFAULT_NAME = "Harman Kardon AVR 151S"
DEFAULT_PORT = 10025
DEFAULT_WAKE_TIMEOUT = 45
CONF_WAKE_REMOTE = "wake_remote"
CONF_WAKE_DEVICE = "wake_device"
CONF_WAKE_COMMAND = "wake_command"
CONF_WAKE_TIMEOUT = "wake_timeout"
DEFAULT_WAKE_DEVICE = "harman_kardon"
DEFAULT_WAKE_COMMAND = "power_on"
SOURCES = (
    "Disc", "STB", "Cable Sat", "Media Server", "DVR", "Radio",
    "TV", "USB", "Game", "Home Network", "AUX",
)
