"""Suíte de aceite C11–C17 da Fase 05: simulação de mundo por tempo."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from application.rebuild import rebuild_projections
from application.world_schedule import cmd_queue, cmd_schedule
from application.world_tick import cmd_world_tick
from contracts.event import ActorRef, EventDraft
from resources.factions.service import (
    make_faction_plan_updated_draft,
    make_faction_updated_draft,
)
from resources.npcs.drafts import make_npc_plan_updated_draft, make_npc_promoted_draft
from resources.ledger import parse_diario_md

MONTHS = [
    "Ventania", "Geada", "Desgelo", "Alvorada", "Sol-Branco", "Éter",
    "Brasa", "Colheita", "Névoa", "Crepúsculo", "Noite-Longa", "Solstício",
]

DIARIO = (
    "<!-- schema_version: 1 -->\n"
    "# Diário de Campanha\n\n"
    "### Cena 1: Abertura\n"
    "* **Data & Local:** 5 de Ventania de 304, 08:00 — Fortaleza de Pedra-Negra\n"
    "* **Presentes:** Aemon, Lady Vespera.\n\n"
    "### Relógios de Ameaça & Prazos\n"
    "* **[Cerco]:** 2/4 (Gatilho: Cerco iminente) [ACTIVE]\n\n"
    "### Histórico de Turnos\n"
)

FICHA = (
    "# Ficha do Protagonista\n\n"
    "### Identidade\n"
    "* **Nome:** Aemon\n\n"
    "### Vitais\n"
    "* **Pontos de Vida (PV):** 20/20\n\n"
    "### Atributos\n"
    "* **FORÇA:** 14 (+2)\n\n"
    "### Nível & XP\n"
    "* **Nível:** 1\n"
    "* **XP:** 0/1000\n"
)

NPCS = (
    "# Personagens Não-Jogáveis (NPCs)\n\n"
    "### Lady Vespera\n"
    "* **Atitude Atual:** Neutro\n"
    "* **Papel:** Regente\n"
    "* **Local:** Fortaleza de Pedra-Negra\n\n"
    "### Bob O Guarda\n"
    "* **Atitude Atual:** Neutro\n"
    "* **Papel:** Soldado\n"
    "* **Local:** Fortaleza de Pedra-Negra\n"
)

MUNDO = (
    "# Mundo\n\n"
    "## Facções\n"
    "### Coroa de Ventania (COROA)\n"
    "- Poder: 4\n"
)

REGRAS = (
    "# Regras\n"
    "```yaml\n"
    "system: d20_3gates\n"
    "calendar:\n"
    "  months:\n"
    + "".join(f"    - {month}\n" for month in MONTHS)
    + "  days_per_month: 30\n"
    "simulation:\n"
    "  clock_step_minutes: 1440\n"
    "  plan_step_minutes: 2880\n"
    "  max_items: 8\n"
    "  retry_backoff_minutes: 60\n"
    "  max_attempts: 3\n"
    "```\n"
)


class Phase05WorldTickTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.camp_dir = Path(self.tmp.name) / "sim_camp"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        self.store = JsonlEventStore(self.camp_dir)

        (self.camp_dir / "diario.md").write_text(DIARIO, encoding="utf-8")
        (self.camp_dir / "ficha.md").write_text(FICHA, encoding="utf-8")
        (self.camp_dir / "npcs.md").write_text(NPCS, encoding="utf-8")
        (self.camp_dir / "mundo.md").write_text(MUNDO, encoding="utf-8")
        (self.camp_dir / "regras.md").write_text(REGRAS, encoding="utf-8")

        actor = ActorRef(kind="human", id="gm")
        created = EventDraft(
            type="campaign.created",
            schema_version=1,
            actor=actor,
            game_time="5 de Ventania de 304, 08:00",
            game_time_sort=0,
            payload={
                "title": "Campanha de Simulação",
                "system": "d20_3gates",
                "calendar": {"months": MONTHS, "days_per_month": 30},
                "start_game_time": "5 de Ventania de 304, 08:00",
                "config_version": 1,
            },
            meta={
                "baseline": {
                    "diario.md": DIARIO,
                    "ficha.md": FICHA,
                    "npcs.md": NPCS,
                    "mundo.md": MUNDO,
                    "regras.md": REGRAS,
                }
            },
        )
        promoted = make_npc_promoted_draft(
            "vespera", "minor", "major", "5 de Ventania de 304, 08:00", 1,
            goals=[{"goal_id": "g_cerco", "description": "Sustentar o cerco", "priority": 4}],
        )
        plan = make_npc_plan_updated_draft(
            "vespera", "pln_cerco", "g_cerco", "Cerco da Fortaleza",
            [{"step_id": "s1", "description": "Mobilizar guarda", "status": "pending"},
             {"step_id": "s2", "description": "Fechar portões", "status": "pending"}],
            "active", "5 de Ventania de 304, 08:00", 2,
        )
        faction = make_faction_updated_draft("COROA", "Coroa de Ventania", "5 de Ventania de 304, 08:00", 4)
        faction_plan = make_faction_plan_updated_draft(
            "COROA", "pln_coroa", "Expandir domínio",
            [{"step_id": "f1", "description": "Recrutar", "status": "pending"},
             {"step_id": "f2", "description": "Marchar", "status": "pending"}],
            "active", "5 de Ventania de 304, 08:00", 3,
        )
        self.store.append("sim_camp", [created, promoted, plan, faction, faction_plan])
        rebuild_projections(self.store, "sim_camp", self.camp_dir, emit_audit_event=False)

        from council import helpers

        self._orig_dirs = list(helpers.CAMPAIGN_DIRS)
        helpers.CAMPAIGN_DIRS = [self.camp_dir.parent]

    def tearDown(self) -> None:
        from council import helpers

        helpers.CAMPAIGN_DIRS = self._orig_dirs
        self.tmp.cleanup()

    # ------------------------------------------------------------------ helpers

    def _queue(self) -> dict:
        return json.loads((self.camp_dir / "queue.json").read_text(encoding="utf-8"))

    def _diario(self) -> dict:
        return parse_diario_md(self.camp_dir / "diario.md")

    def _world_events(self, event_type: str | None = None) -> list:
        events = [e for e in self.store.read("sim_camp") if e.type.startswith("world.")]
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events

    def _clock(self, name: str) -> dict | None:
        return next((c for c in self._diario().get("clocks", []) if c["name"] == name), None)

    def _advance(self, minutes: int, **kwargs):
        return cmd_world_tick("sim_camp", minutes=minutes, **kwargs)

    # ---------------------------------------------------------------- C11

    def test_c11_seven_day_jump_advances_clock_and_plans(self) -> None:
        """C11: +7d avança relógio e planos proporcionalmente e a data final é exata."""
        res = self._advance(7 * 1440, trigger="time")

        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["to"], "12 de Ventania de 304, 08:00")
        self.assertEqual(self._diario()["date_time"], "12 de Ventania de 304, 08:00")

        clock = self._clock("Cerco")
        self.assertEqual(clock["current"], 4)
        self.assertEqual(clock["status"], "BREACHED")

        completions = self._world_events("world.work_completed")
        kinds = {e.payload["kind"] for e in completions}
        self.assertEqual(kinds, {"clock_advance", "npc_plan_step", "faction_plan_step"})

        plan_event = [
            e for e in self.store.read("sim_camp") if e.type == "npc.plan_updated"
        ][-1]
        self.assertEqual(plan_event.payload["steps"][0]["status"], "completed")
        self.assertEqual(plan_event.payload["steps"][1]["status"], "in_progress")

        faction_event = [
            e for e in self.store.read("sim_camp") if e.type == "faction.plan_updated"
        ][-1]
        self.assertEqual(faction_event.payload["steps"][0]["status"], "completed")

        tick = self._world_events("world.ticked")[-1]
        self.assertEqual(tick.payload["to_game_time"], "12 de Ventania de 304, 08:00")
        self.assertEqual(tick.payload["elapsed_minutes"], 10080)

        queue = self._queue()
        self.assertEqual(queue["last_tick"]["tick_id"], res["tick_id"])
        self.assertTrue(queue["hash"].startswith("sha256:"))

    def test_c11_rebuild_of_queue_is_stable(self) -> None:
        """C11/C3: rebuild completo reproduz queue.json com o mesmo hash."""
        self._advance(7 * 1440, trigger="time")
        before = self._queue()["hash"]
        rebuild_projections(self.store, "sim_camp", self.camp_dir, force=True, emit_audit_event=True)
        self.assertEqual(self._queue()["hash"], before)

    # ---------------------------------------------------------------- C12

    def test_c12_every_work_event_has_causal_origin(self) -> None:
        """C12: trabalho derivado tem correlation/causation do ciclo; agendado aponta o agendamento."""
        res = self._advance(7 * 1440, trigger="travel")
        tick_id = res["tick_id"]
        for event in self._world_events():
            if event.type == "world.ticked":
                continue
            self.assertEqual(event.correlation_id, tick_id)
            self.assertTrue(event.causation_id)

        schedule = cmd_schedule(
            "sim_camp", at="13 de Ventania de 304, 08:00",
            kind="scene_due", entity="cena_conselho",
            payload=["beat=Conselho de guerra"], priority=70,
        )
        self.assertEqual(schedule["status"], "scheduled")
        self._advance(1440, trigger="schedule")
        completion = next(
            e for e in self._world_events("world.work_completed")
            if e.payload["kind"] == "scene_due"
        )
        schedule_event = next(
            e for e in self._world_events("world.scheduled")
            if e.payload["work_id"] == schedule["work_id"]
        )
        self.assertEqual(completion.causation_id, schedule_event.event_id)

    # ---------------------------------------------------------------- C13

    def test_c13_budget_defers_without_erasing_completed(self) -> None:
        """C13: orçamento 1 conclui o relógio, adia o resto e não apaga o concluído."""
        first = self._advance(7 * 1440, trigger="time", budget=1)
        self.assertEqual(len(first["selected"]), 1)
        self.assertEqual(first["selected"][0]["kind"], "clock_advance")
        self.assertEqual(len(first["deferred"]), 2)
        self.assertEqual(len(self._world_events("world.work_completed")), 1)
        self.assertEqual(len(self._world_events("world.work_deferred")), 2)

        queue = self._queue()
        self.assertEqual(len(queue["deferred"]), 2)
        self.assertEqual({row["kind"] for row in queue["deferred"]}, {"npc_plan_step", "faction_plan_step"})

        drain = self._advance(0, trigger="time")
        self.assertEqual(drain["status"], "ok")
        self.assertEqual(len(drain["selected"]), 2)
        self.assertEqual(len(self._world_events("world.work_completed")), 3)
        self.assertEqual(self._queue()["deferred"], [])

        clock_events = [e for e in self.store.read("sim_camp") if e.type == "clock.advanced"]
        self.assertEqual(len(clock_events), 1)

    # ---------------------------------------------------------------- C14

    def test_c14_retry_of_same_cycle_is_idempotent(self) -> None:
        """C14: reexecutar o mesmo alvo não duplica eventos nem altera a fila."""
        self._advance(7 * 1440, trigger="time")
        self._advance(0, trigger="time")
        last_seq = self.store.last_seq("sim_camp")
        queue_before = self._queue()
        event_count = len(tuple(self.store.read("sim_camp")))

        again = cmd_world_tick("sim_camp", to="12 de Ventania de 304, 08:00", trigger="time")
        self.assertEqual(again["status"], "idempotent")
        self.assertEqual(self.store.last_seq("sim_camp"), last_seq)
        self.assertEqual(len(tuple(self.store.read("sim_camp"))), event_count)
        self.assertEqual(self._queue()["hash"], queue_before["hash"])

    # ---------------------------------------------------------------- C15

    def test_c15_custom_calendar_and_future_schedule(self) -> None:
        """C15: calendário 12x30 consistente em +30d/+1a e agendamento dispara na data exata."""
        thirty = self._advance(30 * 1440, trigger="time")
        self.assertEqual(thirty["to"], "5 de Geada de 304, 08:00")
        self.assertEqual(self._diario()["date_time"], "5 de Geada de 304, 08:00")

        target = "10 de Geada de 304, 12:00"
        scheduled = cmd_schedule(
            "sim_camp", at=target, kind="scene_due", entity="cena_geada",
            payload=["beat=Primeira neve"], priority=80,
        )
        self.assertEqual(scheduled["status"], "scheduled")

        early = cmd_world_tick("sim_camp", to="9 de Geada de 304, 12:00", trigger="schedule")
        self.assertEqual(
            [o for o in early["outcomes"] if o["kind"] == "scene_due"], []
        )

        reached = cmd_world_tick("sim_camp", to=target, trigger="schedule")
        scene_outcomes = [o for o in reached["outcomes"] if o["kind"] == "scene_due"]
        self.assertEqual(len(scene_outcomes), 1)
        self.assertEqual(scene_outcomes[0]["details"]["beat"], "Primeira neve")
        self.assertEqual(reached["to"], target)

        replay = cmd_world_tick("sim_camp", to=target, trigger="schedule")
        self.assertEqual(replay["status"], "idempotent")
        self.assertEqual(
            len([o for o in replay["outcomes"] if o["kind"] == "scene_due"]), 0
        )

    def test_c15_year_jump_keeps_calendar_consistent(self) -> None:
        """C15: +360d (1 ano) retorna ao mesmo dia do calendário declarado."""
        res = self._advance(360 * 1440, trigger="time")
        self.assertEqual(res["to"], "5 de Ventania de 305, 08:00")

    # ---------------------------------------------------------------- C16

    def test_c16_selective_depth_only_due_entities(self) -> None:
        """C16: entidade sem cadência vencida não gera evento e aparece como silenciosa."""
        res = self._advance(60, trigger="rest")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["selected"], [])
        self.assertIn("clock:Cerco", res["silent_entities"])
        self.assertIn("npc:vespera", res["silent_entities"])
        self.assertEqual(
            [e for e in self._world_events() if e.type == "world.work_completed"], []
        )
        self.assertEqual(len(self._world_events("world.ticked")), 1)

    # ---------------------------------------------------------------- C17

    def test_c17_retry_backoff_and_permanent_failure(self) -> None:
        """C17: falha registra tentativas/backoff e vira permanente ao esgotar."""
        scheduled = cmd_schedule(
            "sim_camp", at="5 de Ventania de 304, 09:00",
            kind="clock_advance", entity="Cerco", priority=70,
        )
        self.assertEqual(scheduled["status"], "scheduled")
        # Relógio deixa de estar ACTIVE antes de o agendamento vencer
        from application import cmd_clock

        cmd_clock("sim_camp", resolve_name="Cerco")

        first = cmd_world_tick("sim_camp", to="5 de Ventania de 304, 09:00", trigger="schedule")
        failed = [o for o in first["outcomes"] if o["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["attempts"], 1)

        second = cmd_world_tick("sim_camp", to="5 de Ventania de 304, 10:00", trigger="schedule")
        failed = [o for o in second["outcomes"] if o["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["attempts"], 2)

        waiting = cmd_world_tick("sim_camp", to="5 de Ventania de 304, 11:00", trigger="schedule")
        self.assertEqual([o for o in waiting["outcomes"] if o["status"] == "failed"], [])

        third = cmd_world_tick("sim_camp", to="5 de Ventania de 304, 12:00", trigger="schedule")
        failed = [o for o in third["outcomes"] if o["status"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["attempts"], 3)
        self.assertTrue(failed[0]["permanent"])

        fourth = cmd_world_tick("sim_camp", to="5 de Ventania de 304, 13:00", trigger="schedule")
        self.assertEqual([o for o in fourth["outcomes"] if o["status"] == "failed"], [])

        queue = self._queue()
        self.assertEqual(len(queue["failed"]), 1)
        self.assertTrue(queue["failed"][0]["permanent"])
        self.assertEqual(queue["failed"][0]["attempts"], 3)
        self.assertEqual(queue["failed"][0]["priority"], 70)

    def test_c17_invalid_schedule_rejected_without_mutation(self) -> None:
        """C17: agendamento inválido gera proposal.rejected e nenhum evento world.*."""
        before = len(self._world_events())
        rejected = cmd_schedule(
            "sim_camp", at="5 de Ventania de 304, 09:00",
            kind="clock_advance", entity="Relógio Inexistente",
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertTrue(rejected["reasons"])
        self.assertEqual(len(self._world_events()), before)
        rejection_events = [e for e in self.store.read("sim_camp") if e.type == "proposal.rejected"]
        self.assertEqual(len(rejection_events), 1)

    # ---------------------------------------------------------------- dry-run

    def test_dry_run_writes_nothing(self) -> None:
        """FR-SIM-14: dry-run calcula o ciclo sem gravar evento, projeção ou fila."""
        last_seq = self.store.last_seq("sim_camp")
        queue_path = self.camp_dir / "queue.json"
        before = queue_path.read_text(encoding="utf-8")

        res = self._advance(7 * 1440, trigger="time", dry_run=True)
        self.assertEqual(res["events_planned"], 7)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(self.store.last_seq("sim_camp"), last_seq)
        self.assertEqual(queue_path.read_text(encoding="utf-8"), before)
        self.assertEqual(self._diario()["date_time"], "5 de Ventania de 304, 08:00")

    def test_invalid_budget_and_trigger_are_rejected(self) -> None:
        """FR-SIM-05/FR-SIM-08: orçamento e gatilho inválidos falham sem escrever."""
        last_seq = self.store.last_seq("sim_camp")
        for budget in (0, -1):
            res = cmd_world_tick("sim_camp", minutes=60, budget=budget)
            self.assertIn("error", res)
        invalid_trigger = cmd_world_tick("sim_camp", minutes=60, trigger="bogus")
        self.assertIn("error", invalid_trigger)
        self.assertEqual(self.store.last_seq("sim_camp"), last_seq)

    def test_deferred_plus_new_work_keeps_state_monotonic(self) -> None:
        """Regressão: débito adiado + trabalho novo no mesmo tick não regride estado."""
        self._advance(7 * 1440, trigger="time", budget=1)
        second = self._advance(2880, trigger="time", budget=8)
        self.assertEqual(second["status"], "ok")

        clock = self._clock("Cerco")
        self.assertEqual(clock["current"], 4)
        self.assertEqual(clock["status"], "BREACHED")

        plan_events = [
            e for e in self.store.read("sim_camp") if e.type == "npc.plan_updated"
        ]
        statuses = [step["status"] for step in plan_events[-1].payload["steps"]]
        self.assertEqual(statuses, ["completed", "completed"])

        faction_events = [
            e for e in self.store.read("sim_camp") if e.type == "faction.plan_updated"
        ]
        faction_statuses = [step["status"] for step in faction_events[-1].payload["steps"]]
        self.assertEqual(faction_statuses, ["completed", "completed"])

    def test_duplicate_schedule_is_idempotent(self) -> None:
        """Regressão: reagendar o mesmo trabalho não levanta DuplicateBatchError."""
        first = cmd_schedule(
            "sim_camp", at="6 de Ventania de 304, 09:00", kind="scene_due",
            entity="cena_unica", payload=["beat=Única"],
        )
        seq_after_first = self.store.last_seq("sim_camp")
        second = cmd_schedule(
            "sim_camp", at="6 de Ventania de 304, 09:00", kind="scene_due",
            entity="cena_unica", payload=["beat=Única"],
        )
        self.assertEqual(first["status"], "scheduled")
        self.assertEqual(second["status"], "already_scheduled")
        self.assertEqual(second["work_id"], first["work_id"])
        self.assertEqual(self.store.last_seq("sim_camp"), seq_after_first)
        scheduled = self._world_events("world.scheduled")
        self.assertEqual(len(scheduled), 1)

    def test_queue_order_matches_priority_final(self) -> None:
        """Regressão: queue.json ordena por priority_final, igual à seleção."""
        cmd_schedule(
            "sim_camp", at="5 de Ventania de 304, 09:00", kind="scene_due",
            entity="cena_prioritaria", payload=["beat=Prioritária"], priority=90,
        )
        self._advance(1440, trigger="time", budget=1)
        queue = self._queue()
        finals = [row["priority_final"] for row in queue["deferred"]]
        self.assertEqual(finals, sorted(finals, reverse=True))
        self.assertNotIn(
            "scene_due",
            {row["kind"] for row in queue["deferred"]},
            "a cena de maior prioridade deve ter sido selecionada",
        )

    def test_unknown_month_with_declared_calendar_raises(self) -> None:
        """Regressão: mês fora do calendário declarado não cai silenciosamente em Janeiro."""
        from temporal.calendar import game_time_to_minutes

        with self.assertRaises(ValueError):
            game_time_to_minutes("30 de Solsticio de 304, 23:59", calendar={
                "months": MONTHS, "days_per_month": [30] * 12,
            })

    def test_queue_command_reports_state(self) -> None:
        """queue lê a fila reconstruída sem mutar o log."""
        self._advance(7 * 1440, trigger="time", budget=1)
        last_seq = self.store.last_seq("sim_camp")
        doc = cmd_queue("sim_camp")
        self.assertEqual(len(doc["deferred"]), 2)
        self.assertEqual(doc["last_tick"]["selected"], 1)
        self.assertEqual(self.store.last_seq("sim_camp"), last_seq)


if __name__ == "__main__":
    unittest.main()
