"""plugins/simulation_policy.py: política determinística de trabalho devido no tempo.

Pura e sem I/O. Decide o que venceu no intervalo (relógios, passos de plano de NPC
e de facção), o que foi agendado para aquele instante, o que foi adiado e o que
pode ser tentado de novo. Não resolve, não grava e não consulta arquivos.
"""

from __future__ import annotations

from typing import Any, Mapping

from contracts.simulation import WorkItem, WorldView
from contracts.simulation_rules import (
    active_plan_of,
    build_item,
    plan_has_open_steps,
    steps_for_elapsed,
)


class TimedSimulationPolicy:
    """Implementação padrão de ``SimulationPolicy`` baseada em cadência declarada."""

    name = "timed_simulation_v1"
    version = "1.0.0"

    def due(self, view: WorldView) -> tuple[WorkItem, ...]:
        config = view.config or {}
        clock_step = int(config.get("clock_step_minutes", 1440))
        plan_step = int(config.get("plan_step_minutes", 2880))
        items: list[WorkItem] = []

        # 1. Relógios ativos com passo proporcional vencido
        if steps_for_elapsed(view.elapsed_minutes, clock_step) > 0:
            for clock in view.clocks:
                if str(clock.get("status", "ACTIVE")).upper() != "ACTIVE":
                    continue
                name = str(clock.get("name", "")).strip()
                if not name:
                    continue
                items.append(
                    build_item(
                        kind="clock_advance",
                        entity_kind="clock",
                        entity_id=name,
                        due_at_sort=view.from_sort,
                        payload={
                            "clock": name,
                            "elapsed_minutes": int(view.elapsed_minutes),
                            "step_minutes": clock_step,
                        },
                    )
                )

        # 2. Planos ativos de NPC e de facção
        if steps_for_elapsed(view.elapsed_minutes, plan_step) > 0:
            for npc_id, npc in sorted(view.npcs.items()):
                if not isinstance(npc, Mapping):
                    continue
                plan = active_plan_of(npc)
                if plan is None or not plan_has_open_steps(plan):
                    continue
                items.append(
                    build_item(
                        kind="npc_plan_step",
                        entity_kind="npc",
                        entity_id=str(npc.get("id", npc_id)),
                        due_at_sort=view.from_sort,
                        payload={
                            "plan_id": str(plan.get("plan_id", "")),
                            "goal_id": str(plan.get("goal_id", "")),
                            "title": str(plan.get("title", "")),
                            "elapsed_minutes": int(view.elapsed_minutes),
                            "step_minutes": plan_step,
                        },
                    )
                )
            for tag, faction in sorted(view.factions.items()):
                if not isinstance(faction, Mapping):
                    continue
                plan = active_plan_of(faction)
                if plan is None or not plan_has_open_steps(plan):
                    continue
                items.append(
                    build_item(
                        kind="faction_plan_step",
                        entity_kind="faction",
                        entity_id=str(faction.get("tag", tag)),
                        due_at_sort=view.from_sort,
                        payload={
                            "plan_id": str(plan.get("plan_id", "")),
                            "goal_id": str(plan.get("goal_id", "")),
                            "title": str(plan.get("title", "")),
                            "elapsed_minutes": int(view.elapsed_minutes),
                            "step_minutes": plan_step,
                        },
                    )
                )

        # 3. Agendamentos vencidos e adiamentos abertos
        items.extend(view.scheduled)
        items.extend(view.deferred)

        # 4. Falhas elegíveis para nova tentativa (backoff já vencido)
        for failure in view.failures:
            try:
                items.append(
                    WorkItem(
                        work_id=str(failure["work_id"]),
                        kind=str(failure["kind"]),
                        entity_kind=str(failure.get("entity_kind", "world")),
                        entity_id=str(failure.get("entity_id", "")),
                        due_at_sort=int(failure.get("retry_at_sort", view.to_sort)),
                        priority=int(failure.get("priority", 50)),
                        payload=dict(failure.get("payload") or {}),
                        attempts=int(failure.get("attempts", 1)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

        return _dedupe_sorted(items, view.completed_ids)


def _dedupe_sorted(items: list[WorkItem], completed: frozenset[str]) -> tuple[WorkItem, ...]:
    """Remove concluídos e duplicatas por ``work_id``, mantendo o item mais adiantado."""
    chosen: dict[str, WorkItem] = {}
    for item in items:
        if item.work_id in completed:
            continue
        current = chosen.get(item.work_id)
        if current is None or (item.deferrals, item.attempts) > (current.deferrals, current.attempts):
            chosen[item.work_id] = item
    ordered = sorted(chosen.values(), key=lambda item: (-item.priority_final, item.due_at_sort, item.work_id))
    return tuple(ordered)


__all__ = ["TimedSimulationPolicy"]
