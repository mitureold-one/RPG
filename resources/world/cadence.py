"""resources/world/cadence.py: avanço proporcional de relógios e planos no tempo.

Funções puras. O tempo decorrido é a única causa do avanço; nenhuma delas decide
desfecho de ação, concede XP ou narra. O plano nunca é encerrado pelo tempo.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from contracts.simulation_rules import (
    VALID_STEP_STATUSES,
    active_plan_of,
    is_plan_active,
    steps_for_elapsed,
)


def clock_advance(
    current: int,
    maximum: int,
    elapsed_minutes: int,
    step_minutes: int,
) -> dict[str, Any]:
    """Calcula o avanço saturado de um relógio ativo.

    ``current`` é saturado em ``maximum``; atingir o máximo implica ``BREACHED``.
    ``delta`` reflete apenas o que foi efetivamente aplicado.
    """
    current = max(0, int(current))
    maximum = max(1, int(maximum))
    delta = steps_for_elapsed(elapsed_minutes, step_minutes)
    target = min(maximum, current + delta)
    applied = target - current
    status = "BREACHED" if target >= maximum else "ACTIVE"
    return {
        "delta": applied,
        "current": target,
        "max": maximum,
        "status": status,
        "breached": status == "BREACHED",
    }


def plan_progress(
    steps: Sequence[Mapping[str, Any]],
    current_step_index: int,
    elapsed_minutes: int,
    step_minutes: int,
) -> dict[str, Any]:
    """Avança passos de um plano proporcionalmente ao tempo decorrido.

    Regra: um passo pendente passa a ``in_progress`` e consome um passo de tempo;
    um passo ``in_progress`` passa a ``completed`` e libera o próximo. O plano
    nunca é marcado como concluído aqui — quando todos os passos terminam,
    devolve ``ready=True`` para que a agência decida o desfecho.
    """
    budget = steps_for_elapsed(elapsed_minutes, step_minutes)
    normalized: list[dict[str, Any]] = []
    for raw in steps:
        item = dict(raw)
        status = str(item.get("status", "pending"))
        item["status"] = status if status in VALID_STEP_STATUSES else "pending"
        normalized.append(item)

    index = max(0, min(int(current_step_index), len(normalized)))
    progressed = 0
    while budget > 0 and index < len(normalized):
        current = normalized[index]
        if current["status"] == "pending":
            current["status"] = "in_progress"
            budget -= 1
            progressed += 1
        elif current["status"] == "in_progress":
            current["status"] = "completed"
            budget -= 1
            progressed += 1
            index += 1
        else:
            index += 1

    ready = bool(normalized) and index >= len(normalized) and all(
        step["status"] in ("completed", "skipped") for step in normalized
    )
    return {
        "steps": normalized,
        "current_step_index": index,
        "progressed": progressed,
        "ready": ready,
    }


__all__ = [
    "VALID_STEP_STATUSES",
    "active_plan_of",
    "clock_advance",
    "is_plan_active",
    "plan_progress",
    "steps_for_elapsed",
]
