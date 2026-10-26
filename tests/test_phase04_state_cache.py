"""Testes de projeção, integridade e staleness do cache estado.json (C08)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from application.context.state import ContextStateViewImpl, PrepareError
from application.projectors.state import StateProjector
from application.rebuild import rebuild_projections
from contracts.event import ActorRef, EventDraft
from resources.factions.service import make_faction_updated_draft
from resources.npcs.drafts import make_npc_plan_updated_draft, make_npc_promoted_draft


class FailingEventStore:
    """Stub de EventStore que levanta exceção caso qualquer método de leitura seja chamado."""

    def __init__(self, real_store: JsonlEventStore) -> None:
        self._real = real_store

    def last_seq(self, campaign_id: str) -> int:
        return self._real.last_seq(campaign_id)

    def read(self, *args, **kwargs):
        raise AssertionError("EventStore.read NÃO deve ser chamado quando o cache está fresco!")

    def append(self, *args, **kwargs):
        return self._real.append(*args, **kwargs)


class StateCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.camp_dir = Path(self.tmp.name) / "test_camp"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        self.store = JsonlEventStore(self.camp_dir)

        # Baseline de eventos
        actor = ActorRef(kind="human", id="gm")
        ev0 = EventDraft(
            type="campaign.created",
            schema_version=1,
            actor=actor,
            game_time="01/10/300 08:00",
            game_time_sort=1,
            payload={
                "title": "Test Camp",
                "system": "d20_dirty",
                "calendar": "standard",
                "start_game_time": "01/10/300 08:00",
                "config_version": 1,
            },
            meta={"baseline": {"diario.md": "# Diário\n\n## 1. Estado da Cena\n- Data/Hora: 01/10 10:00\n- Local: Castelo\n- Presentes: Aemon\n"}},
        )
        ev1 = make_npc_promoted_draft("malakor", "minor", "major", "01/10/300 08:00", 2, capabilities=["guerra"])
        ev2 = make_npc_plan_updated_draft(
            "malakor", "pln_golpe", "tomar_trono", "Golpe", [{"step_id": "s1", "description": "Cercar", "status": "in_progress"}],
            "active", "01/10/300 08:00", 3
        )
        ev3 = make_faction_updated_draft("MALAKOR", "Guarda", "01/10/300 08:00", 4, leadership={"leader_id": "malakor"})

        self.store.append("test_camp", [ev0, ev1, ev2, ev3])
        rebuild_projections(self.store, "test_camp", self.camp_dir, emit_audit_event=False)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_estado_json_generated_by_rebuild(self) -> None:
        state_file = self.camp_dir / "estado.json"
        self.assertTrue(state_file.exists(), "estado.json deve ser criado na raiz")
        proj_file = self.camp_dir / "projections" / "estado.json"
        self.assertTrue(proj_file.exists(), "estado.json deve ser criado em projections/")

        data = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["last_seq"], 4)
        self.assertIn("hash", data)
        self.assertTrue(any(n["id"] == "malakor" for n in data["npcs"]))
        self.assertTrue(any(f["tag"] == "MALAKOR" for f in data["factions"]))

    def test_fresh_cache_does_not_call_event_store_read(self) -> None:
        failing_store = FailingEventStore(self.store)
        view = ContextStateViewImpl.load("test_camp", self.camp_dir, store=failing_store)
        self.assertFalse(view.stale)
        self.assertEqual(view.last_seq, 4)
        self.assertIn("malakor", view.npcs())
        self.assertIn("MALAKOR", view.factions())

    def test_stale_cache_rebuilds_and_marks_stale_true(self) -> None:
        # Corrompe / desatualiza o last_seq no cache
        state_file = self.camp_dir / "estado.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["last_seq"] = 2
        state_file.write_text(json.dumps(data), encoding="utf-8")

        view = ContextStateViewImpl.load("test_camp", self.camp_dir, store=self.store)
        self.assertTrue(view.stale, "Deve marcar stale=True quando detectou divergência")
        self.assertEqual(view.last_seq, 4, "Após auto-reconstrução o last_seq deve ser o correto")

    def test_cache_freshness_after_rebuild_with_audit_event(self) -> None:
        rebuild_projections(self.store, "test_camp", self.camp_dir, emit_audit_event=True)
        view = ContextStateViewImpl.load("test_camp", self.camp_dir, store=self.store)
        self.assertFalse(view.stale, "Cache não pode ficar stale após rebuild com evento de auditoria")
        self.assertEqual(view.last_seq, self.store.last_seq("test_camp"))


if __name__ == "__main__":
    unittest.main()
