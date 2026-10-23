"""Portas do kernel: contratos que adaptadores e plugins implementam.

As portas são estruturais (``Protocol``) e não fazem I/O. Implementações reais
vivem em ``adapters/``, ``plugins/`` ou ``rulesets/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol, Sequence, runtime_checkable

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


__all__ = [
    "Clock",
    "EventStore",
    "EventStreamView",
    "ProjectionSection",
    "Projector",
]
