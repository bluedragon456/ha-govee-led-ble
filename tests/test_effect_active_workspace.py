"""Selector domains survive workspace reload without guessing from slot numbers."""

from custom_components.ha_govee_led_ble.effect_active_workspace import (
    ActiveEffectWorkspace,
    ActiveEffectWorkspaceRepository,
)
from custom_components.ha_govee_led_ble.effect_catalogue import WORKSHOP_PROTOCOL_FIXTURES
from custom_components.ha_govee_led_ble.effect_domain import Origin, SingleEffect, SourceKind
from tests.storage_test_double import InMemoryVersionedDocumentStore


async def test_legacy_workspace_selector_migration_is_content_scoped() -> None:
    for content, expected in [
        (WORKSHOP_PROTOCOL_FIXTURES[0].content("H617A"), "scene-code:24"),
        (SingleEffect(0, 0, 50, ((255, 0, 0),)), "custom:24"),
    ]:
        workspace = ActiveEffectWorkspace(
            config_entry_id="entry-a",
            model="H617A",
            selector_label="Custom",
            content=content,
            origin=Origin(SourceKind.AUTHORED),
            observable_signature="custom:24",
            updated_at="2026-08-26T00:00:00Z",
            generation=1,
        )
        store = InMemoryVersionedDocumentStore({"devices": {"entry-a": workspace.to_dict()}})
        repository = ActiveEffectWorkspaceRepository(store)
        assert (await repository.async_load())[0].observable_signature == expected
        await repository.async_flush()
        reloaded = ActiveEffectWorkspaceRepository(store)
        assert (await reloaded.async_load())[0].observable_signature == expected
