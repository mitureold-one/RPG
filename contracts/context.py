"""Contratos de dados e modelos imutáveis para o pipeline de contexto.

Define estruturas de requisição, itens, seções, omissões e payload de contexto
conforme especificação da Fase 04 do RPGPRO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


VALID_HOLDER_KINDS = {"npc", "faction", "subgroup", "protagonist", "player", "human", "universe", "system"}


@dataclass(frozen=True)
class HolderRef:
    """Referência identificadora de um holder de conhecimento ou audiência."""

    kind: str
    id: str

    def __post_init__(self) -> None:
        if self.kind not in VALID_HOLDER_KINDS:
            raise ValueError(f"kind de holder inválido: '{self.kind}' (esperado: {VALID_HOLDER_KINDS})")
        if not self.id or not isinstance(self.id, str):
            raise ValueError("id do holder deve ser string não vazia")


@dataclass(frozen=True)
class ContextScene:
    """Dados espaciotemporais da cena corrente."""

    location: str
    present: tuple[str, ...]
    game_time: str
    game_time_sort: int
    scene_type: str = "standard"

    def __post_init__(self) -> None:
        if not isinstance(self.location, str):
            raise ValueError("location deve ser texto")
        if not isinstance(self.present, tuple):
            object.__setattr__(self, "present", tuple(self.present))
        if not isinstance(self.game_time, str):
            raise ValueError("game_time deve ser texto")
        if not isinstance(self.game_time_sort, int):
            raise ValueError("game_time_sort deve ser inteiro")


@dataclass(frozen=True)
class ContextLimits:
    """Limites numéricos e limiares de corte para o contexto causal."""

    max_npcs: int = 5
    max_factions: int = 3
    max_facts: int = 8
    max_consequences: int = 5
    min_relevance: int = 200

    def __post_init__(self) -> None:
        for attr, val in (
            ("max_npcs", self.max_npcs),
            ("max_factions", self.max_factions),
            ("max_facts", self.max_facts),
            ("max_consequences", self.max_consequences),
            ("min_relevance", self.min_relevance),
        ):
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"{attr} deve ser inteiro não negativo")


@dataclass(frozen=True)
class ContextRequest:
    """Parâmetros e diretrizes da solicitação de montagem de contexto."""

    campaign_id: str
    mode: str
    action: str
    scene: ContextScene
    viewer: HolderRef
    audience: HolderRef
    purpose: str
    focus: tuple[str, ...] = ()
    limits: ContextLimits = field(default_factory=ContextLimits)
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.campaign_id, str) or not self.campaign_id.strip():
            raise ValueError("campaign_id deve ser texto não vazio")
        if not isinstance(self.mode, str) or not self.mode.strip():
            raise ValueError("mode deve ser texto não vazio")
        if not isinstance(self.action, str):
            raise ValueError("action deve ser texto")
        if not isinstance(self.scene, ContextScene):
            raise ValueError("scene deve ser ContextScene")
        if not isinstance(self.viewer, HolderRef):
            raise ValueError("viewer deve ser HolderRef")
        if not isinstance(self.audience, HolderRef):
            raise ValueError("audience deve ser HolderRef")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("purpose deve ser texto não vazio")
        if not isinstance(self.focus, tuple):
            object.__setattr__(self, "focus", tuple(self.focus))


@dataclass(frozen=True)
class ContextItem:
    """Entidade, fato, plano ou restrição selecionado para compor o contexto."""

    kind: str
    id: str
    label: str
    layer: str
    score: int = 0
    reasons: tuple[str, ...] = ()
    availability: str = "known"
    payload: Mapping[str, Any] = field(default_factory=dict)
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("kind deve ser texto não vazio")
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id deve ser texto não vazio")
        if not isinstance(self.label, str):
            raise ValueError("label deve ser texto")
        if self.layer not in ("core", "causal"):
            raise ValueError(f"layer inválido: '{self.layer}' (esperado: 'core' ou 'causal')")
        if not isinstance(self.score, int):
            raise ValueError("score deve ser inteiro")
        if not isinstance(self.reasons, tuple):
            object.__setattr__(self, "reasons", tuple(self.reasons))
        if self.availability not in ("known", "unknown", "unavailable", "inexistent"):
            raise ValueError(f"availability inválida: '{self.availability}'")
        if not isinstance(self.sources, tuple):
            object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True)
class ContextOmission:
    """Classificação formal de uma lacuna ou referência ausente."""

    kind: str
    reference: str
    availability: str
    reason: str
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("kind deve ser texto não vazio")
        if not isinstance(self.reference, str) or not self.reference.strip():
            raise ValueError("reference deve ser texto não vazio")
        if self.availability not in ("unknown", "unavailable", "inexistent"):
            raise ValueError(f"availability de omissão inválida: '{self.availability}'")
        if not isinstance(self.reason, str):
            raise ValueError("reason deve ser texto")
        if not isinstance(self.sources, tuple):
            object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True)
class ContextSection:
    """Seção consolidada de contexto contendo itens e omissões."""

    key: str
    layer: str
    items: tuple[ContextItem, ...] = ()
    omissions: tuple[ContextOmission, ...] = ()
    hash: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("key deve ser texto não vazio")
        if self.layer not in ("core", "causal"):
            raise ValueError(f"layer inválido: '{self.layer}'")
        if not isinstance(self.items, tuple):
            object.__setattr__(self, "items", tuple(self.items))
        if not isinstance(self.omissions, tuple):
            object.__setattr__(self, "omissions", tuple(self.omissions))
        if not isinstance(self.hash, str):
            raise ValueError("hash deve ser texto")


@dataclass(frozen=True)
class ContextQueryHandles:
    """Manipuladores e capacidades de consulta sob demanda disponibilizados à IA."""

    holder: HolderRef
    audience: HolderRef
    purpose: str
    entities: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    commands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.holder, HolderRef):
            raise ValueError("holder deve ser HolderRef")
        if not isinstance(self.audience, HolderRef):
            raise ValueError("audience deve ser HolderRef")
        if not isinstance(self.purpose, str):
            raise ValueError("purpose deve ser texto")
        if not isinstance(self.commands, tuple):
            object.__setattr__(self, "commands", tuple(self.commands))


@dataclass(frozen=True)
class ContextQueryResult:
    """Resultado determinístico de uma consulta pontual sob demanda."""

    kind: str
    id: str
    availability: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    sources: tuple[str, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("kind deve ser texto não vazio")
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id deve ser texto não vazio")
        if self.availability not in ("known", "unknown", "unavailable", "inexistent"):
            raise ValueError(f"availability inválida: '{self.availability}'")
        if not isinstance(self.sources, tuple):
            object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True)
class TurnContext:
    """Payload completo e auditável montado para um turno de ação."""

    version: int
    request: ContextRequest
    core: ContextSection
    causal: ContextSection
    query: ContextQueryHandles
    omissions: tuple[ContextOmission, ...]
    source_last_seq: int
    context_hash: str
    stale: bool
    providers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.version, int):
            raise ValueError("version deve ser inteiro")
        if not isinstance(self.request, ContextRequest):
            raise ValueError("request deve ser ContextRequest")
        if not isinstance(self.core, ContextSection):
            raise ValueError("core deve ser ContextSection")
        if not isinstance(self.causal, ContextSection):
            raise ValueError("causal deve ser ContextSection")
        if not isinstance(self.query, ContextQueryHandles):
            raise ValueError("query deve ser ContextQueryHandles")
        if not isinstance(self.omissions, tuple):
            object.__setattr__(self, "omissions", tuple(self.omissions))
        if not isinstance(self.source_last_seq, int):
            raise ValueError("source_last_seq deve ser inteiro")
        if not isinstance(self.context_hash, str):
            raise ValueError("context_hash deve ser texto")
        if not isinstance(self.stale, bool):
            raise ValueError("stale deve ser booleano")
        if not isinstance(self.providers, tuple):
            object.__setattr__(self, "providers", tuple(self.providers))


__all__ = [
    "ContextItem",
    "ContextLimits",
    "ContextOmission",
    "ContextQueryHandles",
    "ContextQueryResult",
    "ContextRequest",
    "ContextScene",
    "ContextSection",
    "HolderRef",
    "TurnContext",
]
