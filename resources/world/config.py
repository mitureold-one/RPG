"""resources/world/config.py: configuração do bloco ``simulation:`` de regras.md.

Normalização pura, com defaults conservadores. Um valor inválido nunca derruba a
campanha: ele é substituído pelo default e listado em ``warnings``.
"""

from __future__ import annotations

from typing import Any, Mapping

from contracts.simulation import TickBudget

DEFAULT_SIMULATION: dict[str, int] = {
    "clock_step_minutes": 1440,
    "plan_step_minutes": 2880,
    "max_items": 8,
    "max_items_per_day": 6,
    "retry_backoff_minutes": 60,
    "max_attempts": 3,
}

# Limites aceitos por chave
_BOUNDS: dict[str, tuple[int, int]] = {
    "clock_step_minutes": (60, 525600),
    "plan_step_minutes": (60, 525600),
    "max_items": (1, 64),
    "max_items_per_day": (1, 64),
    "retry_backoff_minutes": (1, 10080),
    "max_attempts": (1, 10),
}


def normalize_simulation(raw: Any) -> dict[str, int]:
    """Coage o bloco declarado em ``dict[str, int]`` com bounds, sem lançar por valor ruim."""
    result = dict(DEFAULT_SIMULATION)
    if not isinstance(raw, Mapping):
        return result
    for key, (minimum, maximum) in _BOUNDS.items():
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool):
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        result[key] = max(minimum, min(maximum, number))
    return result


def budget_from_config(config: Mapping[str, Any], override: int | None = None) -> TickBudget:
    """Constrói :class:`TickBudget` a partir da configuração normalizada."""
    normalized = normalize_simulation(config)
    return TickBudget(
        max_items=normalized["max_items"],
        max_items_per_day=normalized["max_items_per_day"],
        override=override,
    )


def retry_settings(config: Mapping[str, Any]) -> tuple[int, int]:
    """Devolve ``(max_attempts, retry_backoff_minutes)`` normalizados."""
    normalized = normalize_simulation(config)
    return normalized["max_attempts"], normalized["retry_backoff_minutes"]


__all__ = [
    "DEFAULT_SIMULATION",
    "budget_from_config",
    "normalize_simulation",
    "retry_settings",
]
