"""Normalização e serialização canônica de valores JSON.

O kernel não aceita objetos arbitrários em payloads. A normalização converte
``Mapping`` e sequências em ``dict``/``list`` com chaves de texto, rejeita
valores não finitos e garante que a serialização canônica seja estável para
comparação e hash.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence


def _normalize(value: Any, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contém float não finito")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contém chave não textual: {key!r}")
            normalized[key] = _normalize(item, f"{path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise ValueError(f"{path} contém valor não JSON: {type(value).__name__}")


def normalize_json_object(value: Any, field_name: str = "payload") -> dict[str, Any]:
    """Valida e copia um objeto JSON, devolvendo ``dict`` independente."""

    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} deve ser um objeto JSON")
    normalized = _normalize(value, field_name)
    if not isinstance(normalized, dict):
        raise ValueError(f"{field_name} deve ser um objeto JSON")
    return normalized


def canonical_json(value: Any) -> str:
    """Serializa um valor JSON de forma determinística (chaves ordenadas)."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def event_to_dict(event: Any) -> dict[str, Any]:
    """Converte um objeto Event em dict canônico (sem campos operacionais de arquivo)."""
    actor = event.actor
    actor_dict = {"id": actor.id, "kind": actor.kind} if hasattr(actor, "kind") else dict(actor)
    return {
        "actor": actor_dict,
        "campaign_id": event.campaign_id,
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "event_id": event.event_id,
        "game_time": event.game_time,
        "game_time_sort": event.game_time_sort,
        "meta": dict(event.meta),
        "payload": dict(event.payload),
        "recorded_at": event.recorded_at,
        "schema_version": event.schema_version,
        "seq": event.seq,
        "type": event.type,
    }


def hash_event(event: Any) -> str:
    """Calcula o hash SHA-256 canônico de um evento individual."""
    d = event_to_dict(event) if hasattr(event, "event_id") else event
    data = canonical_json(d).encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def hash_batch(events: Sequence[Any]) -> str:
    """Calcula o hash SHA-256 da concatenação canônica dos eventos do lote ordenados por seq."""
    sorted_events = sorted(events, key=lambda e: e.seq if hasattr(e, "seq") else e["seq"])
    buffer = b"".join(
        canonical_json(event_to_dict(e) if hasattr(e, "event_id") else e).encode("utf-8")
        for e in sorted_events
    )
    return f"sha256:{hashlib.sha256(buffer).hexdigest()}"


__all__ = [
    "canonical_json",
    "event_to_dict",
    "hash_batch",
    "hash_event",
    "normalize_json_object",
]
