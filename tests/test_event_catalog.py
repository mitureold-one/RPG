"""tests/test_event_catalog.py: Testes do catálogo de eventos v1 e upcasters."""

import shutil
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from contracts.event import ActorRef, EventDraft, EventType
from kernel.errors import SchemaError, UnknownEventTypeError
from kernel.event_catalog import build_v1_catalog, upcast_payload


class EventCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = build_v1_catalog()
        self.test_dir = Path(".tmp/test_scratch/test_event_catalog")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.store = JsonlEventStore(base_dir=self.test_dir, catalog=self.catalog)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_catalog_contains_expected_v1_types(self) -> None:
        expected = [
            "campaign.created",
            "command.executed",
            "turn.proposed",
            "turn.rejected",
            "action.resolved",
            "turn.committed",
            "clock.created",
            "clock.advanced",
            "clock.resolved",
            "quest.created",
            "quest.objective_completed",
            "quest.completed",
            "quest.failed",
            "quest.status_changed",
            "arc.updated",
            "scene.planned",
            "scene.completed",
            "npc.updated",
            "faction.reputation_changed",
            "protagonist.progression_changed",
            "protagonist.sheet_changed",
            "prose.recorded",
            "correction.issued",
            "correction.recomputed",
            "projection.rebuilt",
        ]
        for name in expected:
            self.assertIn(name, self.catalog)

    def test_valid_payload_appends_cleanly(self) -> None:
        draft = EventDraft(
            type="campaign.created",
            schema_version=1,
            actor=ActorRef("human", "user"),
            payload={
                "title": "Crônica de Cinzas",
                "system": "default",
                "calendar": "standard",
                "start_game_time": "01 de Janeiro de 304, 00:00",
                "config_version": 1,
            },
            game_time="01 de Janeiro de 304, 00:00",
            game_time_sort=0,
        )
        res = self.store.append("camp_cat", [draft])
        self.assertEqual(res.last_seq, 1)

    def test_invalid_payload_raises_schema_error(self) -> None:
        bad_draft = EventDraft(
            type="campaign.created",
            schema_version=1,
            actor=ActorRef("human", "user"),
            payload={
                "title": "Incompleto",
                # ausente system, calendar, etc.
            },
            game_time="01 de Janeiro de 304, 00:00",
            game_time_sort=0,
        )
        with self.assertRaises(SchemaError):
            self.store.append("camp_cat", [bad_draft])

    def test_unknown_event_type_raises_unknown_event_type_error(self) -> None:
        unknown_draft = EventDraft(
            type="unregistered.magic.spell",
            schema_version=1,
            actor=ActorRef("human", "user"),
            payload={"power": 99},
            game_time="01 de Janeiro de 304, 00:00",
            game_time_sort=0,
        )
        with self.assertRaises(UnknownEventTypeError):
            self.store.append("camp_cat", [unknown_draft])

    def test_upcasting_and_future_version_rejection(self) -> None:
        # Cria tipo com schema_version=2 e upcaster 1 -> 2
        custom_type = EventType(
            type="clock.custom",
            schema_version=2,
            payload_schema={"type": "object", "required": ["name", "new_field"]},
            upcasters={1: lambda p: {**p, "new_field": "default_val"}},
        )

        # 1. Versão antiga (1) recebe upcast para versão 2
        v1_payload = {"name": "Relógio"}
        upcasted = upcast_payload(custom_type, 1, v1_payload)
        self.assertEqual(upcasted["new_field"], "default_val")

        # 2. Versão futura (3) é rejeitada com SchemaError
        with self.assertRaises(SchemaError):
            upcast_payload(custom_type, 3, v1_payload)


if __name__ == "__main__":
    unittest.main()
