"""Contratos públicos do RPGPRO.

Este pacote contém apenas tipos e protocolos. Não faz I/O, não importa o
kernel e não conhece domínio, Markdown ou regras de jogo.
"""

from contracts.config import CampaignConfig
from contracts.event import (
    ACTOR_KINDS,
    ActorRef,
    AppendResult,
    Event,
    EventDraft,
    EventType,
)
from contracts.ports import (
    Clock,
    EventStore,
    EventStreamView,
    ProjectionSection,
    Projector,
)
from contracts.serialization import canonical_json, normalize_json_object

__all__ = [
    "ACTOR_KINDS",
    "ActorRef",
    "AppendResult",
    "CampaignConfig",
    "Clock",
    "Event",
    "EventDraft",
    "EventStore",
    "EventStreamView",
    "EventType",
    "ProjectionSection",
    "Projector",
    "canonical_json",
    "normalize_json_object",
]
