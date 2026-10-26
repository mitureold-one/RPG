"""resources/factions/drafts.py: Fábricas de Drafts Canônicos de Facções (Gate G3)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence
from contracts.event import ActorRef, EventDraft
from kernel.ids import new_plan_id


def make_faction_updated_draft(
    tag: str,
    name: str,
    game_time: str,
    game_time_sort: int,
    leadership: Optional[Dict[str, Any]] = None,
    collective_goals: Sequence[Any] = (),
    resources: Optional[Dict[str, Any]] = None,
    influence: Optional[Dict[str, Any]] = None,
    limitations: Sequence[Any] = (),
    internal_conflicts: Sequence[Any] = (),
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de faction.updated."""
    act = actor or ActorRef(kind="faction", id=tag.upper())
    p: Dict[str, Any] = {
        "tag": tag.upper(),
        "name": name,
        "collective_goals": list(collective_goals),
        "limitations": list(limitations),
        "internal_conflicts": list(internal_conflicts),
    }
    if leadership is not None:
        p["leadership"] = dict(leadership)
    if resources is not None:
        p["resources"] = dict(resources)
    if influence is not None:
        p["influence"] = dict(influence)

    return EventDraft(
        type="faction.updated",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload=p,
    )


def make_faction_leadership_draft(
    faction_tag: str,
    leader_id: str,
    title: str,
    game_time: str,
    game_time_sort: int,
    authority_level: int = 3,
    succession_law: str = "appointment",
    cohesion_delta: int = 0,
    faction_name: Optional[str] = None,
) -> EventDraft:
    """Draft para atualização de liderança de facção."""
    return make_faction_updated_draft(
        tag=faction_tag,
        name=faction_name or faction_tag.upper(),
        game_time=game_time,
        game_time_sort=game_time_sort,
        leadership={
            "leader_id": leader_id,
            "title": title,
            "authority_level": authority_level,
            "succession_law": succession_law,
            "cohesion_delta": cohesion_delta,
            "appointed_at": game_time,
        },
    )


def make_faction_subgroup_updated_draft(
    faction_tag: str,
    subgroup_id: str,
    name: str,
    leader_id: str,
    stance_towards_leadership: str,
    game_time: str,
    game_time_sort: int,
    agenda: str = "",
    members: Sequence[str] = (),
    resources: Optional[Dict[str, Any]] = None,
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de faction.subgroup_updated."""
    act = actor or ActorRef(kind="faction", id=faction_tag.upper())
    return EventDraft(
        type="faction.subgroup_updated",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "faction_tag": faction_tag.upper(),
            "subgroup_id": subgroup_id,
            "name": name,
            "leader_id": leader_id,
            "stance_towards_leadership": stance_towards_leadership,
            "agenda": agenda,
            "members": list(members),
            "resources": dict(resources or {}),
        },
    )


def make_faction_plan_updated_draft(
    faction_tag: str,
    plan_id: str,
    title: str,
    steps: Sequence[Dict[str, Any]],
    status: str,
    game_time: str,
    game_time_sort: int,
    goal_id: Optional[str] = None,
    actor_subgroup_id: Optional[str] = None,
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de faction.plan_updated."""
    act = actor or ActorRef(kind="faction", id=faction_tag.upper())
    p: Dict[str, Any] = {
        "faction_tag": faction_tag.upper(),
        "plan_id": plan_id,
        "title": title,
        "steps": list(steps),
        "status": status,
    }
    if goal_id is not None:
        p["goal_id"] = goal_id
    if actor_subgroup_id is not None:
        p["actor_subgroup_id"] = actor_subgroup_id

    return EventDraft(
        type="faction.plan_updated",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload=p,
    )


def make_faction_plan_draft(
    faction_tag: str,
    goal_id: str,
    steps: Sequence[Dict[str, Any]],
    game_time: str,
    game_time_sort: int,
    plan_id: Optional[str] = None,
    title: str = "Plano Corporativo",
    status: str = "active",
) -> EventDraft:
    """Alias compatível para geração de draft de plano de facção."""
    pid = plan_id or new_plan_id()
    return make_faction_plan_updated_draft(
        faction_tag=faction_tag,
        plan_id=pid,
        title=title,
        steps=steps,
        status=status,
        game_time=game_time,
        game_time_sort=game_time_sort,
        goal_id=goal_id,
    )


__all__ = [
    "make_faction_updated_draft",
    "make_faction_leadership_draft",
    "make_faction_subgroup_updated_draft",
    "make_faction_plan_updated_draft",
    "make_faction_plan_draft",
]
