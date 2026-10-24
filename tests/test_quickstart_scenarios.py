"""tests/test_quickstart_scenarios.py: Validação ponta a ponta dos 11 cenários do quickstart.md."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import council.helpers as helpers
from adapters.persistence.event_store import JsonlEventStore
from application.commit import cmd_commit
from application.prose_store import ProseStore
from application.rebuild import rebuild_projections
from application.showrunner import cmd_correct, cmd_rebuild
from campaign.templates import init_campaign_from_templates
from contracts.event import ActorRef, EventDraft
from council.reviewer import cmd_review
from kernel.errors import (
    ConflictError,
    DuplicateBatchError,
    ReplayError,
    SchemaError,
    UnknownEventTypeError,
)
from kernel.event_catalog import build_v1_catalog


class TestQuickstartScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.camp_root = Path(self.tmp_dir.name)
        self.orig_dirs = helpers.CAMPAIGN_DIRS
        helpers.CAMPAIGN_DIRS = [self.camp_root]
        self.camp_id = "_qa_causal_r1"

        init_res = init_campaign_from_templates(
            self.camp_id,
            title="Crônica de Teste Causal",
            protagonist_name="Aemon",
        )
        self.assertEqual(init_res["status"], "ok")
        self.camp_dir = self.camp_root / self.camp_id

    def tearDown(self):
        helpers.CAMPAIGN_DIRS = self.orig_dirs
        self.tmp_dir.cleanup()

    def test_scenario_01_roundtrip(self):
        """Cenário 1: Evento Ida-e-Volta preservando identidade, seq contíguo e UTC."""
        store = JsonlEventStore(self.camp_dir)
        events = tuple(store.read(self.camp_id))
        self.assertGreaterEqual(len(events), 1)
        first = events[0]
        self.assertTrue(first.event_id.startswith("evt_"))
        self.assertEqual(first.seq, 1)
        self.assertEqual(first.type, "campaign.created")
        self.assertTrue(first.recorded_at.endswith("Z"))
        self.assertEqual(store.last_seq(self.camp_id), len(events))

    def test_scenario_02_crash_and_recovery_and_tamper_detection(self):
        """Cenário 2: Lote Atômico sob Crash & Recuperação Automática (C1) + Tamper Detection (P1-9)."""
        store = JsonlEventStore(self.camp_dir)
        seg_file = self.camp_dir / "events" / "000001.jsonl"
        with seg_file.open("a", encoding="utf-8") as f:
            f.write('{"record": "batch", "state": "open", "batch_id": "bat_orphan"}\n')
            f.write('{"record": "event", "event_id": "evt_orph1", "seq": 999}\n')

        evts = tuple(store.read(self.camp_id))
        self.assertNotIn("evt_orph1", [e.event_id for e in evts])

        new_draft = EventDraft(
            type="turn.proposed",
            schema_version=1,
            actor=ActorRef(kind="agent", id="narrative_engine"),
            game_time="01 de Outubro de 2026, 12:30",
            game_time_sort=200,
            payload={"turn": 2, "action": "Avançar", "summary": "Turno 2"},
        )
        store.append(self.camp_id, [new_draft])
        evts_after = tuple(store.read(self.camp_id))
        self.assertEqual(evts_after[-1].payload["turn"], 2)

        # Adultera o hash do marcador committed e valida ReplayError (P1-9)
        orig_seg = seg_file.read_text(encoding="utf-8")
        lines = orig_seg.splitlines()
        last_marker = json.loads(lines[-1])
        last_marker["hash"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        lines[-1] = json.dumps(last_marker)
        seg_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(ReplayError):
            tuple(store.read(self.camp_id))
        seg_file.write_text(orig_seg, encoding="utf-8")

    def test_scenario_03_rebuild_byte_identical(self):
        """Cenário 3: Reconstrução de Projeção Byte-Idêntica (C3) após cmd_commit real."""
        res_com = cmd_commit(
            self.camp_id,
            summary="Aemon avançou pelas muralhas sob chuva intensa.",
            cost="HP -2, time +15m",
            location="Muralhas Norte",
            npc_updates="Aliado Inicial: Em alerta máximo nas ameias",
            force=True,
        )
        self.assertEqual(res_com["status"], "ok")

        res_reb1 = cmd_rebuild(self.camp_id)
        self.assertEqual(res_reb1["status"], "ok")
        hash1 = res_reb1["projection_hash"]

        proj_dir = self.camp_dir / "projections"
        for fname in ("diario.md", "ficha.md", "npcs.md"):
            self.assertEqual(
                (self.camp_dir / fname).read_bytes(),
                (proj_dir / fname).read_bytes(),
            )

        shutil.rmtree(proj_dir)
        self.assertFalse(proj_dir.exists())

        res_reb2 = cmd_rebuild(self.camp_id)
        self.assertEqual(res_reb2["status"], "ok")
        hash2 = res_reb2["projection_hash"]
        self.assertEqual(hash1, hash2)

    def test_scenario_04_selective_correction(self):
        """Cenário 4: Correção Seletiva e Reavaliação de Dependentes."""
        cmd_commit(
            self.camp_id,
            summary="Aemon cumpriu o primeiro objetivo da patrulha.",
            quest_progress="Q1:1",
            force=True,
        )
        store = JsonlEventStore(self.camp_dir)
        events = tuple(store.read(self.camp_id))
        target_evt = next(e.event_id for e in events if e.type == "protagonist.progression_changed")

        cor_res = cmd_correct(
            self.camp_id,
            event=target_evt,
            reason="XP ajustado retroativamente",
            delta_xp=-10,
        )
        self.assertEqual(cor_res["status"], "ok")
        self.assertGreater(cor_res["events_appended"], 0)

    def test_scenario_05_immutable_prose_and_reviewer_audit(self):
        """Cenário 5: Prosa Original Recuperável, Cardinalidade 1:1 & Auditoria PROSE_MISSING."""
        prose_text = "O vento sussurrava nas muralhas de pedra antiga enquanto Aemon observava o horizonte."
        res_com = cmd_commit(
            self.camp_id,
            summary="Aemon vigiou o horizonte das muralhas.",
            prose=prose_text,
            force=True,
        )
        self.assertEqual(res_com["status"], "ok")

        store = ProseStore(self.camp_dir)
        # Cardinalidade 1:1: prosa diferente para o mesmo turno 2 levanta ConflictError (P2-5)
        with self.assertRaises(ConflictError):
            store.store_turn_prose(2, "Outra prosa conflitante para o mesmo turno.")

        # Adulteração do arquivo de prosa gera PROSE_MISSING no cmd_review (P2-5)
        prose_files = list((self.camp_dir / "artifacts" / "prose").glob("turn_000002-*.md"))
        self.assertEqual(len(prose_files), 1)
        prose_path = prose_files[0]
        prose_path.write_text("Prosa adulterada fora da banda!", encoding="utf-8")
        rev = cmd_review(self.camp_id)
        prose_issues = [i for i in rev["issues"] if i["type"] == "PROSE_MISSING"]
        self.assertEqual(len(prose_issues), 1)
        self.assertEqual(prose_issues[0]["severity"], "CRITICAL")

    def test_scenario_06_idempotent_resume_and_duplicate_batch_rejection(self):
        """Cenário 6: Retomada Idempotente e Rejeição de Lote Duplicado (DuplicateBatchError)."""
        store = JsonlEventStore(self.camp_dir)
        draft = EventDraft(
            type="turn.proposed",
            schema_version=1,
            actor=ActorRef(kind="agent", id="narrative_engine"),
            game_time="01 de Outubro de 2026, 14:00",
            game_time_sort=300,
            payload={"turn": 3, "action": "Explorar", "summary": "Turno 3"},
            meta={"idempotency_key": "idem_turn_3"},
        )
        store.append(self.camp_id, [draft])
        with self.assertRaises(DuplicateBatchError):
            store.append(self.camp_id, [draft])

    def test_scenario_07_schema_versioning_and_default_catalog(self):
        """Cenário 7: Catálogo v1 ativo por padrão com 25 tipos e rejeição de versão/tipo inválido (P1-2)."""
        catalog = build_v1_catalog()
        self.assertEqual(len(catalog), 25)

        store = JsonlEventStore(self.camp_dir)
        with self.assertRaises(UnknownEventTypeError):
            store.append(
                self.camp_id,
                [
                    EventDraft(
                        type="evento.fantasma",
                        schema_version=1,
                        actor=ActorRef(kind="agent", id="narrative_engine"),
                        game_time="01 de Outubro de 2026, 15:00",
                        game_time_sort=400,
                        payload={},
                    )
                ],
            )
        with self.assertRaises(SchemaError):
            store.append(
                self.camp_id,
                [
                    EventDraft(
                        type="turn.proposed",
                        schema_version=99,
                        actor=ActorRef(kind="agent", id="narrative_engine"),
                        game_time="01 de Outubro de 2026, 15:00",
                        game_time_sort=400,
                        payload={"turn": 4, "action": "Futuro", "summary": "Turno 4"},
                    )
                ],
            )

    def test_scenario_08_file_segmentation(self):
        """Cenário 8: Segmentação de Arquivos e Rotação."""
        store = JsonlEventStore(self.camp_dir, max_segment_events=5)
        drafts = [
            EventDraft(
                type="turn.proposed",
                schema_version=1,
                actor=ActorRef(kind="agent", id="narrative_engine"),
                game_time="01 de Outubro de 2026, 16:00",
                game_time_sort=500 + i,
                payload={"turn": 10 + i, "action": f"Ação {i}", "summary": f"Turno {10+i}"},
            )
            for i in range(10)
        ]
        store.append(self.camp_id, drafts)
        store.append(
            self.camp_id,
            [
                EventDraft(
                    type="turn.proposed",
                    schema_version=1,
                    actor=ActorRef(kind="agent", id="narrative_engine"),
                    game_time="01 de Outubro de 2026, 16:30",
                    game_time_sort=600,
                    payload={"turn": 99, "action": "Rotacionar", "summary": "Turno 99"},
                )
            ],
        )
        seg2 = self.camp_dir / "events" / "000002.jsonl"
        self.assertTrue(seg2.exists())

    def test_scenario_09_intra_batch_dependencies_and_commit_dag(self):
        """Cenário 9: Validação de Dependências Intra-Lote (C2) e DAG do cmd_commit."""
        res_com = cmd_commit(
            self.camp_id,
            summary="Aemon reforçou as barricadas e descansou.",
            cost="Stamina -2, time +20m",
            add_item="Corda de Cânhamo",
            prose="Aemon amarrou as toras com firmeza sob o olhar atento da guarda.",
            force=True,
        )
        self.assertEqual(res_com["status"], "ok")
        store = JsonlEventStore(self.camp_dir)
        evts = tuple(store.read(self.camp_id))
        types = [e.type for e in evts]
        for expected_type in (
            "campaign.created",
            "turn.proposed",
            "action.resolved",
            "protagonist.sheet_changed",
            "prose.recorded",
            "turn.committed",
        ):
            self.assertIn(expected_type, types)
        last_committed = evts[-1]
        self.assertEqual(last_committed.type, "turn.committed")
        self.assertTrue(all(dep.startswith("evt_") for dep in last_committed.meta["dependencies"]))

    def test_scenario_10_rebuild_audit_isolation(self):
        """Cenário 10: Auditoria de Rebuild sem Autoinfluência (C3)."""
        store = JsonlEventStore(self.camp_dir)
        _, h1 = rebuild_projections(store, self.camp_id, self.camp_dir, emit_audit_event=True)
        _, h2 = rebuild_projections(store, self.camp_id, self.camp_dir, emit_audit_event=False)
        self.assertEqual(h1, h2)

    def test_scenario_11_contradiction_detection_and_resolution(self):
        """Cenário 11: Correção Contraditória com Registro e Resolução de Inconsistência (C4)."""
        store = JsonlEventStore(self.camp_dir)
        evts = tuple(store.read(self.camp_id))
        target_evt = evts[0].event_id

        res = cmd_correct(
            self.camp_id,
            event=target_evt,
            reason="Combate anulado retroativamente",
            contradiction=True,
        )
        self.assertEqual(res["status"], "ok")
        self.assertTrue(res["inconsistency_detected"])

        rev1 = cmd_review(self.camp_id)
        self.assertTrue(any(i["type"] == "CAUSAL_INCONSISTENCY" for i in rev1["issues"]))

        cor_evt = next(e.event_id for e in store.read(self.camp_id) if e.type == "correction.issued")
        res_resolve = cmd_correct(
            self.camp_id,
            event=cor_evt,
            reason="Reconciliado pelo mestre na sessão seguinte",
            resolve=True,
        )
        self.assertEqual(res_resolve["status"], "ok")
        rev2 = cmd_review(self.camp_id)
        self.assertFalse(any(i["type"] == "CAUSAL_INCONSISTENCY" for i in rev2["issues"]))

    def test_commit_rollback_restores_events_projections_and_artifacts(self):
        """P1-1: Falha durante cmd_commit reverte events/, projections/, artifacts/ e Markdown."""
        store = JsonlEventStore(self.camp_dir)
        seq_before = store.last_seq(self.camp_id)
        diario_before = (self.camp_dir / "diario.md").read_bytes()
        ficha_before = (self.camp_dir / "ficha.md").read_bytes()

        with patch("application.commit.cmd_review", side_effect=RuntimeError("falha pós-commit simulada")):
            with self.assertRaises(RuntimeError):
                cmd_commit(
                    self.camp_id,
                    summary="Turno que falhará na auditoria pós-commit.",
                    cost="HP -5",
                    prose="Prosa que deve ser revertida junto com a transação.",
                    force=True,
                )

        self.assertEqual(store.last_seq(self.camp_id), seq_before)
        self.assertEqual((self.camp_dir / "diario.md").read_bytes(), diario_before)
        self.assertEqual((self.camp_dir / "ficha.md").read_bytes(), ficha_before)
        self.assertEqual((self.camp_dir / "projections" / "diario.md").read_bytes(), diario_before)
        self.assertFalse((self.camp_dir / "artifacts").exists())


if __name__ == "__main__":
    unittest.main()
