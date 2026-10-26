"""Contratos da simulação de mundo: trabalho devido, orçamento e decisão de tick.

Portas estruturais (``Protocol``) e value objects imutáveis. Nada aqui faz I/O,
lê arquivos ou chama LLM; implementações vivem em ``plugins/`` e ``resources/world/``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from contracts.serialization import normalize_json_object

WORK_KINDS = (
    "clock_advance",
    "npc_plan_step",
    "faction_plan_step",
    "scene_due",
    "scheduled",
)
WORK_STATUSES = ("scheduled", "pending", "deferred", "completed", "failed", "permanent")
TRIGGERS = ("time", "travel", "rest", "critical_event", "schedule", "manual")
ENTITY_KINDS = ("clock", "npc", "faction", "scene", "world")

BASE_PRIORITY: dict[str, int] = {
    "scene_due": 60,
    "clock_advance": 50,
    "scheduled": 50,
    "faction_plan_step": 40,
    "npc_plan_step": 30,
}

_WORK_ID_RE = re.compile(r"^wrk_[0-9a-f]{26}$")
_TICK_ID_RE = re.compile(r"^tck_[0-9a-f]{26}$")


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} deve ser texto não vazio")
    return value


def _require_int(value: Any, field_name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} deve ser inteiro")
    if value < minimum:
        raise ValueError(f"{field_name} deve ser >= {minimum}")
    return value


def validate_work_id(value: Any) -> str:
    """Valida o formato canônico ``wrk_<26 hex>``."""
    text = _require_text(value, "work_id")
    if not _WORK_ID_RE.match(text):
        raise ValueError("work_id deve ter o formato wrk_<26 hex>")
    return text


def validate_tick_id(value: Any) -> str:
    """Valida o formato canônico ``tck_<26 hex>``."""
    text = _require_text(value, "tick_id")
    if not _TICK_ID_RE.match(text):
        raise ValueError("tick_id deve ter o formato tck_<26 hex>")
    return text


@dataclass(frozen=True)
class WorkItem:
    """Unidade de trabalho devida na simulação."""

    work_id: str
    kind: str
    entity_kind: str
    entity_id: str
    due_at_sort: int
    priority: int = 50
    payload: Mapping[str, Any] = field(default_factory=dict)
    deferrals: int = 0
    attempts: int = 0

    def __post_init__(self) -> None:
        validate_work_id(self.work_id)
        if self.kind not in WORK_KINDS:
            raise ValueError(f"kind inválido: {self.kind!r}")
        if self.entity_kind not in ENTITY_KINDS:
            raise ValueError(f"entity_kind inválido: {self.entity_kind!r}")
        _require_text(self.entity_id, "entity_id")
        _require_int(self.due_at_sort, "due_at_sort")
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise ValueError("priority deve ser inteiro")
        if not (1 <= self.priority <= 100):
            raise ValueError("priority deve estar em 1..100")
        _require_int(self.deferrals, "deferrals")
        _require_int(self.attempts, "attempts")
        object.__setattr__(self, "payload", normalize_json_object(self.payload, "payload"))

    @property
    def priority_final(self) -> int:
        base = max(self.priority, BASE_PRIORITY.get(self.kind, self.priority))
        return min(100, base + min(self.deferrals, 5))

    def with_deferral(self) -> "WorkItem":
        return WorkItem(
            work_id=self.work_id,
            kind=self.kind,
            entity_kind=self.entity_kind,
            entity_id=self.entity_id,
            due_at_sort=self.due_at_sort,
            priority=self.priority,
            payload=dict(self.payload),
            deferrals=self.deferrals + 1,
            attempts=self.attempts,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "kind": self.kind,
            "entity_kind": self.entity_kind,
            "entity_id": self.entity_id,
            "due_at_sort": self.due_at_sort,
            "priority": self.priority,
            "priority_final": self.priority_final,
            "payload": dict(self.payload),
            "deferrals": self.deferrals,
            "attempts": self.attempts,
        }


@dataclass(frozen=True)
class TickBudget:
    """Limites de orçamento de um ciclo de simulação."""

    max_items: int = 8
    max_items_per_day: int = 6
    override: int | None = None

    def __post_init__(self) -> None:
        _require_int(self.max_items, "max_items", 1)
        _require_int(self.max_items_per_day, "max_items_per_day", 1)
        if self.override is not None:
            _require_int(self.override, "override", 1)

    def limit(self, elapsed_minutes: int) -> int:
        """Limite efetivo do ciclo: teto duro explícito ou fórmula adaptativa por dia."""
        _require_int(elapsed_minutes, "elapsed_minutes")
        if self.override is not None:
            return self.override
        days = max(1, (elapsed_minutes + 1439) // 1440)
        adaptive = 4 + elapsed_minutes // 1440
        return max(1, min(self.max_items, self.max_items_per_day * days, adaptive))


@dataclass(frozen=True)
class TickRequest:
    """Pedido de ciclo: identidade, tempo, acionador e orçamento."""

    campaign_id: str
    from_game_time: str
    from_sort: int
    elapsed_minutes: int
    trigger: str = "manual"
    seed: int = 0
    budget: TickBudget = field(default_factory=TickBudget)
    dry_run: bool = False

    def __post_init__(self) -> None:
        _require_text(self.campaign_id, "campaign_id")
        _require_text(self.from_game_time, "from_game_time")
        _require_int(self.from_sort, "from_sort")
        _require_int(self.elapsed_minutes, "elapsed_minutes")
        if self.trigger not in TRIGGERS:
            raise ValueError(f"trigger inválido: {self.trigger!r}")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed deve ser inteiro")
        if not isinstance(self.budget, TickBudget):
            raise ValueError("budget deve ser TickBudget")

    @property
    def to_sort(self) -> int:
        return self.from_sort + self.elapsed_minutes


@dataclass(frozen=True)
class WorldView:
    """Visão imutável e determinística do mundo para as políticas de simulação."""

    campaign_id: str
    from_sort: int
    to_sort: int
    elapsed_minutes: int
    clocks: tuple[Mapping[str, Any], ...] = ()
    npcs: Mapping[str, Any] = field(default_factory=dict)
    factions: Mapping[str, Any] = field(default_factory=dict)
    planned_scenes: tuple[Mapping[str, Any], ...] = ()
    scheduled: tuple[WorkItem, ...] = ()
    deferred: tuple[WorkItem, ...] = ()
    failures: tuple[Mapping[str, Any], ...] = ()
    completed_ids: frozenset[str] = frozenset()
    config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.campaign_id, "campaign_id")
        _require_int(self.from_sort, "from_sort")
        _require_int(self.to_sort, "to_sort")
        _require_int(self.elapsed_minutes, "elapsed_minutes")
        if self.to_sort < self.from_sort:
            raise ValueError("to_sort não pode ser anterior a from_sort")
        object.__setattr__(self, "clocks", tuple(dict(c) for c in self.clocks))
        object.__setattr__(self, "planned_scenes", tuple(dict(s) for s in self.planned_scenes))
        object.__setattr__(self, "scheduled", tuple(self.scheduled))
        object.__setattr__(self, "deferred", tuple(self.deferred))
        object.__setattr__(self, "failures", tuple(dict(f) for f in self.failures))
        object.__setattr__(self, "completed_ids", frozenset(self.completed_ids))
        object.__setattr__(self, "npcs", dict(self.npcs))
        object.__setattr__(self, "factions", dict(self.factions))
        object.__setattr__(self, "config", dict(self.config))


@dataclass(frozen=True)
class TickDecision:
    """Resultado da seleção de trabalho sob orçamento."""

    selected: tuple[WorkItem, ...]
    deferred: tuple[WorkItem, ...]
    limit: int
    adaptive: bool
    silent_entities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_int(self.limit, "limit")


@dataclass(frozen=True)
class WorkOutcome:
    """Resultado determinístico da resolução de um item de trabalho."""

    work_id: str
    kind: str
    status: str
    summary: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""
    retry_at_sort: int | None = None
    attempts: int = 0

    def __post_init__(self) -> None:
        validate_work_id(self.work_id)
        if self.status not in ("completed", "failed"):
            raise ValueError(f"status de outcome inválido: {self.status!r}")
        object.__setattr__(self, "details", normalize_json_object(self.details, "details"))


@runtime_checkable
class SimulationPolicy(Protocol):
    """Decide o trabalho devido no tempo; pura e determinística."""

    name: str
    version: str

    def due(self, view: WorldView) -> tuple[WorkItem, ...]:
        ...


@runtime_checkable
class BudgetPolicy(Protocol):
    """Seleciona trabalho devido sob orçamento, sem descartar o excedente."""

    name: str
    version: str

    def select(
        self,
        items: Sequence[WorkItem],
        budget: TickBudget,
        elapsed_minutes: int,
    ) -> TickDecision:
        ...


__all__ = [
    "BASE_PRIORITY", "ENTITY_KINDS", "TRIGGERS", "WORK_KINDS", "WORK_STATUSES",
    "BudgetPolicy", "SimulationPolicy", "TickBudget", "TickDecision", "TickRequest",
    "WorkItem", "WorkOutcome", "WorldView", "validate_tick_id", "validate_work_id",
]
