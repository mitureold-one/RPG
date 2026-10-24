"""kernel/event_catalog.py: Catálogo mínimo canônico v1 de EventTypes e Upcasters."""

from __future__ import annotations

from typing import Any, Mapping

from contracts.catalog import V1_EVENT_SCHEMAS
from contracts.event import EventType
from kernel.errors import SchemaError
from kernel.schema import validate_schema


def build_v1_catalog() -> dict[str, EventType]:
    """Cria e devolve o catálogo com os 25 tipos canônicos de eventos registrados."""
    return {
        name: EventType(
            type=name,
            schema_version=1,
            payload_schema=schema,
            upcasters={},
        )
        for name, schema in V1_EVENT_SCHEMAS.items()
    }


def upcast_payload(
    event_type: EventType,
    version: int,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Aplica cadeia de upcasters para versão anterior ou rejeita versão futura."""
    if version < 1 or version > event_type.schema_version:
        raise SchemaError(
            f"Versão de schema futura ou inválida '{version}' não suportada para '{event_type.type}' (atual: {event_type.schema_version})",
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
    validate_schema(curr_payload, event_type.payload_schema, path=f"{event_type.type}.payload")
    return curr_payload


__all__ = [
    "V1_EVENT_SCHEMAS",
    "build_v1_catalog",
    "upcast_payload",
]
