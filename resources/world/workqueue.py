"""resources/world/workqueue.py: consultas e documento da fila de simulação.

Funções puras sobre o índice agregado (``resources/world/queue.py``): itens adiados,
agendamentos vencidos, retries elegíveis e o documento ``queue.json``.
"""

from __future__ import annotations

from typing import Any, Mapping

from contracts.simulation import BASE_PRIORITY, WorkItem
from resources.world.config import retry_settings


def _final_priority(kind: str, priority: int, deferrals: int) -> int:
    base = max(int(priority), BASE_PRIORITY.get(kind, int(priority)))
    return min(100, base + min(int(deferrals), 5))


def _item(
    record: Mapping[str, Any],
    *,
    due_at_sort: int,
    priority: int,
    payload: Mapping[str, Any],
    deferrals: int = 0,
    attempts: int = 0,
) -> WorkItem:
    return WorkItem(
        work_id=str(record["work_id"]),
        kind=str(record["kind"]),
        entity_kind=str(record.get("entity_kind", "world")),
        entity_id=str(record.get("entity_id", "")),
        due_at_sort=int(due_at_sort),
        priority=int(priority),
        payload=dict(payload),
        deferrals=int(deferrals),
        attempts=int(attempts),
    )


def deferred_items(index: Mapping[str, Any]) -> tuple[WorkItem, ...]:
    """Adiamentos ainda abertos, reconstruídos como trabalho pendente."""
    items: list[WorkItem] = []
    completed = index.get("completed", set())
    failed = index.get("failed", {})
    for work_id, record in sorted(index.get("deferred", {}).items()):
        if work_id in completed or work_id in failed:
            continue
        items.append(
            _item(
                record,
                due_at_sort=record["due_at_sort"],
                priority=record["priority"],
                payload=record.get("payload", {}),
                deferrals=record.get("deferrals", 0),
            )
        )
    return tuple(items)


def scheduled_items(index: Mapping[str, Any], to_sort: int) -> tuple[WorkItem, ...]:
    """Agendamentos vencidos (``due_at_sort <= to_sort``) ainda não concluídos nem em retry."""
    items: list[WorkItem] = []
    completed = index.get("completed", set())
    failed = index.get("failed", {})
    for work_id, record in sorted(index.get("scheduled", {}).items()):
        if work_id in completed or work_id in failed:
            continue
        if int(record["due_at_sort"]) > int(to_sort):
            continue
        payload = dict(record.get("payload") or {})
        payload["schedule_event_id"] = record.get("source_event_id", "")
        items.append(
            _item(
                record,
                due_at_sort=record["due_at_sort"],
                priority=record["priority"],
                payload=payload,
            )
        )
    return tuple(items)


def retry_items(
    index: Mapping[str, Any],
    to_sort: int,
    config: Mapping[str, Any],
) -> tuple[WorkItem, ...]:
    """Falhas elegíveis para nova tentativa (backoff vencido e tentativas restantes)."""
    max_attempts, _backoff = retry_settings(config)
    items: list[WorkItem] = []
    completed = index.get("completed", set())
    for work_id, record in sorted(index.get("failed", {}).items()):
        if work_id in completed:
            continue
        attempts = int(record.get("attempts", 1))
        if attempts >= max_attempts:
            continue
        if int(record.get("retry_at_sort", 0)) > int(to_sort):
            continue
        items.append(
            _item(
                record,
                due_at_sort=int(record.get("retry_at_sort", to_sort)),
                priority=int(record.get("priority", 50)),
                payload=record.get("payload", {}),
                attempts=attempts,
            )
        )
    return tuple(items)


def queue_document(
    index: Mapping[str, Any],
    last_seq: int,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Documento determinístico de ``queue.json`` (sem hash; o projector calcula)."""
    max_attempts, _backoff = retry_settings(config)
    completed = index.get("completed", set())
    permanent = {
        work_id
        for work_id, record in (index.get("failed") or {}).items()
        if int(record.get("attempts", 1)) >= max_attempts
    }

    pending = [
        {
            "work_id": record["work_id"],
            "kind": record["kind"],
            "entity_kind": record["entity_kind"],
            "entity_id": record["entity_id"],
            "due_at_sort": record["due_at_sort"],
            "priority": record["priority"],
            "priority_final": _final_priority(
                record["kind"], record["priority"], record.get("deferrals", 0)
            ),
            "deferrals": record.get("deferrals", 0),
            "payload": dict(record.get("payload") or {}),
        }
        for work_id, record in index.get("deferred", {}).items()
        if work_id not in completed and work_id not in permanent
    ]
    failed = [
        {
            "work_id": record["work_id"],
            "kind": record["kind"],
            "entity_kind": record.get("entity_kind", "world"),
            "entity_id": record["entity_id"],
            "error": record["error"],
            "attempts": record["attempts"],
            "retry_at_sort": record["retry_at_sort"],
            "priority": record.get("priority", 50),
            "priority_final": _final_priority(
                record["kind"], record.get("priority", 50), 0
            ),
            "payload": dict(record.get("payload") or {}),
            "permanent": record["attempts"] >= max_attempts,
        }
        for record in index.get("failed", {}).values()
    ]
    scheduled = [
        {
            "work_id": record["work_id"],
            "kind": record["kind"],
            "entity_kind": record["entity_kind"],
            "entity_id": record["entity_id"],
            "due_game_time": record["due_game_time"],
            "due_at_sort": record["due_at_sort"],
            "priority": record["priority"],
            "priority_final": _final_priority(record["kind"], record["priority"], 0),
            "payload": dict(record.get("payload") or {}),
        }
        for work_id, record in index.get("scheduled", {}).items()
        if work_id not in completed and work_id not in permanent
    ]

    def _order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            rows,
            key=lambda row: (
                -int(row["priority_final"]),
                int(row["due_at_sort"]),
                row["work_id"],
            ),
        )

    ordered_scheduled = _order(scheduled)
    ordered_deferred = _order(list(pending))
    return {
        "pending": _order(ordered_deferred + ordered_scheduled),
        "deferred": ordered_deferred,
        "failed": sorted(failed, key=lambda row: (row["work_id"],)),
        "scheduled": ordered_scheduled,
        "last_tick": dict(index.get("last_tick") or {}),
        "last_seq": int(last_seq),
        "schema_version": 1,
    }


__all__ = [
    "deferred_items",
    "queue_document",
    "retry_items",
    "scheduled_items",
]
