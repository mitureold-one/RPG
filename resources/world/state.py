"""resources/world/state.py: aplicação sequencial de efeitos ao estado de trabalho.

Durante um ciclo vários itens podem tocar a mesma entidade (débito adiado + trabalho
novo). Resolver todos contra a mesma visão congelada regride estado; este módulo
aplica o efeito de cada lote resolvido antes de resolver o próximo item.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping, MutableMapping, MutableSequence

from contracts.event import EventDraft
from contracts.simulation import WorkItem, WorldView


def silent_entities(view: WorldView, due: Iterable[WorkItem]) -> tuple[str, ...]:
    """Entidades com trabalho aberto que não venceram no ciclo (silêncio auditável)."""
    known: set[str] = set()
    for clock in view.clocks:
        if str(clock.get("status", "ACTIVE")).upper() == "ACTIVE":
            known.add(f"clock:{clock.get('name', '')}")
    for npc_id, npc in view.npcs.items():
        if isinstance(npc, Mapping) and npc.get("active_plan"):
            known.add(f"npc:{npc.get('id', npc_id)}")
    touched = {f"{item.entity_kind}:{item.entity_id}" for item in due}
    return tuple(sorted(known - touched))


def clone_state(
    clocks: Iterable[Mapping[str, Any]],
    npcs: Mapping[str, Any],
    factions: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Cópia profunda e mutável do estado tocado pela simulação."""
    return (
        copy.deepcopy([dict(clock) for clock in clocks]),
        copy.deepcopy(dict(npcs)),
        copy.deepcopy(dict(factions)),
    )


def _match_key(mapping: MutableMapping[str, Any], wanted: str, fallback_name: bool = True) -> str | None:
    if wanted in mapping:
        return wanted
    lowered = wanted.strip().lower()
    for key, value in mapping.items():
        if str(key).strip().lower() == lowered:
            return key
        if fallback_name and isinstance(value, Mapping):
            if str(value.get("name", "")).strip().lower() == lowered:
                return key
    return None


def _apply_clock(clocks: MutableSequence[dict[str, Any]], payload: Mapping[str, Any]) -> None:
    name = str(payload.get("name", "")).strip()
    for clock in clocks:
        if str(clock.get("name", "")).strip().lower() == name.lower():
            clock["current"] = int(payload.get("current", clock.get("current", 0)))
            clock["max"] = int(payload.get("max", clock.get("max", 1)))
            clock["status"] = str(payload.get("status", clock.get("status", "ACTIVE")))
            return


def _apply_plan(entity: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    steps = payload.get("steps") or ()
    active = entity.get("active_plan")
    plan = dict(active) if isinstance(active, Mapping) else {}
    plan.update(
        {
            "plan_id": str(payload.get("plan_id", plan.get("plan_id", ""))),
            "goal_id": str(payload.get("goal_id", plan.get("goal_id", ""))),
            "steps": [dict(step) for step in steps if isinstance(step, Mapping)],
            "current_step_index": int(payload.get("current_step_index", 0)),
            "status": str(payload.get("status", plan.get("status", "active"))),
        }
    )
    entity["active_plan"] = plan  # type: ignore[index]


def apply_draft_effects(
    clocks: MutableSequence[dict[str, Any]],
    npcs: MutableMapping[str, Any],
    factions: MutableMapping[str, Any],
    drafts: Iterable[EventDraft],
) -> None:
    """Atualiza o estado de trabalho com os efeitos determinísticos dos drafts."""
    for draft in drafts:
        payload = draft.payload or {}
        if draft.type == "clock.advanced":
            _apply_clock(clocks, payload)
        elif draft.type == "npc.plan_updated":
            npc_id = str(payload.get("npc_id", "")).strip()
            key = _match_key(npcs, npc_id) if npc_id else None
            if key is not None and isinstance(npcs[key], dict):
                _apply_plan(npcs[key], payload)
        elif draft.type == "faction.plan_updated":
            tag = str(payload.get("faction_tag", "")).strip()
            key = _match_key(factions, tag) if tag else None
            if key is not None and isinstance(factions[key], dict):
                _apply_plan(factions[key], payload)


__all__ = ["apply_draft_effects", "clone_state", "silent_entities"]
