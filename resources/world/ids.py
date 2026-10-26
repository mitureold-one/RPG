"""resources/world/ids.py: identidade determinística de trabalho e de ciclo.

Os identificadores são funções puras do conteúdo canônico: mesmo estado e mesmos
parâmetros produzem os mesmos ids, o que garante retomada sem duplicação.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from contracts.serialization import canonical_json

WORK_ID_PREFIX = "wrk_"
TICK_ID_PREFIX = "tck_"


def _digest26(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:26]


def make_work_id(
    kind: str,
    entity_kind: str,
    entity_id: str,
    due_at_sort: int,
    payload: Mapping[str, Any] | None = None,
) -> str:
    """Gera ``wrk_<26 hex>`` determinístico para um item de trabalho."""
    material = "|".join(
        (
            str(kind),
            f"{entity_kind}:{entity_id}",
            str(int(due_at_sort)),
            canonical_json(dict(payload or {})),
        )
    )
    return f"{WORK_ID_PREFIX}{_digest26(material)}"


def make_tick_id(
    campaign_id: str,
    from_sort: int,
    to_sort: int,
    trigger: str,
    seed: int,
    queue_revision: int,
) -> str:
    """Gera ``tck_<26 hex>`` determinístico para um ciclo de simulação."""
    material = "|".join(
        (
            str(campaign_id),
            str(int(from_sort)),
            str(int(to_sort)),
            str(trigger),
            str(int(seed)),
            str(int(queue_revision)),
        )
    )
    return f"{TICK_ID_PREFIX}{_digest26(material)}"


__all__ = ["TICK_ID_PREFIX", "WORK_ID_PREFIX", "make_tick_id", "make_work_id"]
