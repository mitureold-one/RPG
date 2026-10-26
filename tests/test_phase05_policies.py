"""Testes unitários puros das políticas, cadências e tempo canônico da Fase 05."""

from __future__ import annotations

import unittest

from contracts.simulation import TickBudget, WorkItem, WorldView
from contracts.simulation_rules import build_item
from plugins.budget_policy import PriorityBudgetPolicy
from plugins.simulation_policy import TimedSimulationPolicy
from resources.world.cadence import clock_advance, plan_progress
from resources.world.ids import make_tick_id, make_work_id
from temporal.calendar import (
    advance_game_time,
    game_time_to_minutes,
    minutes_to_game_time,
)

CAL12 = {
    "months": [
        "Ventania", "Geada", "Desgelo", "Alvorada", "Sol-Branco", "Éter",
        "Brasa", "Colheita", "Névoa", "Crepúsculo", "Noite-Longa", "Solstício",
    ],
    "days_per_month": [30] * 12,
}


def _item(kind: str, entity: str, due: int = 0, deferrals: int = 0, payload=None) -> WorkItem:
    return build_item(
        kind=kind,
        entity_kind="clock",
        entity_id=entity,
        due_at_sort=due,
        payload=payload or {},
        deferrals=deferrals,
    )


class BudgetAndPriorityTests(unittest.TestCase):
    def test_budget_limit_adaptive_and_hard_cap(self) -> None:
        budget = TickBudget(max_items=8, max_items_per_day=6)
        self.assertEqual(budget.limit(0), 4)
        self.assertEqual(budget.limit(1440), 5)
        self.assertEqual(budget.limit(10080), 8)
        self.assertEqual(budget.limit(100 * 1440), 8)
        self.assertEqual(TickBudget(override=1).limit(10080), 1)

    def test_priority_base_and_starvation(self) -> None:
        clock = _item("clock_advance", "Cerco")
        npc = _item("npc_plan_step", "vespera")
        self.assertEqual(clock.priority, 50)
        self.assertEqual(npc.priority, 30)
        self.assertEqual(npc.with_deferral().deferrals, 1)
        starved = _item("npc_plan_step", "vespera", deferrals=20)
        self.assertEqual(starved.priority_final, 35)
        high = _item("scene_due", "cena", deferrals=20)
        self.assertLessEqual(high.priority_final, 100)

    def test_budget_selects_priority_order_and_defers_rest(self) -> None:
        items = (
            _item("npc_plan_step", "a", due=0),
            _item("clock_advance", "b", due=0),
            _item("scene_due", "c", due=0),
        )
        decision = PriorityBudgetPolicy().select(items, TickBudget(override=2), 1440)
        self.assertEqual([i.kind for i in decision.selected], ["scene_due", "clock_advance"])
        self.assertEqual([i.kind for i in decision.deferred], ["npc_plan_step"])
        self.assertEqual(decision.deferred[0].deferrals, 1)
        self.assertEqual(len(decision.selected) + len(decision.deferred), len(items))

    def test_budget_never_erases_items(self) -> None:
        items = tuple(
            _item("clock_advance", f"clock_{idx}", due=idx) for idx in range(5)
        )
        decision = PriorityBudgetPolicy().select(items, TickBudget(override=1), 0)
        self.assertEqual(len(decision.selected), 1)
        self.assertEqual(len(decision.deferred), 4)
        self.assertEqual(
            {i.work_id for i in decision.selected} | {i.work_id for i in decision.deferred},
            {i.work_id for i in items},
        )


class SimulationPolicyTests(unittest.TestCase):
    def _view(self, **overrides) -> WorldView:
        base = dict(
            campaign_id="sim",
            from_sort=0,
            to_sort=10080,
            elapsed_minutes=10080,
            clocks=({"name": "Cerco", "current": 1, "max": 4, "status": "ACTIVE"},),
            npcs={},
            factions={},
            config={"clock_step_minutes": 1440, "plan_step_minutes": 2880},
        )
        base.update(overrides)
        return WorldView(**base)

    def test_due_includes_active_clock_only(self) -> None:
        view = self._view()
        due = TimedSimulationPolicy().due(view)
        self.assertEqual([i.kind for i in due], ["clock_advance"])

        resolved = self._view(
            clocks=({"name": "Cerco", "current": 4, "max": 4, "status": "RESOLVED"},)
        )
        self.assertEqual(TimedSimulationPolicy().due(resolved), ())

    def test_due_respects_cadence(self) -> None:
        short = self._view(to_sort=60, elapsed_minutes=60)
        self.assertEqual(TimedSimulationPolicy().due(short), ())

    def test_due_removes_completed_and_dedupes(self) -> None:
        view = self._view()
        due = TimedSimulationPolicy().due(view)
        self.assertEqual(len(due), 1)
        completed_view = self._view(completed_ids=frozenset({due[0].work_id}))
        self.assertEqual(TimedSimulationPolicy().due(completed_view), ())

    def test_due_orders_by_priority_then_due(self) -> None:
        view = self._view(
            clocks=(
                {"name": "B", "current": 0, "max": 4, "status": "ACTIVE"},
                {"name": "A", "current": 0, "max": 4, "status": "ACTIVE"},
            ),
            scheduled=(_item("scene_due", "cena", due=0),),
        )
        due = TimedSimulationPolicy().due(view)
        self.assertEqual(due[0].kind, "scene_due")
        self.assertEqual([i.entity_id for i in due[1:]], ["A", "B"])


class CadenceTests(unittest.TestCase):
    def test_clock_saturates_at_max(self) -> None:
        res = clock_advance(current=3, maximum=4, elapsed_minutes=10080, step_minutes=1440)
        self.assertEqual(res["delta"], 1)
        self.assertEqual(res["current"], 4)
        self.assertEqual(res["status"], "BREACHED")

    def test_plan_progress_never_closes_plan(self) -> None:
        steps = [
            {"step_id": "s1", "status": "pending"},
            {"step_id": "s2", "status": "pending"},
        ]
        res = plan_progress(steps, 0, elapsed_minutes=10080, step_minutes=2880)
        self.assertEqual(res["steps"][0]["status"], "completed")
        self.assertEqual(res["steps"][1]["status"], "in_progress")
        self.assertEqual(res["current_step_index"], 1)
        self.assertFalse(res["ready"])

    def test_plan_progress_reports_ready_without_concluding(self) -> None:
        steps = [{"step_id": "s1", "status": "in_progress"}]
        res = plan_progress(steps, 0, elapsed_minutes=2880, step_minutes=2880)
        self.assertTrue(res["ready"])
        self.assertEqual(res["steps"][0]["status"], "completed")


class TemporalRoundTripTests(unittest.TestCase):
    def test_round_trip_named_month_with_declared_calendar(self) -> None:
        date = "5 de Ventania de 304, 08:00"
        sort = game_time_to_minutes(date, calendar=CAL12)
        self.assertEqual(minutes_to_game_time(sort, date, calendar=CAL12), date)

    def test_round_trip_slash_and_day_formats(self) -> None:
        slash = "01/10/300, 10:00"
        self.assertEqual(
            minutes_to_game_time(game_time_to_minutes(slash), slash), "01/10/300, 10:00"
        )
        day = "Dia 7, 09:30"
        self.assertEqual(
            minutes_to_game_time(game_time_to_minutes(day), day), "Dia 7, 09:30"
        )

    def test_advance_uses_declared_calendar(self) -> None:
        self.assertEqual(
            advance_game_time("5 de Ventania de 304, 08:00", 30 * 1440, CAL12),
            "5 de Geada de 304, 08:00",
        )
        self.assertEqual(
            advance_game_time("5 de Ventania de 304, 08:00", 360 * 1440, CAL12),
            "5 de Ventania de 305, 08:00",
        )


class IdentityTests(unittest.TestCase):
    def test_work_and_tick_ids_are_deterministic(self) -> None:
        first = make_work_id("clock_advance", "clock", "Cerco", 100, {"a": 1})
        second = make_work_id("clock_advance", "clock", "Cerco", 100, {"a": 1})
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("wrk_"))
        self.assertEqual(len(first), 30)
        self.assertNotEqual(first, make_work_id("clock_advance", "clock", "Cerco", 101, {"a": 1}))

        tick = make_tick_id("sim", 0, 10080, "time", 0, 3)
        self.assertTrue(tick.startswith("tck_"))
        self.assertEqual(tick, make_tick_id("sim", 0, 10080, "time", 0, 3))


if __name__ == "__main__":
    unittest.main()
