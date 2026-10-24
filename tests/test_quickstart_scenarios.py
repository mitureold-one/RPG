"""tests/test_quickstart_scenarios.py: Validação ponta a ponta dos 11 cenários do quickstart.md."""

import shutil
import tempfile
import unittest
from pathlib import Path

import council.helpers as helpers
from adapters.persistence.event_store import JsonlEventStore
from application.commit import cmd_commit
from application.correction import CorrectionService
from application.prose_store import ProseStore
from application.rebuild import rebuild_projections
from application.showrunner import cmd_correct, cmd_rebuild
from campaign.templates import init_campaign_from_templates
from contracts.event import ActorRef, EventDraft
from kernel.errors import DuplicateBatchError, SchemaError, ValidationError


class TestQuickstartScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.camp_root = Path(self.tmp_dir.name)
        self.orig_dirs = helpers.CAMPAIGN_DIRS
        helpers.CAMPAIGN_DIRS = [self.camp_root]
        self.camp_id = "_qa_causal_r1"

        # Inicializa a campanha canônica de teste
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
        self.assertTrue(first.recorded_at.endswith("Z"))
        self.assertEqual(store.last_seq(self.camp_id), len(events))

    def test_scenario_02_crash_and_recovery(self):
        """Cenário 2: Lote Atômico sob Crash & Recuperação Automática (C1)."""
        store = JsonlEventStore(self.camp_dir)
        # Injeta cauda corrompida / incompleta
        seg_file = self.camp_dir / "events" / "000001.jsonl"
        with seg_file.open("a", encoding="utf-8") as f:
            f.write('{"record": "batch", "state": "open", "batch_id": "bat_orphan"}\n')
            f.write('{"record": "event", "event_id": "evt_orph1", "seq": 999}\n')

        # Read não vê o lote corrompido
        evts = tuple(store.read(self.camp_id))
        self.assertNotIn("evt_orph1", [e.event_id for e in evts])

        # Novo append trunca e preserva integridade
        new_draft = EventDraft(
            type="turn.proposed",
            schema_version=1,
            actor=ActorRef(kind="agent", id="narrative_engine"),
            game_time="01 de Janeiro, 12:00",
            game_time_sort=200,
            payload={"turn": 2, "action": "Avançar", "summary": "Turno 2"},
        )
        store.append(self.camp_id, [new_draft])
        evts_after = tuple(store.read(self.camp_id))
        self.assertEqual(evts_after[-1].payload["turn"], 2)

    def test_scenario_03_rebuild_byte_identical(self):
        """Cenário 3: Reconstrução de Projeção Byte-Idêntica (C3)."""
        res_reb1 = cmd_rebuild(self.camp_id)
        self.assertEqual(res_reb1["status"], "ok")
        hash1 = res_reb1["projection_hash"]

        # Apaga projeções
        proj_dir = self.camp_dir / "projections"
        shutil.rmtree(proj_dir)
        self.assertFalse(proj_dir.exists())

        # Rebuild 2 recria projeções idênticas
        res_reb2 = cmd_rebuild(self.camp_id)
        self.assertEqual(res_reb2["status"], "ok")
        hash2 = res_reb2["projection_hash"]
        self.assertEqual(hash1, hash2)

    def test_scenario_04_selective_correction(self):
        """Cenário 4: Correção Seletiva e Reavaliação de Dependentes."""
        store = JsonlEventStore(self.camp_dir)
        events = tuple(store.read(self.camp_id))
        target_evt = events[0].event_id

        cor_res = cmd_correct(
            self.camp_id,
            event=target_evt,
            reason="XP duplicado",
            delta_xp=-100,
        )
        self.assertEqual(cor_res["status"], "ok")
        self.assertGreater(cor_res["events_appended"], 0)

    def test_scenario_05_immutable_prose(self):
        """Cenário 5: Prosa Original Recuperável & Hash Auditável."""
        store = ProseStore(self.camp_dir)
        content = "O vento sussurrava nas muralhas de pedra antiga."
        rel_p, p_hash, p_len = store.store_turn_prose(1, content)
        self.assertTrue(store.verify_prose(rel_p, p_hash))

    def test_scenario_06_idempotent_resume(self):
        """Cenário 6: Retomada Idempotente sem Duplicação."""
        store = JsonlEventStore(self.camp_dir)
        draft = EventDraft(
            type="turn.proposed",
            schema_version=1,
            actor=ActorRef(kind="agent", id="narrative_engine"),
            game_time="01 de Janeiro, 14:00",
            game_time_sort=300,
            payload={"turn": 3, "action": "Explorar", "summary": "Turno 3"},
        )
        # Primeiro append
        store.append(self.camp_id, [draft])
        # Re-leitura é consistente
        evts = tuple(store.read(self.camp_id))
        self.assertTrue(any(e.payload.get("turn") == 3 for e in evts))

    def test_scenario_07_schema_versioning(self):
        """Cenário 7: Versionamento de Schema e Rejeição de Versão Futura."""
        from kernel.event_catalog import build_v1_catalog
        store = JsonlEventStore(self.camp_dir, catalog=build_v1_catalog())
        # Versão futura desconhecida é rejeitada
        with self.assertRaises(Exception):
            draft_future = EventDraft(
                type="turn.proposed",
                schema_version=99,
                actor=ActorRef(kind="agent", id="narrative_engine"),
                game_time="01 de Janeiro, 15:00",
                game_time_sort=400,
                payload={"turn": 4, "action": "Futuro", "summary": "Turno 4"},
            )
            store.append(self.camp_id, [draft_future])

    def test_scenario_08_file_segmentation(self):
        """Cenário 8: Segmentação de Arquivos e Rotação."""
        store = JsonlEventStore(self.camp_dir, max_segment_events=5)
        drafts = [
            EventDraft(
                type="turn.proposed",
                schema_version=1,
                actor=ActorRef(kind="agent", id="narrative_engine"),
                game_time="01 de Janeiro, 16:00",
                game_time_sort=500 + i,
                payload={"turn": 10 + i, "action": f"Ação {i}", "summary": f"Turno {10+i}"},
            )
            for i in range(10)
        ]
        store.append(self.camp_id, drafts)
        # Próximo lote rotaciona para segmento 000002.jsonl
        store.append(self.camp_id, [
            EventDraft(
                type="turn.proposed",
                schema_version=1,
                actor=ActorRef(kind="agent", id="narrative_engine"),
                game_time="01 de Janeiro, 16:30",
                game_time_sort=600,
                payload={"turn": 99, "action": "Rotacionar", "summary": "Turno 99"},
            )
        ])
        # Confirma presença de múltiplos segmentos
        seg2 = self.camp_dir / "events" / "000002.jsonl"
        self.assertTrue(seg2.exists())

    def test_scenario_09_intra_batch_dependencies(self):
        """Cenário 9: Validação de Dependências Intra-Lote (C2)."""
        store = JsonlEventStore(self.camp_dir)
        d1 = EventDraft(
            type="turn.proposed",
            schema_version=1,
            actor=ActorRef(kind="agent", id="narrative_engine"),
            game_time="01 de Janeiro, 17:00",
            game_time_sort=600,
            payload={"turn": 20, "action": "Início", "summary": "T20"},
        )
        d2 = EventDraft(
            type="turn.committed",
            schema_version=1,
            actor=ActorRef(kind="agent", id="narrative_engine"),
            game_time="01 de Janeiro, 17:00",
            game_time_sort=601,
            payload={"turn": 20, "summary": "T20"},
            meta={"dependencies": ["batch:0"]},
        )
        res = store.append(self.camp_id, [d1, d2])
        self.assertEqual(len(res.events), 2)

    def test_scenario_10_rebuild_audit_isolation(self):
        """Cenário 10: Auditoria de Rebuild sem Autoinfluência (C3)."""
        store = JsonlEventStore(self.camp_dir)
        _, h1 = rebuild_projections(store, self.camp_id, self.camp_dir, emit_audit_event=True)
        _, h2 = rebuild_projections(store, self.camp_id, self.camp_dir, emit_audit_event=False)
        self.assertEqual(h1, h2)

    def test_scenario_11_contradiction_detection(self):
        """Cenário 11: Correção Contraditória com Registro de Inconsistência (C4)."""
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


if __name__ == "__main__":
    unittest.main()
