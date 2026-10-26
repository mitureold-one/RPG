"""tests/test_causal_correction.py: Testes de correções causais, compensações e contradições (C4)."""

import shutil
import tempfile
import unittest
from pathlib import Path

import council.helpers as helpers
from adapters.persistence.event_store import JsonlEventStore
from application.commit import cmd_commit
from application.correction import CorrectionService, check_causal_inconsistencies
from application.showrunner import cmd_correct
from campaign.templates import init_campaign_from_templates
from contracts.event import ActorRef, EventDraft
from council.quests import parse_xp_ledger_from_diario
from council.reviewer import cmd_review
from kernel.errors import DuplicateBatchError
from kernel.event_catalog import build_v1_catalog
from resources.progression import parse_progression_from_ficha


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
        (self.camp_dir / "diario.md").write_text("<!-- schema_version: 1 -->\n# Diário\n**Data & Local:** Dia 1 — Capital\n**Presentes:** Kaelen\n", encoding="utf-8")
        (self.camp_dir / "npcs.md").write_text("# NPCs\n", encoding="utf-8")
        (self.camp_dir / "mundo.md").write_text("# Mundo\n", encoding="utf-8")
        (self.camp_dir / "regras.md").write_text("# Regras\n", encoding="utf-8")

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_numerical_xp_compensation_appends_cleanly(self) -> None:
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

        self.service.issue_correction(
            campaign_id="camp_cor",
            actor=ActorRef("human", "user"),
            corrects=[orig_eid],
            reason="XP concedido em duplicidade",
            changes=[{"field": "xp_delta", "delta": -100}],
            game_time="01 de Janeiro de 304, 12:00",
            game_time_sort=720,
        )

        all_events = tuple(self.store.read("camp_cor"))
        self.assertEqual(len(all_events), 3)
        self.assertEqual(all_events[0].event_id, orig_eid)
        self.assertEqual(all_events[1].type, "correction.issued")
        self.assertEqual(all_events[2].type, "protagonist.progression_changed")
        self.assertEqual(all_events[2].payload["xp_delta"], -100)
        self.assertEqual(all_events[2].payload["xp_total"], 0)

    def test_contradictory_correction_flags_and_resolves_inconsistency_c4(self) -> None:
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

        self.service.issue_correction(
            campaign_id="camp_cor",
            actor=ActorRef("human", "user"),
            corrects=[orig_eid],
            reason="O algoz na verdade utilizou um feitiço de escape e não foi derrotado",
            changes=[{"field": "outcome", "contradiction": True}],
            game_time="01 de Janeiro de 304, 12:00",
            game_time_sort=720,
        )

        all_events = tuple(self.store.read("camp_cor"))
        cor_issued = next(e for e in all_events if e.type == "correction.issued")
        self.assertTrue(cor_issued.payload["inconsistency_detected"])
        self.assertEqual(cor_issued.payload["state"], "pendente")

        issues = check_causal_inconsistencies(self.camp_dir, "camp_cor")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["type"], "CAUSAL_INCONSISTENCY")
        self.assertEqual(issues[0]["severity"], "CRITICAL")

        # Resolve inconsistência via issue_correction(..., resolve=True) (P2-8)
        self.service.issue_correction(
            campaign_id="camp_cor",
            actor=ActorRef("human", "user"),
            corrects=[cor_issued.event_id],
            reason="Inconsistência reconciliada pelo mestre",
            changes=[],
            game_time="01 de Janeiro de 304, 12:30",
            game_time_sort=750,
            resolve=True,
        )
        issues_after = check_causal_inconsistencies(self.camp_dir, "camp_cor")
        self.assertEqual(issues_after, [])

    def test_repeated_correction_is_rejected_without_duplicate_compensation(self) -> None:
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
                        "source": "teste",
                    },
                    game_time="01 de Janeiro de 304, 10:00",
                    game_time_sort=600,
                )
            ],
        )
        orig_eid = res_orig.events[0].event_id
        changes = [{"field": "xp_delta", "delta": -100}]

        self.service.issue_correction(
            campaign_id="camp_cor",
            actor=ActorRef("human", "user"),
            corrects=[orig_eid],
            reason="XP indevido",
            changes=changes,
            game_time="01 de Janeiro de 304, 12:00",
            game_time_sort=720,
        )
        with self.assertRaises(DuplicateBatchError):
            self.service.issue_correction(
                campaign_id="camp_cor",
                actor=ActorRef("human", "user"),
                corrects=[orig_eid],
                reason="XP indevido",
                changes=changes,
                game_time="01 de Janeiro de 304, 12:00",
                game_time_sort=720,
            )

        events = tuple(self.store.read("camp_cor"))
        self.assertEqual(sum(1 for e in events if e.type == "correction.issued"), 1)
        compensations = [e for e in events if e.type == "protagonist.progression_changed"]
        self.assertEqual(len(compensations), 2)  # original + uma compensação
        self.assertEqual(compensations[-1].payload["xp_delta"], -100)

    def test_cli_cmd_correct_updates_ficha_and_diario_xp_without_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orig_dirs = helpers.CAMPAIGN_DIRS
            helpers.CAMPAIGN_DIRS = [root]
            try:
                cid = "camp_xp_fix"
                init_campaign_from_templates(cid, title="Campanha XP", protagonist_name="Vael")
                cdir = root / cid

                # Concede +40 XP concluindo objetivo Q1:1 no commit
                res_com = cmd_commit(
                    cid,
                    summary="Vael reconheceu o perímetro e identificou ameaças.",
                    quest_progress="Q1:1",
                    force=True,
                )
                self.assertEqual(res_com["status"], "ok")
                prog_before = parse_progression_from_ficha(cdir / "ficha.md")
                self.assertEqual(prog_before["xp"], 40)

                store = JsonlEventStore(cdir)
                prog_ev = next(e for e in store.read(cid) if e.type == "protagonist.progression_changed")

                # Corrige deduzindo -15 XP via cmd_correct (P1-4)
                res_cor = cmd_correct(
                    cid,
                    event=prog_ev.event_id,
                    reason="Ajuste de XP do objetivo",
                    delta_xp=-15,
                )
                self.assertEqual(res_cor["status"], "ok")

                prog_after = parse_progression_from_ficha(cdir / "ficha.md")
                self.assertEqual(prog_after["xp"], 25)
                ledger_after = parse_xp_ledger_from_diario(cdir / "diario.md")
                self.assertEqual(sum(x["amount"] for x in ledger_after), 25)

                rev = cmd_review(cid)
                xp_issues = [i for i in rev["issues"] if i["type"] == "XP_MISMATCH"]
                self.assertEqual(xp_issues, [])
            finally:
                helpers.CAMPAIGN_DIRS = orig_dirs

    def test_causal_compensation_for_clock_quest_and_arc_updates_projections_immediately_p2_3(self) -> None:
        from application.progression import cmd_quest
        from application.showrunner import cmd_clock
        from council.quests import parse_quests_from_diario
        from resources.clocks import parse_clocks_from_diario
        from resources.ledger import parse_arc_from_diario

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orig_dirs = helpers.CAMPAIGN_DIRS
            helpers.CAMPAIGN_DIRS = [root]
            try:
                cid = "camp_p2_3"
                init_campaign_from_templates(cid, title="Compensação P2-3", protagonist_name="Doran")
                cdir = root / cid

                cmd_clock(cid, add_name="Invasão Sombria", max_steps=4, trigger="Ataque total")
                cmd_clock(cid, advance_name="Invasão Sombria", advance_steps=2)
                cmd_quest(cid, check_target="Q1:1")
                cmd_quest(cid, complete_id="Q1", evidence="Relatório entregue")

                store = JsonlEventStore(cdir)
                all_evts = tuple(store.read(cid))
                clk_ev = next(e for e in reversed(all_evts) if e.type == "clock.advanced")
                q_ev = next(e for e in reversed(all_evts) if e.type == "quest.completed")

                # 1. Compensa relógio (-1 passo) e arco via cmd_correct
                res_cor1 = cmd_correct(
                    cid,
                    event=clk_ev.event_id,
                    reason="Avanço de relógio excessivo no turno anterior",
                    clock="Invasão Sombria:-1",
                    arc_stage="Investigação",
                    arc_title="Sombra nas Fronteiras",
                )
                self.assertEqual(res_cor1.get("status"), "ok")

                clocks_now = parse_clocks_from_diario(cdir / "diario.md")
                inv_clk = next(c for c in clocks_now if c["name"] == "Invasão Sombria")
                self.assertEqual(inv_clk["current"], 1)
                self.assertEqual(inv_clk["status"], "ACTIVE")

                arc_now = parse_arc_from_diario(cdir / "diario.md")
                self.assertEqual(arc_now["stage"], "Investigação")
                self.assertEqual(arc_now["title"], "Sombra nas Fronteiras")

                # 2. Compensa status de missão (Q1 de COMPLETED -> ACTIVE) via cmd_correct
                res_cor2 = cmd_correct(
                    cid,
                    event=q_ev.event_id,
                    reason="Missão concluída prematuramente",
                    quest="Q1:ACTIVE",
                )
                self.assertEqual(res_cor2.get("status"), "ok")

                quests_now = parse_quests_from_diario(cdir / "diario.md")
                q1_now = next(q for q in quests_now if q["id"] == "Q1")
                self.assertEqual(q1_now["status"], "ACTIVE")
                self.assertEqual(
                    (cdir / "diario.md").read_bytes(),
                    (cdir / "projections" / "diario.md").read_bytes(),
                )
            finally:
                helpers.CAMPAIGN_DIRS = orig_dirs

    def test_vital_and_reputation_compensation_applies_relative_delta_and_absolute_values_p1_c(self) -> None:
        from application.factions import cmd_faction
        from council.factions import parse_reputation_from_ficha
        from resources.sheet import parse_ficha_md

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orig_dirs = helpers.CAMPAIGN_DIRS
            helpers.CAMPAIGN_DIRS = [root]
            try:
                cid = "camp_p1_c"
                init_campaign_from_templates(cid, title="Compensação Vital e Rep", protagonist_name="Lyra")
                cdir = root / cid

                cmd_faction(cid, add_name="FTest", desc="Facção de teste")
                res_com = cmd_commit(
                    cid,
                    summary="Lyra enfrentou patrulheiros de FTest e sofreu desgaste.",
                    cost="HP -5, CE -5",
                    faction_rep="FTest:+1",
                    force=True,
                )
                self.assertEqual(res_com.get("status"), "ok")

                ficha_mid = parse_ficha_md(cdir / "ficha.md")
                self.assertEqual(ficha_mid["vitals"]["hp"]["current"], 20)
                self.assertEqual(ficha_mid["vitals"]["ce"]["current"], 25)
                reps_mid = parse_reputation_from_ficha(cdir / "ficha.md")
                self.assertEqual(reps_mid["ftest"]["score"], 1)

                store = JsonlEventStore(cdir)
                all_evts = tuple(store.read(cid))
                sheet_ev = next(e for e in reversed(all_evts) if e.type == "protagonist.sheet_changed")
                rep_ev = next(e for e in reversed(all_evts) if e.type == "faction.reputation_changed")

                # 1. Compensação relativa: --vital hp:+2 (20 -> 22) e --rep FTest:-1 (1 -> 0)
                res_cor1 = cmd_correct(
                    cid,
                    event=sheet_ev.event_id,
                    reason="Custo de HP e ganho de reputação excedentes",
                    vital="hp:+2",
                    rep="FTest:-1",
                )
                self.assertEqual(res_cor1.get("status"), "ok")

                ficha_after1 = parse_ficha_md(cdir / "ficha.md")
                self.assertEqual(ficha_after1["vitals"]["hp"]["current"], 22)
                reps_after1 = parse_reputation_from_ficha(cdir / "ficha.md")
                self.assertEqual(reps_after1["ftest"]["score"], 0)

                # 2. Compensação por sinônimo (mana:+3 -> CE 25 -> 28) e valor absoluto (hp:18 -> 18)
                res_cor2 = cmd_correct(
                    cid,
                    event=rep_ev.event_id,
                    reason="Recuperação parcial de mana",
                    vital="mana:+3",
                )
                self.assertEqual(res_cor2.get("status"), "ok")
                self.assertEqual(parse_ficha_md(cdir / "ficha.md")["vitals"]["ce"]["current"], 28)

                res_cor3 = cmd_correct(
                    cid,
                    event=sheet_ev.event_id,
                    reason="Ajuste absoluto de HP",
                    vital="hp:18",
                )
                self.assertEqual(res_cor3.get("status"), "ok")
                self.assertEqual(parse_ficha_md(cdir / "ficha.md")["vitals"]["hp"]["current"], 18)

                self.assertEqual((cdir / "ficha.md").read_bytes(), (cdir / "projections" / "ficha.md").read_bytes())
                self.assertEqual((cdir / "diario.md").read_bytes(), (cdir / "projections" / "diario.md").read_bytes())
            finally:
                helpers.CAMPAIGN_DIRS = orig_dirs


if __name__ == "__main__":
    unittest.main()
