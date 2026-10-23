"""Contratos do envelope de evento.

``EventDraft`` é o que a aplicação produz. ``Event`` é o fato persistido:
identidade, sequência e tempo real são atribuídos pelo ``EventStore``, nunca
pela aplicação.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Mapping

from contracts.serialization import normalize_json_object

ACTOR_KINDS = frozenset({"human", "agent", "system", "npc", "faction"})
_EVENT_ID_RE = re.compile(r"^evt_[0-9A-HJKMNP-TV-Z]{26}$")


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} deve ser texto não vazio")
    return value


def _require_int(value: Any, field_name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} deve ser inteiro")
    if value < minimum:
        raise ValueError(f"{field_name} deve ser >= {minimum}")
    return value


@dataclass(frozen=True)
class ActorRef:
    """Ator responsável por um evento."""

    kind: str
    id: str

    def __post_init__(self) -> None:
        if self.kind not in ACTOR_KINDS:
            raise ValueError(
                f"actor.kind inválido: {self.kind!r}; esperado um de {sorted(ACTOR_KINDS)}"
            )
        _require_text(self.id, "actor.id")


@dataclass(frozen=True)
class EventDraft:
    """Proposta de evento; o store completa identidade, sequência e tempo real."""

    type: str
    schema_version: int
    actor: ActorRef
    payload: Mapping[str, Any]
    game_time: str | None = None
    game_time_sort: int | None = None
    causation_id: str | None = None
    correlation_id: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.type, "type")
        _require_int(self.schema_version, "schema_version", 1)
        if not isinstance(self.actor, ActorRef):
            raise ValueError("actor deve ser um ActorRef")
        object.__setattr__(self, "payload", normalize_json_object(self.payload, "payload"))
        object.__setattr__(self, "meta", normalize_json_object(self.meta, "meta"))
        if self.game_time is not None:
            _require_text(self.game_time, "game_time")
        if self.game_time_sort is not None:
            _require_int(self.game_time_sort, "game_time_sort", 0)
        if self.causation_id is not None:
            _require_text(self.causation_id, "causation_id")
        if self.correlation_id is not None:
            _require_text(self.correlation_id, "correlation_id")


@dataclass(frozen=True)
class Event:
    """Fato persistido, imutável e ordenado por campanha."""

    event_id: str
    campaign_id: str
    seq: int
    type: str
    schema_version: int
    recorded_at: str
    game_time: str
    game_time_sort: int
    actor: ActorRef
    causation_id: str | None
    correlation_id: str | None
    payload: Mapping[str, Any]
    meta: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not _EVENT_ID_RE.match(self.event_id):
            raise ValueError("event_id deve ter o formato evt_<ulid>")
        _require_text(self.campaign_id, "campaign_id")
        _require_int(self.seq, "seq", 1)
        _require_text(self.type, "type")
        _require_int(self.schema_version, "schema_version", 1)
        _require_text(self.game_time, "game_time")
        _require_int(self.game_time_sort, "game_time_sort", 0)
        if not isinstance(self.actor, ActorRef):
            raise ValueError("actor deve ser um ActorRef")
        if self.causation_id is not None:
            _require_text(self.causation_id, "causation_id")
        if self.correlation_id is not None:
            _require_text(self.correlation_id, "correlation_id")
        try:
            recorded = datetime.fromisoformat(self.recorded_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("recorded_at deve ser ISO-8601") from exc
        if recorded.tzinfo is None or recorded.utcoffset() != timedelta(0):
            raise ValueError("recorded_at deve estar em UTC")
        object.__setattr__(self, "payload", normalize_json_object(self.payload, "payload"))
        object.__setattr__(self, "meta", normalize_json_object(self.meta, "meta"))


@dataclass(frozen=True)
class EventType:
    """Tipo de evento registrado, com schema e cadeia de upcasters."""

    type: str
    schema_version: int
    payload_schema: Mapping[str, Any]
    upcasters: Mapping[int, Callable[[Mapping[str, Any]], Mapping[str, Any]]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        _require_text(self.type, "type")
        _require_int(self.schema_version, "schema_version", 1)
        object.__setattr__(
            self, "payload_schema", normalize_json_object(self.payload_schema, "payload_schema")
        )
        upcasters: dict[int, Callable[[Mapping[str, Any]], Mapping[str, Any]]] = {}
        for version, upcaster in self.upcasters.items():
            if isinstance(version, bool) or not isinstance(version, int) or version < 0:
                raise ValueError("upcasters devem usar versões inteiras >= 0")
            if not callable(upcaster):
                raise ValueError(f"upcaster da versão {version} não é chamável")
            upcasters[version] = upcaster
        object.__setattr__(self, "upcasters", upcasters)


@dataclass(frozen=True)
class AppendResult:
    """Resultado de um append atômico.

    Lote vazio não cria eventos nem avança a sequência: ``first_seq`` e
    ``last_seq`` devolvem a sequência atual (0 para campanha nova).
    """

    events: tuple[Event, ...]
    first_seq: int
    last_seq: int

    def __post_init__(self) -> None:
        if not isinstance(self.events, (tuple, list)):
            raise ValueError("events deve ser uma sequência")
        events = tuple(self.events)
        if any(not isinstance(event, Event) for event in events):
            raise ValueError("events deve conter apenas Event")
        object.__setattr__(self, "events", events)
        _require_int(self.first_seq, "first_seq", 0)
        _require_int(self.last_seq, "last_seq", 0)
        if not events:
            if self.first_seq != self.last_seq:
                raise ValueError("lote vazio deve manter first_seq == last_seq")
            return
        if self.first_seq != events[0].seq:
            raise ValueError("first_seq deve ser a sequência do primeiro evento")
        if self.last_seq != events[-1].seq:
            raise ValueError("last_seq deve ser a sequência do último evento")
        expected = list(range(self.first_seq, self.last_seq + 1))
        if [event.seq for event in events] != expected:
            raise ValueError("eventos devem ter sequência contígua e crescente")
        if len({event.campaign_id for event in events}) != 1:
            raise ValueError("um lote não pode misturar campanhas")


__all__ = [
    "ACTOR_KINDS",
    "ActorRef",
    "AppendResult",
    "Event",
    "EventDraft",
    "EventType",
]
