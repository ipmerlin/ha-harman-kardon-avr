"""Constants for the AVR 151S integration."""

DOMAIN = "hk_avr"
DEFAULT_NAME = "Harman Kardon AVR 151S"
DEFAULT_PORT = 10025
DEFAULT_WAKE_TIMEOUT = 45
CONF_WAKE_REMOTE = "wake_remote"
CONF_WAKE_DEVICE = "wake_device"
CONF_WAKE_COMMAND = "wake_command"
CONF_WAKE_TIMEOUT = "wake_timeout"
WAKE_REMOTE_INTEGRATIONS = ("broadlink", "xiaomi_ir")
DEFAULT_WAKE_DEVICE = "harman_kardon"
DEFAULT_WAKE_COMMAND = "power_on"
SOURCES = (
    "Disc", "STB", "Cable Sat", "Media Server", "DVR", "Radio",
    "TV", "USB", "Game", "Home Network", "AUX",
)

# Names verified in KarimGeiger/HKAPI lib/Actions; AVR 151S testing is pending.
NETWORK_BUTTONS = {
    "mute_toggle": ("mute-toggle", "mdi:volume-mute"),
    "play": ("play", "mdi:play"),
    "pause": ("pause", "mdi:pause"),
    "next": ("next", "mdi:skip-next"),
    "previous": ("previous", "mdi:skip-previous"),
    "forward": ("forward", "mdi:fast-forward"),
    "reverse": ("reverse", "mdi:rewind"),
    "up": ("up", "mdi:arrow-up"),
    "down": ("down", "mdi:arrow-down"),
    "left": ("left", "mdi:arrow-left"),
    "right": ("right", "mdi:arrow-right"),
    "ok": ("ok", "mdi:check-circle-outline"),
    "back": ("back", "mdi:arrow-u-left-top"),
    "home": ("home", "mdi:home"),
    "info": ("info", "mdi:information-outline"),
    "options": ("options", "mdi:tune"),
    "sleep": ("sleep", "mdi:power-sleep"),
}
REMOTE_COMMANDS = {
    **{key: command for key, (command, _) in NETWORK_BUTTONS.items()},
    "volume_up": "volume-up", "volume_down": "volume-down",
}
