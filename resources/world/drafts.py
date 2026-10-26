"""resources/world/drafts.py: fábricas de eventos da simulação de mundo.

Constrói ``EventDraft`` para o ciclo, o trabalho e os agendamentos. Sem I/O e sem
decisão de negócio: apenas a forma canônica dos eventos do catálogo v1.
"""

from __future__ import annotations

from typing import Any, Mapping

from contracts.event import ActorRef, EventDraft
from contracts.simulation import WorkItem

SIM_ACTOR = ActorRef(kind="system", id="world_simulation")
SCHEDULE_ACTOR = ActorRef(kind="agent", id="simulation")


def world_ticked_draft(
    *,
    tick_id: str,
    from_game_time: str,
    to_game_time: str,
    game_time_sort: int,
    elapsed_minutes: int,
    trigger: str,
    budget_limit: int,
    selected: int,
    deferred: int,
    seed: int,
) -> EventDraft:
    return EventDraft(
        type="world.ticked",
        schema_version=1,
        actor=SIM_ACTOR,
        game_time=to_game_time,
        game_time_sort=game_time_sort,
        correlation_id=tick_id,
        payload={
            "tick_id": tick_id,
            "from_game_time": from_game_time,
            "to_game_time": to_game_time,
            "elapsed_minutes": int(elapsed_minutes),
            "trigger": trigger,
            "budget_limit": int(budget_limit),
            "selected": int(selected),
            "deferred": int(deferred),
            "seed": int(seed),
        },
    )


def work_completed_draft(
    item: WorkItem,
    *,
    summary: str,
    details: Mapping[str, Any],
    game_time: str,
    game_time_sort: int,
    tick_id: str,
    causation_id: str,
) -> EventDraft:
    return EventDraft(
        type="world.work_completed",
        schema_version=1,
        actor=SIM_ACTOR,
        game_time=game_time,
        game_time_sort=game_time_sort,
        causation_id=causation_id,
        correlation_id=tick_id,
        payload={
            "work_id": item.work_id,
            "kind": item.kind,
            "entity_kind": item.entity_kind,
            "entity_id": item.entity_id,
            "outcome": {"summary": summary, "details": dict(details)},
        },
    )


def work_failed_draft(
    item: WorkItem,
    *,
    error: str,
    attempts: int,
    retry_at_sort: int,
    game_time: str,
    game_time_sort: int,
    tick_id: str,
    causation_id: str,
) -> EventDraft:
    return EventDraft(
        type="world.work_failed",
        schema_version=1,
        actor=SIM_ACTOR,
        game_time=game_time,
        game_time_sort=game_time_sort,
        causation_id=causation_id,
        correlation_id=tick_id,
        payload={
            "work_id": item.work_id,
            "kind": item.kind,
            "entity_kind": item.entity_kind,
            "entity_id": item.entity_id,
            "error": error,
            "attempts": int(attempts),
            "retry_at_sort": int(retry_at_sort),
            "priority": int(item.priority),
            "payload": dict(item.payload),
        },
    )


def work_deferred_draft(
    item: WorkItem,
    *,
    game_time: str,
    game_time_sort: int,
    tick_id: str,
) -> EventDraft:
    return EventDraft(
        type="world.work_deferred",
        schema_version=1,
        actor=SIM_ACTOR,
        game_time=game_time,
        game_time_sort=game_time_sort,
        causation_id=tick_id,
        correlation_id=tick_id,
        payload={
            "work_id": item.work_id,
            "kind": item.kind,
            "entity_kind": item.entity_kind,
            "entity_id": item.entity_id,
            "due_at_sort": int(item.due_at_sort),
            "priority": int(item.priority),
            "payload": dict(item.payload),
            "reason": "budget_exhausted",
            "deferrals": int(item.deferrals),
        },
    )


def scheduled_draft(
    *,
    work_id: str,
    kind: str,
    entity_kind: str,
    entity_id: str,
    due_game_time: str,
    due_at_sort: int,
    priority: int,
    payload: Mapping[str, Any],
    game_time: str,
    game_time_sort: int,
) -> EventDraft:
    return EventDraft(
        type="world.scheduled",
        schema_version=1,
        actor=SCHEDULE_ACTOR,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "work_id": work_id,
            "kind": kind,
            "entity_kind": entity_kind,
            "entity_id": entity_id,
            "due_game_time": due_game_time,
            "due_at_sort": int(due_at_sort),
            "priority": int(priority),
            "payload": dict(payload),
        },
    )


def proposal_rejected_draft(
    *,
    reasons: list[str],
    summary: Mapping[str, Any],
    game_time: str,
    game_time_sort: int,
) -> EventDraft:
    return EventDraft(
        type="proposal.rejected",
        schema_version=1,
        actor=SCHEDULE_ACTOR,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "proposal_kind": "world.schedule",
            "actor_id": "agent",
            "reasons": list(reasons),
            "payload_summary": dict(summary),
        },
    )


__all__ = [
    "SCHEDULE_ACTOR",
    "SIM_ACTOR",
    "proposal_rejected_draft",
    "scheduled_draft",
    "work_completed_draft",
    "work_deferred_draft",
    "work_failed_draft",
    "world_ticked_draft",
]
