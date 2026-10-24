"""tests/test_projection_rebuild.py: Testes de reconstrução de projeções e auditoria isolada (C3)."""

import shutil
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from application.projection_engine import ProjectionEngine
from application.rebuild import default_projectors, rebuild_projections
from contract_support import make_draft
from contracts.event import ActorRef, EventDraft
from kernel.event_catalog import build_v1_catalog


class ProjectionRebuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(".tmp/test_scratch/test_rebuild")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = build_v1_catalog()
        self.store = JsonlEventStore(base_dir=self.test_dir, catalog=self.catalog)
        self.camp_dir = self.test_dir / "camp_reb"
        self.camp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_rebuild_produces_byte_identical_markdown_and_hash(self) -> None:
        # Grava eventos canônicos de turno, progressão e NPC
        drafts = [
            EventDraft(
                type="turn.committed",
                schema_version=1,
                actor=ActorRef("agent", "gm"),
                payload={
                    "turn": 1,
                    "summary": "O herói atravessou o desfiladeiro sombrio.",
                    "scene_type": "Exploração",
                    "location": "Desfiladeiro",
                    "present": ["Aemon"],
                    "vitals": {"hp": 18, "stamina": 15},
                },
                game_time="01 de Janeiro de 304, 10:00",
                game_time_sort=600,
            ),
            EventDraft(
                type="protagonist.progression_changed",
                schema_version=1,
                actor=ActorRef("system", "ruleset"),
                payload={
                    "xp_delta": 50,
                    "xp_total": 50,
                    "level": 1,
                    "attribute_points": 0,
                    "ability_points": 0,
                    "source": "exploração",
                },
                game_time="01 de Janeiro de 304, 10:00",
                game_time_sort=600,
            ),
            EventDraft(
                type="npc.updated",
                schema_version=1,
                actor=ActorRef("agent", "gm"),
                payload={
                    "npc_id": "malakor",
                    "changes": {"name": "Lorde Malakor", "status": "Hostil"},
                },
                game_time="01 de Janeiro de 304, 10:00",
                game_time_sort=600,
            ),
        ]
        self.store.append("camp_reb", drafts)

        # 1. Primeiro rebuild
        seq1, hash1 = rebuild_projections(self.store, "camp_reb", self.camp_dir, emit_audit_event=False)
        self.assertEqual(seq1, 3)
        self.assertTrue(hash1.startswith("sha256:"))

        proj_dir = self.camp_dir / "projections"
        self.assertTrue((proj_dir / "diario.md").exists())
        self.assertTrue((proj_dir / "ficha.md").exists())
        self.assertTrue((proj_dir / "npcs.md").exists())

        diario_text1 = (proj_dir / "diario.md").read_text(encoding="utf-8")
        ficha_text1 = (proj_dir / "ficha.md").read_text(encoding="utf-8")
        npcs_text1 = (proj_dir / "npcs.md").read_text(encoding="utf-8")

        # 2. Segundo rebuild (idempotência e byte-identidade)
        seq2, hash2 = rebuild_projections(self.store, "camp_reb", self.camp_dir, emit_audit_event=False)
        self.assertEqual(hash1, hash2)
        self.assertEqual(diario_text1, (proj_dir / "diario.md").read_text(encoding="utf-8"))
        self.assertEqual(ficha_text1, (proj_dir / "ficha.md").read_text(encoding="utf-8"))
        self.assertEqual(npcs_text1, (proj_dir / "npcs.md").read_text(encoding="utf-8"))

    def test_rebuild_audit_isolated_from_hash_c3(self) -> None:
        # Critério C3: comprovar que projection.rebuilt não altera o hash verificado
        draft = EventDraft(
            type="turn.committed",
            schema_version=1,
            actor=ActorRef("agent", "gm"),
            payload={"turn": 1, "summary": "Ato heroico."},
            game_time="01 de Janeiro de 304, 12:00",
            game_time_sort=720,
        )
        self.store.append("camp_reb", [draft])

        # Executa rebuild com emissão do evento de auditoria
        seq, audit_hash = rebuild_projections(self.store, "camp_reb", self.camp_dir, emit_audit_event=True)

        # O evento projection.rebuilt foi gravado no store
        events_after = tuple(self.store.read("camp_reb"))
        self.assertEqual(len(events_after), 2)
        self.assertEqual(events_after[-1].type, "projection.rebuilt")
        self.assertEqual(events_after[-1].payload["hash"], audit_hash)

        # Recalcula o hash das projeções em disco: deve ser ESTRITAMENTE o mesmo
        from contracts.ports import EventStreamView
        engine = ProjectionEngine(default_projectors(), campaign_dir=self.camp_dir)
        proj_view = engine.project(EventStreamView(campaign_id="camp_reb", events=tuple(self.store.read("camp_reb"))))
        recalc_hash = engine.write_projections_atomic(proj_view)

        self.assertEqual(audit_hash, recalc_hash, "O evento projection.rebuilt não pode alterar o hash auditado (Critério C3)")


if __name__ == "__main__":
    unittest.main()
