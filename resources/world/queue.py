"""resources/world/queue.py: índice de fila derivado dos eventos ``world.*``.

A fila é projeção do log: agendamentos, adiamentos, falhas e conclusões são
agregados por ``work_id`` na ordem dos eventos. Consultas e documento ficam em
``resources/world/workqueue.py``.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from resources.world.ids import make_work_id


def _payload_of(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = record.get("payload")
    return dict(payload) if isinstance(payload, Mapping) else {}


def collect(events: Iterable[Any], initial: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Agrega eventos de mundo em um índice por ``work_id``, partindo de um índice inicial."""
    base = initial if isinstance(initial, Mapping) else {}
    scheduled: dict[str, dict[str, Any]] = {
        str(key): dict(value) for key, value in (base.get("scheduled") or {}).items()
    }
    deferred: dict[str, dict[str, Any]] = {
        str(key): dict(value) for key, value in (base.get("deferred") or {}).items()
    }
    failed: dict[str, dict[str, Any]] = {
        str(key): dict(value) for key, value in (base.get("failed") or {}).items()
    }
    completed: set[str] = set(str(value) for value in (base.get("completed") or ()))
    last_tick: dict[str, Any] | None = dict(base["last_tick"]) if base.get("last_tick") else None
    queue_revision = int(base.get("queue_revision", 0))

    for event in events:
        event_type = getattr(event, "type", "")
        payload = getattr(event, "payload", {}) or {}
        event_id = str(getattr(event, "event_id", "") or "")
        if not event_type.startswith("world."):
            continue
        queue_revision += 1
        work_id = str(payload.get("work_id", ""))

        if event_type == "world.scheduled" and work_id:
            scheduled[work_id] = {
                "work_id": work_id,
                "kind": str(payload.get("kind", "")),
                "entity_kind": str(payload.get("entity_kind", "world")),
                "entity_id": str(payload.get("entity_id", "")),
                "due_game_time": str(payload.get("due_game_time", "")),
                "due_at_sort": int(payload.get("due_at_sort", 0)),
                "priority": int(payload.get("priority", 50)),
                "payload": _payload_of(payload),
                "source_event_id": event_id,
            }
        elif event_type == "world.work_deferred" and work_id:
            deferred[work_id] = {
                "work_id": work_id,
                "kind": str(payload.get("kind", "")),
                "entity_kind": str(payload.get("entity_kind", "world")),
                "entity_id": str(payload.get("entity_id", "")),
                "due_at_sort": int(payload.get("due_at_sort", 0)),
                "priority": int(payload.get("priority", 50)),
                "payload": _payload_of(payload),
                "deferrals": int(payload.get("deferrals", 0)),
                "reason": str(payload.get("reason", "")),
            }
        elif event_type == "world.work_failed" and work_id:
            if work_id in completed:
                continue
            failed[work_id] = {
                "work_id": work_id,
                "kind": str(payload.get("kind", "")),
                "entity_kind": str(payload.get("entity_kind", "world")),
                "entity_id": str(payload.get("entity_id", "")),
                "payload": _payload_of(payload),
                "error": str(payload.get("error", "")),
                "attempts": int(payload.get("attempts", 1)),
                "retry_at_sort": int(payload.get("retry_at_sort", 0)),
            }
        elif event_type == "world.work_completed" and work_id:
            completed.add(work_id)
            deferred.pop(work_id, None)
            failed.pop(work_id, None)
            scheduled.pop(work_id, None)
        elif event_type == "world.ticked":
            last_tick = {
                "tick_id": str(payload.get("tick_id", "")),
                "to_game_time": str(payload.get("to_game_time", "")),
                "trigger": str(payload.get("trigger", "")),
                "selected": int(payload.get("selected", 0)),
                "deferred": int(payload.get("deferred", 0)),
            }

    return {
        "scheduled": scheduled,
        "deferred": deferred,
        "failed": failed,
        "completed": completed,
        "last_tick": last_tick,
        "queue_revision": queue_revision,
    }


def from_document(document: Mapping[str, Any] | None) -> dict[str, Any]:
    """Reconstrói um índice de fila a partir de ``queue.json`` (para merge pós-snapshot)."""
    if not isinstance(document, Mapping):
        return {
            "scheduled": {}, "deferred": {}, "failed": {},
            "completed": set(), "last_tick": None, "queue_revision": 0,
        }
    scheduled: dict[str, dict[str, Any]] = {}
    for row in document.get("scheduled") or ():
        if isinstance(row, Mapping) and row.get("work_id"):
            scheduled[str(row["work_id"])] = {
                "work_id": str(row["work_id"]),
                "kind": str(row.get("kind", "")),
                "entity_kind": str(row.get("entity_kind", "world")),
                "entity_id": str(row.get("entity_id", "")),
                "due_game_time": str(row.get("due_game_time", "")),
                "due_at_sort": int(row.get("due_at_sort", 0)),
                "priority": int(row.get("priority", 50)),
                "payload": dict(row.get("payload") or {}),
                "source_event_id": str(row.get("source_event_id", "")),
            }
    deferred: dict[str, dict[str, Any]] = {}
    for row in document.get("deferred") or ():
        if isinstance(row, Mapping) and row.get("work_id"):
            deferred[str(row["work_id"])] = {
                "work_id": str(row["work_id"]),
                "kind": str(row.get("kind", "")),
                "entity_kind": str(row.get("entity_kind", "world")),
                "entity_id": str(row.get("entity_id", "")),
                "due_at_sort": int(row.get("due_at_sort", 0)),
                "priority": int(row.get("priority", 50)),
                "payload": dict(row.get("payload") or {}),
                "deferrals": int(row.get("deferrals", 0)),
                "reason": str(row.get("reason", "")),
            }
    failed: dict[str, dict[str, Any]] = {}
    for row in document.get("failed") or ():
        if isinstance(row, Mapping) and row.get("work_id"):
            failed[str(row["work_id"])] = {
                "work_id": str(row["work_id"]),
                "kind": str(row.get("kind", "")),
                "entity_kind": str(row.get("entity_kind", "world")),
                "entity_id": str(row.get("entity_id", "")),
                "payload": dict(row.get("payload") or {}),
                "error": str(row.get("error", "")),
                "attempts": int(row.get("attempts", 1)),
                "retry_at_sort": int(row.get("retry_at_sort", 0)),
            }
    return {
        "scheduled": scheduled,
        "deferred": deferred,
        "failed": failed,
        "completed": set(),
        "last_tick": dict(document["last_tick"]) if document.get("last_tick") else None,
        "queue_revision": 0,
    }


def schedule_work_id(kind: str, entity_id: str, due_at_sort: int, payload: Mapping[str, Any]) -> str:
    """Identidade determinística de um agendamento."""
    return make_work_id(kind, "world", entity_id, due_at_sort, payload)


__all__ = ["collect", "from_document", "schedule_work_id"]
