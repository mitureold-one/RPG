"""tests/test_causal_correction.py: Testes de correções causais, compensações e contradições (C4)."""

import shutil
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from application.correction import CorrectionService
from contracts.event import ActorRef, EventDraft
from council.reviewer import cmd_review
from kernel.event_catalog import build_v1_catalog


class CausalCorrectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(".tmp/test_scratch/test_correction")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = build_v1_catalog()
        self.store = JsonlEventStore(base_dir=self.test_dir, catalog=self.catalog)
        self.service = CorrectionService(self.store)

        self.camp_dir = self.test_dir / "camp_cor"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        (self.camp_dir / "ficha.md").write_text("# Ficha\n* **Nome:** Kaelen\n### Vitais\n* **HP:** 20/20\n", encoding="utf-8")
        (self.camp_dir / "diario.md").write_text("# Diário\n**Data & Local:** Dia 1 — Capital\n**Presentes:** Kaelen\n", encoding="utf-8")
        (self.camp_dir / "npcs.md").write_text("# NPCs\n", encoding="utf-8")
        (self.camp_dir / "mundo.md").write_text("# Mundo\n", encoding="utf-8")
        (self.camp_dir / "regras.md").write_text("# Regras\n", encoding="utf-8")

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_numerical_xp_compensation_appends_cleanly(self) -> None:
        # 1. Evento original de concessão de XP indevido (100 XP)
        res_orig = self.store.append(
            "camp_cor",
            [
                EventDraft(
                    type="protagonist.progression_changed",
                    schema_version=1,
                    actor=ActorRef("system", "ruleset"),
                    payload={
                        "xp_delta": 100,
                        "xp_total": 100,
                        "level": 1,
                        "attribute_points": 0,
                        "ability_points": 0,
                        "source": "missao_duplicada",
                    },
                    game_time="01 de Janeiro de 304, 10:00",
                    game_time_sort=600,
                )
            ],
        )
        orig_eid = res_orig.events[0].event_id

        # 2. Emite correção deduzindo 100 XP
        res_cor = self.service.issue_correction(
            campaign_id="camp_cor",
            actor=ActorRef("human", "user"),
            corrects=[orig_eid],
            reason="XP concedido em duplicidade",
            changes=[{"field": "xp_delta", "delta": -100}],
            game_time="01 de Janeiro de 304, 12:00",
            game_time_sort=720,
        )

        all_events = tuple(self.store.read("camp_cor"))
        # Evento original (1), correction.issued (2), protagonist.progression_changed compensatório (3)
        self.assertEqual(len(all_events), 3)
        self.assertEqual(all_events[0].event_id, orig_eid)
        self.assertEqual(all_events[1].type, "correction.issued")
        self.assertEqual(all_events[2].type, "protagonist.progression_changed")
        self.assertEqual(all_events[2].payload["xp_delta"], -100)
        self.assertEqual(all_events[2].payload["xp_total"], 0)

    def test_contradictory_correction_flags_inconsistency_c4(self) -> None:
        # Critério C4: invalidar fato posterior registra inconsistência sem mutação silenciosa
        res_orig = self.store.append(
            "camp_cor",
            [
                EventDraft(
                    type="turn.committed",
                    schema_version=1,
                    actor=ActorRef("agent", "gm"),
                    payload={"turn": 1, "summary": "Vitória contra o algoz."},
                    game_time="01 de Janeiro de 304, 10:00",
                    game_time_sort=600,
                )
            ],
        )
        orig_eid = res_orig.events[0].event_id

        # Emite correção com flag de contradição narrativa
        res_cor = self.service.issue_correction(
            campaign_id="camp_cor",
            actor=ActorRef("human", "user"),
            corrects=[orig_eid],
            reason="O algoz na verdade utilizou um feitiço de escape e não foi derrotado",
            changes=[{"field": "outcome", "contradiction": True}],
            game_time="01 de Janeiro de 304, 12:00",
            game_time_sort=720,
        )

        # Verifica eventos gravados
        all_events = tuple(self.store.read("camp_cor"))
        cor_issued = next(e for e in all_events if e.type == "correction.issued")
        self.assertTrue(cor_issued.payload["inconsistency_detected"])
        self.assertEqual(cor_issued.payload["state"], "pendente")

        # Verifica detecção de inconsistência causal (Critério C4)
        from application.correction import check_causal_inconsistencies
        issues = check_causal_inconsistencies(self.camp_dir, "camp_cor")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["type"], "CAUSAL_INCONSISTENCY")
        self.assertEqual(issues[0]["severity"], "CRITICAL")


if __name__ == "__main__":
    unittest.main()
