"""Normalização e serialização canônica de valores JSON.

O kernel não aceita objetos arbitrários em payloads. A normalização converte
``Mapping`` e sequências em ``dict``/``list`` com chaves de texto, rejeita
valores não finitos e garante que a serialização canônica seja estável para
comparação e hash.
"""

from __future__ import annotations

import json
import math
from typing import Any, Mapping


def _normalize(value: Any, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contém float não finito")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contém chave não textual: {key!r}")
            normalized[key] = _normalize(item, f"{path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise ValueError(f"{path} contém valor não JSON: {type(value).__name__}")


def normalize_json_object(value: Any, field_name: str = "payload") -> dict[str, Any]:
    """Valida e copia um objeto JSON, devolvendo ``dict`` independente."""

    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} deve ser um objeto JSON")
    normalized = _normalize(value, field_name)
    if not isinstance(normalized, dict):
        raise ValueError(f"{field_name} deve ser um objeto JSON")
    return normalized


def canonical_json(value: Any) -> str:
    """Serializa um valor JSON de forma determinística (chaves ordenadas)."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


__all__ = ["canonical_json", "normalize_json_object"]
