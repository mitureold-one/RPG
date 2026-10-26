"""resources/factions/model.py: Modelos de Facções com Política Interna e Subgrupos (Gate G3).

Define FactionLeadership, FactionSubgroup e FactionState com coesão interna e planos operacionais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from resources.npcs.model import AgentPlan

VALID_SUCCESSION_LAWS = {"hereditary", "elective", "strength", "appointment"}


@dataclass(frozen=True)
class FactionLeadership:
    """Estrutura formal de liderança de uma facção."""
    leader_id: str
    title: str
    authority_level: int = 3   # 1..5
    succession_law: str = "appointment"
    appointed_at: str = ""

    def __post_init__(self) -> None:
        if not (1 <= self.authority_level <= 5):
            raise ValueError(f"authority_level fora de 1..5: {self.authority_level}")
        if self.succession_law not in VALID_SUCCESSION_LAWS:
            raise ValueError(f"succession_law inválida: {self.succession_law}")


@dataclass(frozen=True)
class FactionSubgroup:
    """Subgrupo, ala ou célula interna de uma facção com agenda própria."""
    subgroup_id: str
    faction_id: str
    name: str
    leader_id: Optional[str] = None
    agenda: str = ""
    loyalty_to_faction: int = 100  # 0..100 (porcentagem de alinhamento)
    resources: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0 <= self.loyalty_to_faction <= 100):
            raise ValueError(f"loyalty_to_faction fora de 0..100: {self.loyalty_to_faction}")


@dataclass(frozen=True)
class FactionState:
    """Estado persistente e projetado de uma facção na simulação."""
    tag: str
    name: str
    power: int = 3             # 1..5
    scale: str = "regional"
    clock: str = ""
    rivals: Tuple[str, ...] = ()
    leadership: Optional[FactionLeadership] = None
    subgroups: Tuple[FactionSubgroup, ...] = ()
    cohesion: int = 100        # 0..100 (coesão política interna)
    active_plan: Optional[AgentPlan] = None
    resources: Dict[str, Any] = field(default_factory=dict)
    collective_goals: Tuple[Dict[str, Any], ...] = ()
    influence: Dict[str, Any] = field(default_factory=dict)
    limitations: Tuple[str, ...] = ()
    internal_conflicts: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (1 <= self.power <= 5):
            raise ValueError(f"power fora de 1..5: {self.power}")
        if not (0 <= self.cohesion <= 100):
            raise ValueError(f"cohesion fora de 0..100: {self.cohesion}")


__all__ = [
    "VALID_SUCCESSION_LAWS",
    "FactionLeadership",
    "FactionSubgroup",
    "FactionState",
]
