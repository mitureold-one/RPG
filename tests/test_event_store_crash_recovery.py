"""tests/test_event_store_crash_recovery.py: Testes de crash e recuperação do JsonlEventStore (C1)."""

import json
import shutil
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from contract_support import make_draft
from contracts.event import ActorRef, EventDraft
from kernel.errors import InvalidDraftError


class EventStoreCrashRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(".tmp/test_scratch/test_crash_recovery")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.store = JsonlEventStore(base_dir=self.test_dir, max_events_per_segment=5, catalog=None)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_crash_after_batch_open_recovers_cleanly(self) -> None:
        # Inicia segmento com batch.open órfão
        events_dir = self.test_dir / "camp1" / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        seg1 = events_dir / "000001.jsonl"
        with open(seg1, "w", encoding="utf-8") as f:
            f.write(json.dumps({"record": "batch", "state": "open", "batch_id": "bat_test1", "first_seq": 1, "event_count": 2}) + "\n")

        self.assertEqual(self.store.last_seq("camp1"), 0)
        self.assertEqual(tuple(self.store.read("camp1")), ())

        # Novo append trunca o open órfão e grava com sucesso
        res = self.store.append("camp1", [make_draft(payload={"val": "ok"})])
        self.assertEqual(res.first_seq, 1)
        self.assertEqual(res.last_seq, 1)
        self.assertEqual(self.store.last_seq("camp1"), 1)

        read_events = tuple(self.store.read("camp1"))
        self.assertEqual(len(read_events), 1)
        self.assertEqual(read_events[0].payload["val"], "ok")

    def test_crash_after_partial_events_is_invisible_and_truncated(self) -> None:
        # 1. Grava lote inicial válido
        self.store.append("camp1", [make_draft(payload={"step": 1})])
        self.assertEqual(self.store.last_seq("camp1"), 1)

        # 2. Injeta crash: grava batch.open e 2 eventos sem committed
        seg1 = self.test_dir / "camp1" / "events" / "000001.jsonl"
        with open(seg1, "a", encoding="utf-8") as f:
            f.write(json.dumps({"record": "batch", "state": "open", "batch_id": "bat_crash", "first_seq": 2, "event_count": 3}) + "\n")
            f.write(json.dumps({
                "record": "event",
                "event_id": "evt_01J00000000000000000000001",
                "campaign_id": "camp1",
                "seq": 2,
                "type": "test.step",
                "schema_version": 1,
                "recorded_at": "2026-10-24T12:00:00Z",
                "game_time": "01 de Janeiro de 304, 00:00",
                "game_time_sort": 0,
                "actor": {"id": "test", "kind": "system"},
                "causation_id": None,
                "correlation_id": None,
                "payload": {"step": 2},
                "meta": {},
            }) + "\n")

        # Nenhum leitor vê o evento órfão de seq 2
        events = tuple(self.store.read("camp1"))
        self.assertEqual(len(events), 1)
        self.assertEqual(self.store.last_seq("camp1"), 1)

        # 3. Novo append recupera truncando a cauda órfã
        res = self.store.append("camp1", [make_draft(payload={"step": "recuperado"})])
        self.assertEqual(res.first_seq, 2)
        self.assertEqual(res.last_seq, 2)
        self.assertEqual(self.store.last_seq("camp1"), 2)

        read_all = tuple(self.store.read("camp1"))
        self.assertEqual([e.seq for e in read_all], [1, 2])
        self.assertEqual(read_all[1].payload["step"], "recuperado")

    def test_crash_during_committed_marker_corrupted_line(self) -> None:
        self.store.append("camp1", [make_draft(payload={"ok": True})])
        seg1 = self.test_dir / "camp1" / "events" / "000001.jsonl"

        with open(seg1, "a", encoding="utf-8") as f:
            f.write(json.dumps({"record": "batch", "state": "open", "batch_id": "bat_bad", "first_seq": 2, "event_count": 1}) + "\n")
            f.write('{"record":"batch","state":"committed","batch_id":"bat_bad",CORRUPTED_JSON\n')

        # Leitura ignora o lote corrompido
        self.assertEqual(self.store.last_seq("camp1"), 1)
        self.assertEqual(len(tuple(self.store.read("camp1"))), 1)

        # Novo lote trunca a corrupção e avança limpo
        res = self.store.append("camp1", [make_draft(payload={"ok": "after_crash"})])
        self.assertEqual(res.first_seq, 2)
        self.assertEqual(res.last_seq, 2)

    def test_segment_rotation_when_max_events_exceeded(self) -> None:
        # max_events_per_segment configurado para 5 no setUp
        drafts = [make_draft(payload={"idx": i}) for i in range(5)]
        self.store.append("camp1", drafts)

        events_dir = self.test_dir / "camp1" / "events"
        self.assertTrue((events_dir / "000001.jsonl").exists())
        self.assertFalse((events_dir / "000002.jsonl").exists())

        # Próximo append rotaciona para o segundo segmento
        res = self.store.append("camp1", [make_draft(payload={"idx": 5})])
        self.assertEqual(res.events[0].seq, 6)
        self.assertTrue((events_dir / "000002.jsonl").exists())

        all_read = tuple(self.store.read("camp1"))
        self.assertEqual(len(all_read), 6)
        self.assertEqual([e.seq for e in all_read], list(range(1, 7)))

    def test_missing_game_time_raises_invalid_draft_error(self) -> None:
        bad_draft = EventDraft(
            type="test.event",
            schema_version=1,
            actor=ActorRef("system", "kernel-test"),
            payload={"k": "v"},
            game_time=None,
            game_time_sort=None,
        )
        with self.assertRaises(InvalidDraftError):
            self.store.append("camp1", [bad_draft])


if __name__ == "__main__":
    unittest.main()
