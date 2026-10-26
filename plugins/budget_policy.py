"""plugins/budget_policy.py: seleção determinística de trabalho sob orçamento.

Pura e sem I/O. Nunca descarta trabalho: o excedente é adiado com contador de
adiamentos (anti-inanição). O teto explícito vence a fórmula adaptativa.
"""

from __future__ import annotations

from typing import Sequence

from contracts.simulation import TickBudget, TickDecision, WorkItem


class PriorityBudgetPolicy:
    """Implementação padrão de ``BudgetPolicy`` por prioridade e antiguidade."""

    name = "priority_budget_v1"
    version = "1.0.0"

    def select(
        self,
        items: Sequence[WorkItem],
        budget: TickBudget,
        elapsed_minutes: int,
    ) -> TickDecision:
        if not isinstance(budget, TickBudget):
            raise ValueError("budget deve ser TickBudget")
        limit = budget.limit(int(elapsed_minutes))
        ordered = sorted(
            items,
            key=lambda item: (-item.priority_final, item.due_at_sort, item.work_id),
        )
        selected = tuple(ordered[:limit])
        deferred = tuple(item.with_deferral() for item in ordered[limit:])
        return TickDecision(
            selected=selected,
            deferred=deferred,
            limit=limit,
            adaptive=budget.override is None,
        )


__all__ = ["PriorityBudgetPolicy"]
