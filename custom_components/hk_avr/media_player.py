"""Receiver controls with learned-command IR wake support."""

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_WAKE_REMOTE, SOURCES
from .entity import AvrEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([AvrMediaPlayer(entry.runtime_data)])


class AvrMediaPlayer(AvrEntity, MediaPlayerEntity):
    """Keep turn-on callable while asleep when an IR remote is configured."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_assumed_state = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )
    _attr_source_list = list(SOURCES)

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "receiver")

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data.reachable
                    or self.coordinator.entry.data.get(CONF_WAKE_REMOTE))

    @property
    def state(self) -> MediaPlayerState | None:
        power = self.coordinator.data.power
        if power == "on":
            return MediaPlayerState.ON
        if power == "off":
            return MediaPlayerState.OFF
        return None

    @property
    def source(self) -> str | None:
        return self.coordinator.data.source

    @property
    def extra_state_attributes(self) -> dict:
        return {"network_reachable": self.coordinator.data.reachable,
                "state_feedback": "optimistic",
                "last_command_transport": self.coordinator.data.last_transport}

    async def async_turn_on(self) -> None:
        await self.coordinator.async_command("power-on")

    async def async_turn_off(self) -> None:
        await self.coordinator.async_command("power-off")

    async def async_volume_up(self) -> None:
        await self.coordinator.async_command("volume-up")

    async def async_volume_down(self) -> None:
        await self.coordinator.async_command("volume-down")

    async def async_select_source(self, source: str) -> None:
        await self.coordinator.async_command("source-selection", source)

    async def async_media_play(self) -> None:
        await self.coordinator.async_command("play")

    async def async_media_pause(self) -> None:
        await self.coordinator.async_command("pause")

    async def async_media_next_track(self) -> None:
        await self.coordinator.async_command("next")

    async def async_media_previous_track(self) -> None:
        await self.coordinator.async_command("previous")
