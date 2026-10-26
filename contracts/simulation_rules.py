"""contracts/simulation_rules.py: helpers puros compartilhados pela simulação.

Sem I/O e sem domínio de negócio: apenas leitura tolerante de planos projetados e
construção canônica de ``WorkItem``. Usado por políticas (plugins) e pelo domínio
(resources/world) sem criar dependência entre camadas.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping, Sequence

from contracts.serialization import canonical_json
from contracts.simulation import BASE_PRIORITY, WorkItem

VALID_STEP_STATUSES = ("pending", "in_progress", "completed", "failed", "skipped")
_OPEN_STEP_STATUSES = ("pending", "in_progress")


def steps_for_elapsed(elapsed_minutes: int, step_minutes: int) -> int:
    """Número de passos proporcionais ao tempo decorrido (divisão inteira)."""
    if elapsed_minutes <= 0 or step_minutes <= 0:
        return 0
    return elapsed_minutes // step_minutes


def is_plan_active(plan: Mapping[str, Any] | None) -> bool:
    if not isinstance(plan, Mapping):
        return False
    return str(plan.get("status", "active")).lower() == "active"


def active_plan_of(entity: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    """Extrai o plano ativo de um NPC/facção projetado, tolerando ausência."""
    if not isinstance(entity, Mapping):
        return None
    plan = entity.get("active_plan")
    if isinstance(plan, Mapping) and is_plan_active(plan):
        return plan
    plans = entity.get("plans")
    if isinstance(plans, Iterable) and not isinstance(plans, (str, bytes, Mapping)):
        for candidate in plans:
            if isinstance(candidate, Mapping) and is_plan_active(candidate):
                return candidate
    return None


def plan_has_open_steps(plan: Mapping[str, Any] | None) -> bool:
    """Há passo pendente ou em andamento no plano."""
    if not isinstance(plan, Mapping):
        return False
    steps = plan.get("steps") or ()
    if not isinstance(steps, Sequence):
        return False
    for step in steps:
        if isinstance(step, Mapping) and str(step.get("status", "pending")) in _OPEN_STEP_STATUSES:
            return True
    return False


def build_item(
    *,
    kind: str,
    entity_kind: str,
    entity_id: str,
    due_at_sort: int,
    payload: Mapping[str, Any] | None = None,
    priority: int | None = None,
    work_id: str | None = None,
    deferrals: int = 0,
    attempts: int = 0,
) -> WorkItem:
    """Constrói um ``WorkItem`` canônico, derivando o ``work_id`` quando ausente.

    O id deriva de ``kind|entity|due|payload`` (mesma regra de ``resources/world/ids``),
    replicada aqui para manter ``contracts`` livre de dependência de ``resources``.
    ``priority=None`` usa a prioridade base do ``kind``.
    """
    body = dict(payload or {})
    resolved_priority = int(priority) if priority is not None else BASE_PRIORITY.get(kind, 50)
    if work_id is None:
        material = "|".join(
            (str(kind), f"{entity_kind}:{entity_id}", str(int(due_at_sort)), canonical_json(body))
        )
        work_id = f"wrk_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:26]}"
    return WorkItem(
        work_id=work_id,
        kind=kind,
        entity_kind=entity_kind,
        entity_id=entity_id,
        due_at_sort=int(due_at_sort),
        priority=resolved_priority,
        payload=body,
        deferrals=int(deferrals),
        attempts=int(attempts),
    )


__all__ = [
    "VALID_STEP_STATUSES",
    "active_plan_of",
    "build_item",
    "is_plan_active",
    "plan_has_open_steps",
    "steps_for_elapsed",
]
