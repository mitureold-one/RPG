"""kernel/event_catalog.py: Catálogo mínimo canônico v1 de EventTypes e Upcasters."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from contracts.event import EventType
from kernel.errors import SchemaError, UnknownEventTypeError
from kernel.schema import validate_schema

# Schemas de payload dos 23+ tipos canônicos v1
_SCHEMAS: dict[str, dict[str, Any]] = {
    "campaign.created": {
        "type": "object",
        "required": ["title", "system", "calendar", "start_game_time", "config_version"],
        "properties": {
            "title": {"type": "string"},
            "system": {"type": "string"},
            "calendar": {"type": "string"},
            "start_game_time": {"type": "string"},
            "config_version": {"type": "integer"},
        },
    },
    "command.executed": {
        "type": "object",
        "required": ["command", "status", "summary"],
        "properties": {
            "command": {"type": "string"},
            "args": {"type": "array"},
            "status": {"type": "string"},
            "summary": {"type": "string"},
        },
    },
    "turn.proposed": {
        "type": "object",
        "required": ["turn", "action", "summary"],
        "properties": {
            "turn": {"type": "integer"},
            "action": {"type": "string"},
            "summary": {"type": "string"},
            "stakes": {"type": "string"},
            "dc": {"type": "integer"},
            "stat": {"type": "string"},
            "target": {"type": "object"},
            "preconditions": {"type": "array"},
        },
    },
    "turn.rejected": {
        "type": "object",
        "required": ["turn", "reasons"],
        "properties": {
            "turn": {"type": "integer"},
            "reasons": {"type": "array"},
        },
    },
    "action.resolved": {
        "type": "object",
        "required": ["turn", "result", "outcome"],
        "properties": {
            "turn": {"type": "integer"},
            "result": {"type": "string"},
            "outcome": {"type": "string"},
            "costs": {"type": "object"},
            "effects": {"type": "object"},
        },
    },
    "turn.committed": {
        "type": "object",
        "required": ["turn", "summary"],
        "properties": {
            "turn": {"type": "integer"},
            "summary": {"type": "string"},
            "scene_type": {"type": "string"},
            "location": {"type": "string"},
            "present": {"type": "array"},
            "vitals": {"type": "object"},
            "costs": {"type": "object"},
        },
    },
    "clock.created": {
        "type": "object",
        "required": ["name", "max", "trigger"],
        "properties": {
            "name": {"type": "string"},
            "max": {"type": "integer", "minimum": 1},
            "trigger": {"type": "string"},
        },
    },
    "clock.advanced": {
        "type": "object",
        "required": ["name", "steps", "current", "max", "status"],
        "properties": {
            "name": {"type": "string"},
            "steps": {"type": "integer"},
            "current": {"type": "integer"},
            "max": {"type": "integer"},
            "status": {"type": "string"},
        },
    },
    "clock.resolved": {
        "type": "object",
        "required": ["name", "status"],
        "properties": {
            "name": {"type": "string"},
            "status": {"type": "string"},
            "xp_granted": {"type": "integer"},
        },
    },
    "quest.created": {
        "type": "object",
        "required": ["quest_id", "title", "type"],
        "properties": {
            "quest_id": {"type": "string"},
            "title": {"type": "string"},
            "type": {"type": "string"},
            "contractor": {"type": ["string", "null"]},
            "clock": {"type": ["string", "null"]},
            "reward": {"type": "object"},
        },
    },
    "quest.objective_completed": {
        "type": "object",
        "required": ["quest_id", "objective_index"],
        "properties": {
            "quest_id": {"type": "string"},
            "objective_index": {"type": "integer"},
            "xp_granted": {"type": "integer"},
        },
    },
    "quest.completed": {
        "type": "object",
        "required": ["quest_id"],
        "properties": {
            "quest_id": {"type": "string"},
            "xp_granted": {"type": "integer"},
            "contractor_rep": {"type": "object"},
        },
    },
    "quest.failed": {
        "type": "object",
        "required": ["quest_id", "reason"],
        "properties": {
            "quest_id": {"type": "string"},
            "reason": {"type": "string"},
            "contractor_rep": {"type": "object"},
        },
    },
    "quest.status_changed": {
        "type": "object",
        "required": ["quest_id", "from", "to"],
        "properties": {
            "quest_id": {"type": "string"},
            "from": {"type": "string"},
            "to": {"type": "string"},
            "reason": {"type": "string"},
        },
    },
    "arc.updated": {
        "type": "object",
        "required": ["title", "question", "stage"],
        "properties": {
            "title": {"type": "string"},
            "question": {"type": "string"},
            "stage": {"type": "string"},
            "scene_name": {"type": "string"},
            "date_time": {"type": "string"},
            "location": {"type": "string"},
            "present": {"type": "array"},
        },
    },
    "scene.planned": {
        "type": "object",
        "required": ["beat", "scene_type"],
        "properties": {
            "beat": {"type": "string"},
            "scene_type": {"type": "string"},
            "actors": {"type": "array"},
        },
    },
    "scene.completed": {
        "type": "object",
        "required": ["index"],
        "properties": {
            "index": {"type": "integer"},
        },
    },
    "npc.updated": {
        "type": "object",
        "required": ["npc_id", "changes"],
        "properties": {
            "npc_id": {"type": "string"},
            "changes": {"type": "object"},
        },
    },
    "faction.reputation_changed": {
        "type": "object",
        "required": ["faction", "delta_rep", "new_score"],
        "properties": {
            "faction": {"type": "string"},
            "delta_rep": {"type": "integer"},
            "new_score": {"type": "integer"},
            "favors": {"type": "integer"},
            "debts": {"type": "integer"},
            "reason": {"type": "string"},
        },
    },
    "protagonist.progression_changed": {
        "type": "object",
        "required": ["xp_delta", "xp_total", "level"],
        "properties": {
            "xp_delta": {"type": "integer"},
            "xp_total": {"type": "integer"},
            "level": {"type": "integer"},
            "attribute_points": {"type": "integer"},
            "ability_points": {"type": "integer"},
            "source": {"type": "string"},
        },
    },
    "protagonist.sheet_changed": {
        "type": "object",
        "required": ["kind", "target", "new_value"],
        "properties": {
            "kind": {"type": "string"},
            "target": {"type": "string"},
            "new_value": {},
            "points_remaining": {"type": "integer"},
            "source": {"type": "string"},
        },
    },
    "prose.recorded": {
        "type": "object",
        "required": ["turn", "text_hash", "text_path"],
        "properties": {
            "turn": {"type": "integer"},
            "text_hash": {"type": "string"},
            "text_path": {"type": "string"},
            "source": {"type": "string"},
            "bytes": {"type": "integer"},
            "scene_type": {"type": "string"},
        },
    },
    "correction.issued": {
        "type": "object",
        "required": ["correction_id", "corrects", "reason", "changes"],
        "properties": {
            "correction_id": {"type": "string"},
            "corrects": {"type": "array"},
            "reason": {"type": "string"},
            "changes": {"type": "array"},
            "state": {"type": "string"},
            "inconsistency_detected": {"type": "boolean"},
        },
    },
    "correction.recomputed": {
        "type": "object",
        "required": ["correction_id", "affected", "outcome"],
        "properties": {
            "correction_id": {"type": "string"},
            "affected": {"type": "array"},
            "outcome": {"type": "string"},
        },
    },
    "projection.rebuilt": {
        "type": "object",
        "required": ["from_seq", "to_seq", "projection_version", "hash"],
        "properties": {
            "from_seq": {"type": "integer"},
            "to_seq": {"type": "integer"},
            "projection_version": {"type": "integer"},
            "hash": {"type": "string"},
        },
    },
}


def build_v1_catalog() -> dict[str, EventType]:
    """Cria e devolve o catálogo com os 25 tipos canônicos de eventos registrados."""
    catalog: dict[str, EventType] = {}
    for name, schema in _SCHEMAS.items():
        catalog[name] = EventType(
            type=name,
            schema_version=1,
            payload_schema=schema,
            upcasters={},
        )
    return catalog


def upcast_payload(
    event_type: EventType,
    version: int,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Aplica cadeia de upcasters para versão anterior ou rejeita versão futura."""
    if version > event_type.schema_version:
        raise SchemaError(
            f"Versão de schema futura '{version}' não suportada para '{event_type.type}' (atual: {event_type.schema_version})",
            details={"type": event_type.type, "version": version},
        )
    curr_payload = dict(payload)
    curr_version = version
    while curr_version < event_type.schema_version:
        upcaster = event_type.upcasters.get(curr_version)
        if not upcaster:
            raise SchemaError(
                f"Upcaster ausente da versão {curr_version} para {curr_version + 1} em '{event_type.type}'",
                details={"type": event_type.type, "version": curr_version},
            )
        curr_payload = dict(upcaster(curr_payload))
        curr_version += 1
    return curr_payload


__all__ = [
    "build_v1_catalog",
    "upcast_payload",
]
