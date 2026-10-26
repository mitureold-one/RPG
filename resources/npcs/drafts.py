"""resources/npcs/drafts.py: Fábricas de Drafts Canônicos de NPCs (Gate G3)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence
from contracts.event import ActorRef, EventDraft
from kernel.ids import new_plan_id


def make_npc_promoted_draft(
    npc_id: str,
    from_tier: str = "minor",
    to_tier: str = "major",
    game_time: str = "01 de Outubro de 2026, 10:00",
    game_time_sort: int = 1,
    name: Optional[str] = None,
    goals: Sequence[Any] = (),
    capabilities: Sequence[str] = (),
    resources: Optional[Dict[str, Any]] = None,
    location: Optional[str] = None,
    condition: Optional[str] = None,
    commitments: Sequence[str] = (),
    actor: Optional[ActorRef] = None,
    **kwargs: Any,
) -> EventDraft:
    """Cria um draft canônico de npc.promoted alinhado ao catálogo v1."""
    # Trata caso de chamada legada make_npc_promoted_draft("kael", "Kael", "01/10/2026", 1)
    # onde o 2º arg era nome e o 3º arg era game_time
    if isinstance(to_tier, str) and ("/" in to_tier or "de" in to_tier):
        gt = to_tier
        gts = int(game_time) if isinstance(game_time, int) else (int(game_time_sort) if isinstance(game_time_sort, int) else 1)
        f_tier = "minor"
        t_tier = "major"
        nm = from_tier
    else:
        f_tier = from_tier
        t_tier = to_tier
        gt = game_time
        gts = game_time_sort
        nm = name or kwargs.get("from_tier_or_name")

    act = actor or ActorRef(kind="agent", id="narrative_engine")
    p: Dict[str, Any] = {
        "npc_id": npc_id,
        "from_tier": f_tier,
        "to_tier": t_tier,
        "goals": list(goals),
        "capabilities": list(capabilities),
        "resources": dict(resources or {}),
    }
    if nm is not None:
        p["name"] = nm
    if location is not None:
        p["location"] = location
    if condition is not None:
        p["condition"] = condition
    if commitments:
        p["commitments"] = list(commitments)

    return EventDraft(
        type="npc.promoted",
        schema_version=1,
        actor=act,
        game_time=gt,
        game_time_sort=gts,
        payload=p,
    )


def make_npc_goal_updated_draft(
    npc_id: str,
    goal_id: str,
    description: str,
    horizon: str,
    priority: int,
    status: str,
    game_time: str,
    game_time_sort: int,
    reason: Optional[str] = None,
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de npc.goal_updated."""
    act = actor or ActorRef(kind="npc", id=npc_id)
    p: Dict[str, Any] = {
        "npc_id": npc_id,
        "goal_id": goal_id,
        "description": description,
        "horizon": horizon,
        "priority": priority,
        "status": status,
    }
    if reason is not None:
        p["reason"] = reason

    return EventDraft(
        type="npc.goal_updated",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload=p,
    )


def make_npc_plan_updated_draft(
    npc_id: str,
    plan_id: str,
    goal_id: str,
    title: str,
    steps: Sequence[Dict[str, Any]],
    status: str,
    game_time: str,
    game_time_sort: int,
    alternatives: Sequence[Any] = (),
    completion_conditions: Sequence[Any] = (),
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de npc.plan_updated."""
    act = actor or ActorRef(kind="npc", id=npc_id)
    return EventDraft(
        type="npc.plan_updated",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "npc_id": npc_id,
            "plan_id": plan_id,
            "goal_id": goal_id,
            "title": title,
            "steps": list(steps),
            "status": status,
            "alternatives": list(alternatives),
            "completion_conditions": list(completion_conditions),
        },
    )


def make_npc_plan_draft(
    npc_id: str,
    goal_id: str,
    steps: Sequence[Dict[str, Any]],
    game_time: str,
    game_time_sort: int,
    plan_id: Optional[str] = None,
    title: str = "Plano Operacional",
    status: str = "active",
) -> EventDraft:
    """Alias compatível para geração de draft de plano de NPC."""
    pid = plan_id or new_plan_id()
    return make_npc_plan_updated_draft(
        npc_id=npc_id,
        plan_id=pid,
        goal_id=goal_id,
        title=title,
        steps=steps,
        status=status,
        game_time=game_time,
        game_time_sort=game_time_sort,
    )


def make_npc_relationship_updated_draft(
    npc_id: str,
    target_id: str,
    game_time: str,
    game_time_sort: int,
    trust: int = 0,
    rivalry: int = 0,
    dependency: int = 0,
    debt: int = 0,
    loyalty: int = 0,
    note: str = "",
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de npc.relationship_updated."""
    act = actor or ActorRef(kind="npc", id=npc_id)
    return EventDraft(
        type="npc.relationship_updated",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "npc_id": npc_id,
            "target_id": target_id,
            "trust": trust,
            "rivalry": rivalry,
            "dependency": dependency,
            "debt": debt,
            "loyalty": loyalty,
            "note": note,
        },
    )


make_npc_relationship_draft = make_npc_relationship_updated_draft


def make_npc_updated_draft(
    npc_id: str,
    game_time: str,
    game_time_sort: int,
    changes: Optional[Dict[str, Any]] = None,
    commitments: Optional[Sequence[str]] = None,
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de npc.updated."""
    act = actor or ActorRef(kind="agent", id="narrative_engine")
    p: Dict[str, Any] = {"npc_id": npc_id, "changes": dict(changes or {})}
    if commitments is not None:
        p["commitments"] = list(commitments)
    return EventDraft(
        type="npc.updated",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload=p,
    )


__all__ = [
    "make_npc_promoted_draft",
    "make_npc_updated_draft",
    "make_npc_goal_updated_draft",
    "make_npc_plan_updated_draft",
    "make_npc_plan_draft",
    "make_npc_relationship_updated_draft",
    "make_npc_relationship_draft",
]
