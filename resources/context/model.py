"""Enums, constantes e validações de modelo puro para o contexto causal."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class ContextLayer(str, Enum):
    """Camadas fundamentais do contexto montado."""

    CORE = "core"
    CAUSAL = "causal"


class Availability(str, Enum):
    """Status de disponibilidade epistêmica de uma informação ou entidade."""

    KNOWN = "known"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    INEXISTENT = "inexistent"


class ContextKind(str, Enum):
    """Tipos de entidades e elementos que compõem itens de contexto."""

    NPC = "npc"
    FACTION = "faction"
    PLAN = "plan"
    QUEST = "quest"
    CLOCK = "clock"
    FACT = "fact"
    CONSEQUENCE = "consequence"
    CLAIM = "claim"
    ARC = "arc"
    CONSTRAINT = "constraint"
    RULESET = "ruleset"
    PROTAGONIST = "protagonist"
    SCENE = "scene"


def validate_item_availability(availability: str) -> str:
    """Valida se uma disponibilidade pertence ao vocabulário canônico."""
    valid = {a.value for a in Availability}
    if availability not in valid:
        raise ValueError(f"Disponibilidade inválida: '{availability}' (esperado: {valid})")
    return availability


def validate_context_layer(layer: str) -> str:
    """Valida se uma camada pertence ao vocabulário canônico."""
    valid = {l.value for l in ContextLayer}
    if layer not in valid:
        raise ValueError(f"Camada de contexto inválida: '{layer}' (esperado: {valid})")
    return layer


__all__ = [
    "Availability",
    "ContextKind",
    "ContextLayer",
    "validate_context_layer",
    "validate_item_availability",
]
