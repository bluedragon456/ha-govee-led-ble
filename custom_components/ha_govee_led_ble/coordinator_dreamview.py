"""Service-only DreamView transactions and anonymous observations.

Like issue #257 this is a coordinator mixin, but local authorship is not a slot
identity map. It never probes members or claims membership was read back.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping, Sequence
from typing import Any

from homeassistant.helpers.storage import Store
from homeassistant.util.file import WriteError
from homeassistant.util.json import SerializationError

from .const import DOMAIN
from .control_arbiter import ControlIntent, async_control_intent
from .coordinator_base import _CoordinatorBase
from .dreamview import (
    DREAMVIEW_READ_SETTINGS,
    DreamviewMember,
    build_dreamview_command,
    build_dreamview_group,
    build_dreamview_query,
    parse_dreamview_status,
    require_dreamview,
)


class _DreamviewStore(Store[dict[str, Any]]):
    """Require a completed atomic save, not Store's logged or deferred failure."""

    async def async_save(self, data: dict[str, Any]) -> None:
        if self.hass.is_stopping:
            raise OSError("DreamView persistence cannot be deferred during shutdown")
        await super().async_save(data)

    async def _async_write_data(self, data: dict[str, Any]) -> None:
        try:
            await super()._async_write_data(data)
        except WriteError, SerializationError:
            # Store suppresses these two exceptions. Do not allow BLE after either,
            # or include serialized member identities in the propagated error.
            raise OSError("DreamView membership could not be persisted") from None


class _DreamviewMixin(_CoordinatorBase):
    """Uses the existing complete-sequence writer, physical guards and arbiter."""

    def _init_dreamview(self) -> None:
        self._dreamview_observed: dict[str, dict[str, Any]] = {}
        self._dreamview_authored: dict[str, Any] | None = None
        self._dreamview_loaded = False
        self._dreamview_last_write = "unknown"
        self._dreamview_private_write = False
        self._dreamview_store = (
            _DreamviewStore(
                self.hass, 1, f"{DOMAIN}.dreamview.{self.config_entry.entry_id}", private=True, atomic_writes=True
            )
            if self.config_entry is not None
            else None
        )

    def _handle_dreamview_notification(self, frame: bytes) -> bool:
        """Call after decryption, before generic status routing; ACKs are ignored."""
        if not self.profile.dreamview_max_sub_devices or self.profile.status_grammar != "H6099":
            return False
        observed = parse_dreamview_status(frame)
        if observed is None:
            return False
        setting, values = observed
        self._dreamview_observed[setting] = values
        return True

    async def _async_load_dreamview(self) -> None:
        if not self._dreamview_loaded:
            if self._dreamview_store is None:
                raise ValueError("DreamView requires a config entry for private membership persistence")
            self._dreamview_authored = await self._dreamview_store.async_load()
            self._dreamview_loaded = True

    async def async_replace_dreamview_group(self, members: Sequence[DreamviewMember]) -> None:
        """Explicit replacement, not merge. Persist intent, never confirmed membership."""
        packets = build_dreamview_group(members, self.profile)
        authored = {"operation": "replace", "members": [member.as_dict() for member in members]}
        async with async_control_intent(self, ControlIntent.USER):
            await self._async_load_dreamview()
            assert self._dreamview_store is not None
            # Save before transmission so an interrupted upload retains the authored request.
            await self._dreamview_store.async_save(authored)
            self._dreamview_authored = authored
            self._dreamview_private_write = True
            try:
                await self._async_write_dreamview(packets)
            finally:
                self._dreamview_private_write = False

    async def async_set_dreamview(self, setting: str, values: Mapping[str, Any]) -> None:
        packet = build_dreamview_command(setting, values, self.profile)
        if setting == "delete_group":
            raise ValueError("Use explicit delete_dreamview_group")
        async with async_control_intent(self, ControlIntent.USER):
            await self._async_write_dreamview((packet,))

    async def async_delete_dreamview_group(self) -> None:
        """Keep the last authored members for recovery, mark only deletion intent."""
        packet = build_dreamview_command("delete_group", {}, self.profile)
        async with async_control_intent(self, ControlIntent.USER):
            await self._async_load_dreamview()
            assert self._dreamview_store is not None
            authored = {**(self._dreamview_authored or {}), "operation": "delete"}
            await self._dreamview_store.async_save(authored)
            self._dreamview_authored = authored
            await self._async_write_dreamview((packet,))

    async def _async_write_dreamview(self, packets: Sequence[bytes]) -> None:
        self._dreamview_last_write = "not_attempted"

        def guard() -> None:
            require_dreamview(self.profile)
            self._dreamview_last_write = "attempted_unconfirmed"

        await self.async_write_effect_sequence(packets, intent=ControlIntent.USER, write_guard=guard)
        self._dreamview_last_write = "sent_unconfirmed"

    async def async_read_dreamview_state(self, *, timeout: float = 2.0) -> dict[str, Any]:
        """Query only known individual reads; absent replies remain unknown.

        The protocol has no request IDs. Responses received after dispatch are
        observations, not proof they were caused by that request or any write.
        """
        require_dreamview(self.profile)
        if not 0 <= timeout <= 10:
            raise ValueError("DreamView read timeout must be 0..10 seconds")
        packets = tuple(build_dreamview_query(setting, self.profile) for setting in DREAMVIEW_READ_SETTINGS)
        async with async_control_intent(self, ControlIntent.USER):
            await self._async_load_dreamview()
            self._dreamview_observed.clear()
            await self.async_write_effect_sequence(
                packets, intent=ControlIntent.USER, write_guard=lambda: require_dreamview(self.profile)
            )
            deadline = asyncio.get_running_loop().time() + timeout
            while not set(DREAMVIEW_READ_SETTINGS) <= self._dreamview_observed.keys():
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(0.05, remaining))
            return {
                "authored": copy.deepcopy(self._dreamview_authored),
                "authored_source": "local_request",
                "membership_confirmed": False,
                "membership_readback": "unavailable",
                "last_write": self._dreamview_last_write,
                "observed": copy.deepcopy(self._dreamview_observed),
                "missing_reads": sorted(set(DREAMVIEW_READ_SETTINGS) - self._dreamview_observed.keys()),
                "slot_identities": "unknown",
            }
