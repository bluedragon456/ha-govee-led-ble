"""Constants for HA Govee LED BLE."""

from dataclasses import dataclass

DOMAIN = "ha_govee_led_ble"
CONF_MODEL = "model"


@dataclass(frozen=True)
class ModelProfile:
    name: str
    state_readable: bool = False
    scene_source: str = "none"
    supports_video_mode: bool = False
    supports_video_sound_effects: bool = False
    music_modes: tuple[str, ...] = ()
    supports_music_color: bool = False
    supports_music_style: bool = False
    supports_music_params: bool = False
    supports_white_brightness: bool = False
    static_readback_echoes_color: bool = False
    supports_diy: bool = False
    supports_timers: bool = False
    supports_poweroff_memory: bool = False
    segment_count: int = 0
    supports_segment_writes: bool = False

    @property
    def supports_segments(self) -> bool:
        return self.segment_count > 0 and self.supports_segment_writes

    @property
    def supports_music_mode(self) -> bool:
        return bool(self.music_modes)

    @property
    def custom_effect_kinds(self) -> frozenset[str]:
        kinds = {"segments"} if self.supports_segments else set()
        if self.supports_diy:
            kinds.update({"sketch", "vibrant", "flat", "combo"})
        return frozenset(kinds)


MUSIC_MODES: dict[str, int] = {
    "energetic": 0x05,
    "rhythm": 0x03,
    "spectrum": 0x04,
    "rolling": 0x06,
    "separation": 0x32,
    "hopping": 0x33,
    "piano keys": 0x34,
    "fountain": 0x35,
    "day and night": 0x37,
    "bloom": 0x30,
    "shiny": 0x31,
}

# Single source of truth for the ``select.music_mode`` options: HA slugs (underscored, no
# "off") mapped to their live-confirmed mode codes. Distinct from ``MUSIC_MODES`` above, whose
# spaced display names remain the parse/service vocabulary.
MUSIC_MODE_SLUGS: dict[str, int] = {
    "energetic": 0x05,
    "rhythm": 0x03,
    "spectrum": 0x04,
    "rolling": 0x06,
    "separation": 0x32,
    "hopping": 0x33,
    "piano_keys": 0x34,
    "fountain": 0x35,
    "day_and_night": 0x37,
    "bloom": 0x30,
    "shiny": 0x31,
}

_H6199_MUSIC_MODES = ("energetic", "rhythm", "spectrum", "rolling")


_H617X_PROFILE = ModelProfile(
    "H617A/H617E LED Strip",
    state_readable=True,
    scene_source="api",
    music_modes=tuple(MUSIC_MODE_SLUGS),
    supports_music_color=True,
    supports_music_style=True,
    supports_music_params=True,
    supports_diy=True,
    supports_timers=True,
    segment_count=15,
    supports_segment_writes=True,
    # supports_white_brightness stays false, and NOT because the command does nothing. Driven
    # directly on 2026-07-31 it dims the strip and compounds with the whole-strip opcode 0x04
    # rather than duplicating it (command_write::static_brightness). Two things block exposing
    # it through this service. It has no read-back, and async_set_white_brightness verifies
    # through _refresh_with_retry, which raises when the field is never observed. And the
    # service means "the level of the white mode" and forces ColorMode.COLOR_TEMP, which is not
    # what the frame does here: on this model it is a relative brightness that multiplies the
    # master. Exposing that axis needs its own control, which is a feature, not a correction.
)


MODEL_PROFILES: dict[str, ModelProfile] = {
    "H617A": _H617X_PROFILE,
    "H617E": _H617X_PROFILE,
    "H6199": ModelProfile(
        "H6199 DreamView T1",
        state_readable=True,
        supports_video_mode=True,
        supports_video_sound_effects=True,
        music_modes=_H6199_MUSIC_MODES,
        supports_white_brightness=True,
        # UNVERIFIED, and deliberately named so it can be falsified. The parser assumed this of
        # every model until the H617A disproved it (status_reply::cm_static: the byte after the
        # mode mirrors the 33 a3 register, and no colour is ever echoed). That evidence is H617A
        # only and says nothing about this model, so the old assumption is kept here rather than
        # silently extended or silently dropped. supports_white_brightness depends on it: the
        # write is verified against a read-back, so if the H6199 also echoes nothing, that service
        # raises. Settle it in the H6199 discovery run.
        static_readback_echoes_color=True,
        # Carries no protocol claim. supports_segment_writes is unset, so supports_segments is False
        # and nothing addresses H6199 segments on the wire; this value only sizes the diagnostic
        # preview image, which is created for every model. It is NOT 38 on purpose. The device does
        # answer 38 to aa 40, but that reply has been positively excluded as an app segment count
        # (an external H7015 reads 30 against 15 segments proven by an exhaustive per-bit sweep), so
        # copying it in would re-assert the very reading we disproved. The 38 is also not capture-
        # backed: the vendor app never issues aa 40 to this model, so it came from a direct firmware
        # register read. See status_reply::unit_count_body. The real number is a question for the
        # H6199 discovery run, which owns that model's wire behaviour.
        segment_count=15,
    ),
}

UNSUPPORTED_PROFILE = ModelProfile("Unsupported Govee device")


def resolve_model(model: str) -> str | None:
    candidate = model.strip().upper()
    return next((known for known in MODEL_PROFILES if candidate.startswith(known)), None)


def get_profile(model: str) -> ModelProfile:
    resolved = resolve_model(model)
    return MODEL_PROFILES[resolved] if resolved is not None else UNSUPPORTED_PROFILE
