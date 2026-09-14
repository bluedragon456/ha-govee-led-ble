"""Qualified music requests, prepared in full before any control side effects."""

from collections.abc import Mapping, Sequence
from typing import Any

from kaitaistruct import KaitaiStructError

from .const import MUSIC_MODE_SLUGS, ModelProfile, get_profile
from .generated_protocol_adapter import build_music_mode, build_power, encode_music_parameters, music_default_palette
from .music_semantics import compile_music_parameters, music_parameters_available, music_params_for_mode, music_variant
from .transport import fragment_a3


def build_music_params(
    mode: int,
    parameters: Mapping[str, Any],
    palette: list[tuple[int, int, int]] | None = None,
    *,
    profile: ModelProfile,
    calm: bool = False,
) -> list[bytes]:
    if type(mode) is not int or mode not in (MUSIC_MODE_SLUGS[slug] for slug in profile.music_modes):
        raise ValueError("unsupported music mode")
    if not isinstance(calm, bool):
        raise ValueError("music style must be a boolean")
    variant = music_variant(profile, mode)
    compiled = compile_music_parameters(parameters, mode, profile)
    if variant is None or variant.layout is None:
        if compiled or palette is not None or (variant is not None and (variant.template or variant.parameters)):
            raise ValueError("music parameter layout is unqualified")
        return []
    if not music_parameters_available(profile, variant):
        if palette is not None:
            raise ValueError("music parameters require known physical IC count")
        return []
    try:
        body = encode_music_parameters(
            variant, compiled, palette=palette, calm=calm, physical_ic_count=profile.physical_ic_count
        )
    except (KaitaiStructError, EOFError) as error:
        raise ValueError("music parameter layout or palette is invalid") from error
    return fragment_a3(0x41, body)


def prepare_music_request(
    model: str,
    mode: str,
    sensitivity: int,
    colour: tuple[int, int, int] | None,
    calm: bool,
    parameters: Mapping[str, Any],
    *,
    include_parameters: bool = True,
    profile: ModelProfile | None = None,
    palette: Sequence[tuple[int, int, int]] | None = None,
) -> tuple[bytes, ...]:
    profile = get_profile(model) if profile is None else profile
    if mode not in profile.music_modes:
        raise ValueError(f"{model} does not support music mode {mode}")
    mode_code = MUSIC_MODE_SLUGS[mode]
    variant = music_variant(profile, mode_code)
    if palette is not None and (variant is None or variant.palette_bounds is None):
        raise ValueError("music mode does not support an authored palette")
    if palette is not None and not include_parameters:
        raise ValueError("music palette requires a parameter upload")
    companion = (
        build_music_params(
            mode_code, parameters, None if palette is None else list(palette), profile=profile, calm=calm
        )
        if include_parameters
        else []
    )
    selector = build_music_mode(mode_code, sensitivity, colour, calm, model)
    control = (*companion, selector) if profile.music_upload_before_selector else (selector, *companion)
    return (build_power(True, model), *control)


def resolve_music_profile(
    model: str,
    mode: str,
    sensitivity: int,
    colour: tuple[int, int, int] | None,
    calm: bool | None,
    parameters: Mapping[str, Any],
    *,
    profile: ModelProfile | None = None,
    palette: Sequence[tuple[int, int, int]] | None = None,
) -> tuple[bool, dict[str, int | bool | str], tuple[bytes, ...]]:
    """Resolve and validate the complete target request without changing device state."""
    profile = get_profile(model) if profile is None else profile
    if mode not in profile.music_modes:
        raise ValueError(f"{model} does not support music mode {mode}")
    variant = music_variant(profile, MUSIC_MODE_SLUGS[mode])
    if calm is not None and (variant is None or not variant.supports_style):
        raise ValueError(f"music mode {mode} does not support a style setting")
    if colour is not None and not (profile.supports_music_color and (variant is None or variant.supports_fixed_colour)):
        raise ValueError(f"{model} does not support a fixed music colour")
    resolved_calm = calm if calm is not None else variant.calm_default if variant and variant.supports_style else False
    compiled = compile_music_parameters(parameters, MUSIC_MODE_SLUGS[mode], profile)
    packets = prepare_music_request(
        model, mode, sensitivity, colour, resolved_calm, compiled, profile=profile, palette=palette
    )
    return resolved_calm, compiled, packets


def prepare_music_profile_writes(
    model: str,
    mode: str,
    sensitivity: int,
    colour: tuple[int, int, int] | None,
    calm: bool,
    parameters: Mapping[str, Any],
    *,
    profile: ModelProfile | None = None,
    include_parameters: bool = True,
    palette: Sequence[tuple[int, int, int]] | None = None,
) -> tuple[tuple[bytes, dict[str, Any]], ...]:
    """Pair validated packets with retained state installed at their physical attempt."""
    profile = get_profile(model) if profile is None else profile
    packets = prepare_music_request(
        model,
        mode,
        sensitivity,
        colour,
        calm,
        parameters,
        profile=profile,
        include_parameters=include_parameters,
        palette=palette,
    )
    states: list[dict[str, Any]] = [{} for _ in packets]
    states[0] = {"is_on": True}
    selector_index = len(packets) - 1 if profile.music_upload_before_selector else 1
    states[selector_index] = {
        "music_sensitivity": sensitivity,
        "music_color": colour,
        "music_calm": calm,
        "music_mode": mode,
        "video_mode": "off",
        "effect": None,
        "diy_code": None,
    }
    variant = music_variant(profile, MUSIC_MODE_SLUGS[mode])
    if variant and variant.layout == "h6099_music_parameters":
        # New selectors carry neither style nor fixed colour, even without an upload.
        del states[selector_index]["music_calm"]
        del states[selector_index]["music_color"]
    if len(packets) > 2:
        # Earlier fragments cannot complete the companion; a final attempt may.
        companion_index = len(packets) - 2 if profile.music_upload_before_selector else len(packets) - 1
        states[companion_index] = {
            spec.key: parameters.get(spec.profile_key, spec.default)
            for spec in music_params_for_mode(MUSIC_MODE_SLUGS[mode], profile)
        }
        if variant and variant.layout == "h6099_music_parameters" and variant.supports_style:
            states[companion_index]["music_calm"] = calm
        if variant and variant.palette_bounds:
            # An incomplete upload invalidates retained knowledge. Neither assignment is readback.
            first_companion = 1 if profile.music_upload_before_selector else 2
            states[first_companion]["_music_palette"] = None
            retained = tuple(tuple(rgb) for rgb in palette) if palette is not None else music_default_palette(variant)
            states[companion_index]["_music_palette"] = (mode, retained)
    return tuple(zip(packets, states, strict=True))


def music_default_available(model: str, mode: str, *, profile: ModelProfile | None = None) -> bool:
    profile = get_profile(model) if profile is None else profile
    try:
        resolve_music_profile(model, mode, profile.music_sensitivity_max, None, None, {}, profile=profile)
    except ValueError:
        return False
    return True
