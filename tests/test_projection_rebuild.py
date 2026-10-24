"""tests/test_projection_rebuild.py: Testes de reconstrução de projeções e auditoria isolada (C3)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import council.helpers as helpers
from adapters.persistence.event_store import JsonlEventStore
from application.commit import cmd_commit
from application.projection_engine import ProjectionEngine
from application.rebuild import default_projectors, rebuild_projections
from campaign.templates import init_campaign_from_templates
from contracts.event import ActorRef, EventDraft
from contracts.ports import EventStreamView
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

        # Cria arquivo obsoleto em projections/ para validar limpeza (P2-7)
        proj_dir = self.camp_dir / "projections"
        proj_dir.mkdir(parents=True, exist_ok=True)
        obsolete_file = proj_dir / "obsolete_legacy.md"
        obsolete_file.write_text("lixo obsoleto", encoding="utf-8")

        seq1, hash1 = rebuild_projections(self.store, "camp_reb", self.camp_dir, emit_audit_event=False)
        self.assertEqual(seq1, 3)
        self.assertTrue(hash1.startswith("sha256:"))
        self.assertFalse(obsolete_file.exists())

        for fname in ("diario.md", "ficha.md", "npcs.md"):
            self.assertTrue((proj_dir / fname).exists())
            self.assertTrue((self.camp_dir / fname).exists())
            self.assertEqual(
                (proj_dir / fname).read_bytes(),
                (self.camp_dir / fname).read_bytes(),
            )

        diario_text1 = (proj_dir / "diario.md").read_text(encoding="utf-8")
        ficha_text1 = (proj_dir / "ficha.md").read_text(encoding="utf-8")
        npcs_text1 = (proj_dir / "npcs.md").read_text(encoding="utf-8")

        seq2, hash2 = rebuild_projections(self.store, "camp_reb", self.camp_dir, emit_audit_event=False)
        self.assertEqual(hash1, hash2)
        self.assertEqual(diario_text1, (proj_dir / "diario.md").read_text(encoding="utf-8"))
        self.assertEqual(ficha_text1, (proj_dir / "ficha.md").read_text(encoding="utf-8"))
        self.assertEqual(npcs_text1, (proj_dir / "npcs.md").read_text(encoding="utf-8"))

    def test_rebuild_audit_isolated_from_hash_c3(self) -> None:
        draft = EventDraft(
            type="turn.committed",
            schema_version=1,
            actor=ActorRef("agent", "gm"),
            payload={"turn": 1, "summary": "Ato heroico."},
            game_time="01 de Janeiro de 304, 12:00",
            game_time_sort=720,
        )
        self.store.append("camp_reb", [draft])

        seq, audit_hash = rebuild_projections(self.store, "camp_reb", self.camp_dir, emit_audit_event=True)
        events_after = tuple(self.store.read("camp_reb"))
        self.assertEqual(len(events_after), 2)
        self.assertEqual(events_after[-1].type, "projection.rebuilt")
        self.assertEqual(events_after[-1].payload["hash"], audit_hash)

        engine = ProjectionEngine(default_projectors(), campaign_dir=self.camp_dir)
        proj_view = engine.project(EventStreamView(campaign_id="camp_reb", events=tuple(self.store.read("camp_reb"))))
        recalc_hash = engine.write_projections_atomic(proj_view)
        self.assertEqual(audit_hash, recalc_hash)

    def test_rebuild_incremental_from_snapshot_and_force_ignore(self) -> None:
        self.store.append(
            "camp_reb",
            [
                EventDraft(
                    type="turn.committed",
                    schema_version=1,
                    actor=ActorRef("agent", "gm"),
                    payload={"turn": 1, "summary": "Primeiro turno histórico."},
                    game_time="01 de Janeiro de 304, 10:00",
                    game_time_sort=600,
                ),
                EventDraft(
                    type="turn.committed",
                    schema_version=1,
                    actor=ActorRef("agent", "gm"),
                    payload={"turn": 2, "summary": "Segundo turno histórico."},
                    game_time="01 de Janeiro de 304, 11:00",
                    game_time_sort=660,
                ),
            ],
        )

        # Rebuild incremental passando apenas last_seq=1 materializa o prefixo e aplica o Turno 2 (P1-6)
        _, hash_inc = rebuild_projections(
            self.store,
            "camp_reb",
            self.camp_dir,
            snapshot={"last_seq": 1},
            emit_audit_event=False,
        )
        diario_inc = (self.camp_dir / "diario.md").read_text(encoding="utf-8")
        self.assertIn("Turno 1:", diario_inc)
        self.assertIn("Turno 2:", diario_inc)

        # Rebuild completo desde 0 gera hash idêntico
        _, hash_full = rebuild_projections(
            self.store,
            "camp_reb",
            self.camp_dir,
            force=True,
            emit_audit_event=False,
        )
        self.assertEqual(hash_inc, hash_full)

        # Injeta snapshot corrompido em snapshots/ e verifica que force=True ignora (P2-4)
        snap_dir = self.camp_dir / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        (snap_dir / "000001.json").write_text(
            json.dumps({"last_seq": 1, "files": {"diario.md": "CORROMPIDO"}}),
            encoding="utf-8",
        )
        _, hash_forced = rebuild_projections(
            self.store,
            "camp_reb",
            self.camp_dir,
            force=True,
            emit_audit_event=False,
        )
        self.assertEqual(hash_forced, hash_full)

    def test_rebuild_restores_deleted_root_ssot_after_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orig_dirs = helpers.CAMPAIGN_DIRS
            helpers.CAMPAIGN_DIRS = [root]
            try:
                cid = "camp_ssot_restore"
                res_init = init_campaign_from_templates(cid, title="Campanha Restaurável", protagonist_name="Kael")
                self.assertEqual(res_init["status"], "ok")
                cdir = root / cid

                res_com = cmd_commit(
                    cid,
                    summary="Kael explorou a torre vigiada e recuou ferido.",
                    cost="HP -3, time +30m",
                    location="Torre Vigiada",
                    npc_updates="Aliado Inicial: Preocupado com o ferimento de Kael",
                    force=True,
                )
                self.assertEqual(res_com["status"], "ok")

                saved = {
                    fname: (cdir / fname).read_bytes()
                    for fname in ("diario.md", "ficha.md", "npcs.md")
                }
                for fname, raw in saved.items():
                    self.assertEqual(raw, (cdir / "projections" / fname).read_bytes())
                    (cdir / fname).unlink()

                shutil.rmtree(cdir / "projections")
                store = JsonlEventStore(cdir)
                rebuild_projections(store, cid, cdir, emit_audit_event=False)

                for fname, raw in saved.items():
                    self.assertEqual((cdir / fname).read_bytes(), raw)
                    self.assertEqual((cdir / "projections" / fname).read_bytes(), raw)
            finally:
                helpers.CAMPAIGN_DIRS = orig_dirs


if __name__ == "__main__":
    unittest.main()
