"""resources/npcs/model.py: Modelo de NPCs em Dois Níveis (Minor e Major) para RPGPRO.

Representa agentes com vetores relacionais multidimensionais, metas e planos operacionais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

VALID_NPC_TIERS = {"minor", "major"}
VALID_GOAL_STATUS = {"active", "achieved", "abandoned", "blocked"}
VALID_PLAN_STATUS = {"active", "completed", "abandoned", "suspended"}
VALID_STEP_STATUS = {"pending", "in_progress", "completed", "failed", "skipped"}


@dataclass(frozen=True)
class RelationalVector:
    """Vetor relacional direcional de um NPC para outro alvo."""
    target_id: str
    trust: int = 0         # -3..+3
    rivalry: int = 0       # 0..+3
    dependency: int = 0    # 0..+3
    debt: int = 0          # -3..+3 (positivo: deve ao alvo; negativo: alvo deve)
    loyalty: int = 0       # -3..+3

    def __post_init__(self) -> None:
        if not (-3 <= self.trust <= 3):
            raise ValueError(f"trust fora do intervalo -3..+3: {self.trust}")
        if not (0 <= self.rivalry <= 3):
            raise ValueError(f"rivalry fora do intervalo 0..+3: {self.rivalry}")
        if not (0 <= self.dependency <= 3):
            raise ValueError(f"dependency fora do intervalo 0..+3: {self.dependency}")
        if not (-3 <= self.debt <= 3):
            raise ValueError(f"debt fora do intervalo -3..+3: {self.debt}")
        if not (-3 <= self.loyalty <= 3):
            raise ValueError(f"loyalty fora do intervalo -3..+3: {self.loyalty}")


@dataclass(frozen=True)
class AgentGoal:
    """Objetivo tático ou estratégico de um NPC."""
    goal_id: str
    description: str
    priority: int = 3      # 1..5
    status: str = "active"
    target_ref: Optional[str] = None
    success_criteria: str = ""

    def __post_init__(self) -> None:
        if not (1 <= self.priority <= 5):
            raise ValueError(f"priority fora de 1..5: {self.priority}")
        if self.status not in VALID_GOAL_STATUS:
            raise ValueError(f"status de goal inválido: {self.status}")


@dataclass(frozen=True)
class PlanStep:
    """Passo ordenado de execução de um plano."""
    step_id: str
    order: int
    action_kind: str
    description: str
    status: str = "pending"
    expected_outcome: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_STEP_STATUS:
            raise ValueError(f"status de passo de plano inválido: {self.status}")


@dataclass(frozen=True)
class AgentPlan:
    """Plano operacional sequencial de um NPC."""
    plan_id: str           # pln_<ulid>
    goal_id: str
    steps: Tuple[PlanStep, ...] = ()
    current_step_index: int = 0
    status: str = "active"

    def __post_init__(self) -> None:
        if not self.plan_id.startswith("pln_"):
            raise ValueError(f"plan_id deve iniciar com 'pln_': {self.plan_id}")
        if self.status not in VALID_PLAN_STATUS:
            raise ValueError(f"status de plano inválido: {self.status}")


@dataclass(frozen=True)
class NpcState:
    """Estado persistente e projetado de um NPC na simulação."""
    id: str
    name: str
    tier: str = "minor"    # "minor" | "major"
    archetype: str = ""
    goals: Tuple[AgentGoal, ...] = ()
    active_plan: Optional[AgentPlan] = None
    plans: Tuple[AgentPlan, ...] = ()
    relationships: Tuple[RelationalVector, ...] = ()
    faction_id: Optional[str] = None
    subgroup_id: Optional[str] = None
    capabilities: Tuple[str, ...] = ()
    resources: Dict[str, Any] = field(default_factory=dict)
    location: Optional[str] = None
    condition: str = "normal"
    commitments: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.tier not in VALID_NPC_TIERS:
            raise ValueError(f"tier de NPC inválido: {self.tier}")


__all__ = [
    "VALID_NPC_TIERS",
    "VALID_GOAL_STATUS",
    "VALID_PLAN_STATUS",
    "VALID_STEP_STATUS",
    "RelationalVector",
    "AgentGoal",
    "PlanStep",
    "AgentPlan",
    "NpcState",
]
