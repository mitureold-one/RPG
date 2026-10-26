"""Portas do kernel: contratos que adaptadores e plugins implementam.

As portas são estruturais (``Protocol``) e não fazem I/O. Implementações reais
vivem em ``adapters/``, ``plugins/`` ou ``rulesets/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence, runtime_checkable

from contracts.context import ContextRequest, ContextSection
from contracts.event import AppendResult, Event, EventDraft


@dataclass(frozen=True)
class ProjectionSection:
    """Seção de um arquivo de projeção produzida por um ``Projector``."""

    file: str
    section: str
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.file, str) or not self.file.strip():
            raise ValueError("file deve ser texto não vazio")
        if not isinstance(self.section, str) or not self.section.strip():
            raise ValueError("section deve ser texto não vazio")
        if not isinstance(self.content, str):
            raise ValueError("content deve ser texto")


@dataclass(frozen=True)
class EventStreamView:
    """Visão imutável e ordenada de eventos entregue a um projector."""

    campaign_id: str
    events: tuple[Event, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.campaign_id, str) or not self.campaign_id.strip():
            raise ValueError("campaign_id deve ser texto não vazio")
        events = tuple(self.events)
        if any(not isinstance(event, Event) for event in events):
            raise ValueError("events deve conter apenas Event")
        if any(event.campaign_id != self.campaign_id for event in events):
            raise ValueError("a view não pode misturar campanhas")
        object.__setattr__(self, "events", events)

    @property
    def last_seq(self) -> int:
        return self.events[-1].seq if self.events else 0


@runtime_checkable
class EventStore(Protocol):
    """Registro append-only, ordenado por campanha."""

    def append(
        self,
        campaign_id: str,
        drafts: Sequence[EventDraft],
        expected_last_seq: int | None = None,
    ) -> AppendResult:
        ...

    def read(self, campaign_id: str, after_seq: int = 0) -> Iterable[Event]:
        ...

    def last_seq(self, campaign_id: str) -> int:
        ...


@runtime_checkable
class Projector(Protocol):
    """Projeta um stream de eventos em uma seção de arquivo."""

    file: str
    section: str
    order: int

    def project(self, view: EventStreamView) -> ProjectionSection:
        ...


@runtime_checkable
class Clock(Protocol):
    """Relógio de tempo real; adaptadores podem fixá-lo em testes."""

    def now_utc(self) -> datetime:
        ...


@dataclass(frozen=True)
class Intent:
    """Proposta de ação, plano, objetivo ou revisão epistêmica de um agente."""
    actor_kind: str
    actor_id: str
    intent_kind: str
    description: str
    target_id: str | None = None
    required_claims: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    required_resources: dict[str, int] | None = None
    location: str | None = None
    acts_for_faction: str | None = None
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class ReactionContext:
    """Visão imutável entregue a uma BehaviorPolicy."""
    campaign_id: str
    game_time: str
    game_time_sort: int
    npc_state: Any
    knowledge_view: Any
    present_actors: tuple[str, ...] = ()
    seed: int = 0


@dataclass(frozen=True)
class FactionContext:
    """Visão imutável entregue a uma FactionPolicy."""
    campaign_id: str
    game_time: str
    game_time_sort: int
    faction_state: Any
    knowledge_view: Any
    active_clocks: tuple[dict[str, Any], ...] = ()
    seed: int = 0


@runtime_checkable
class BehaviorPolicy(Protocol):
    """Porta para políticas determinísticas de comportamento de NPC."""
    name: str
    version: str

    def propose(self, ctx: ReactionContext) -> tuple[Intent, ...]:
        ...


@runtime_checkable
class FactionPolicy(Protocol):
    """Porta para políticas determinísticas de facção e subgrupos."""
    name: str
    version: str

    def propose(self, ctx: FactionContext) -> tuple[Intent, ...]:
        ...


@runtime_checkable
class KnowledgeProvider(Protocol):
    """Porta para consulta de conhecimento/crença e construção de KnowledgeView."""
    name: str

    def build_view(
        self,
        events: Sequence[Event],
        holder_kind: str,
        holder_id: str,
        audience_kind: str = "self",
        audience_id: str = "",
        purpose: str = "decision",
    ) -> Any:
        ...


@runtime_checkable
class ContextStateView(Protocol):
    """Porta para leitura imutável do cache derivado de estado da campanha."""

    last_seq: int
    stale: bool

    def npcs(self) -> Mapping[str, Any]: ...
    def factions(self) -> Mapping[str, Any]: ...
    def knowledge(self) -> Sequence[Any]: ...
    def recent_events(self, limit: int = 50) -> Sequence[Any]: ...
    def quests(self) -> Sequence[Any]: ...
    def clocks(self) -> Sequence[Any]: ...
    def arc(self) -> Mapping[str, Any]: ...
    def registered_claims(self) -> Sequence[str]: ...


@runtime_checkable
class ContextProvider(Protocol):
    """Porta para provedores modulares de contexto (núcleo e causal)."""

    key: str
    layer: str
    priority: int

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        ...


_EVENT_STORE_FACTORY: Callable[..., EventStore] | None = None


def register_event_store_factory(factory: Callable[..., EventStore]) -> None:
    global _EVENT_STORE_FACTORY
    _EVENT_STORE_FACTORY = factory


def create_event_store(base_dir: Any, **kwargs: Any) -> EventStore:
    if _EVENT_STORE_FACTORY is None:
        raise RuntimeError("EventStore factory not registered")
    return _EVENT_STORE_FACTORY(base_dir, **kwargs)


__all__ = [
    "BehaviorPolicy",
    "Clock",
    "ContextProvider",
    "ContextStateView",
    "EventStore",
    "EventStreamView",
    "FactionContext",
    "FactionPolicy",
    "Intent",
    "KnowledgeProvider",
    "ProjectionSection",
    "Projector",
    "ReactionContext",
    "create_event_store",
    "register_event_store_factory",
]
