"""resources/factions/service.py: Projeção de Estado de Facções (Gate G3).

Reconstrói deterministicamente o mapa de FactionState a partir do log canônico de eventos.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence
from resources.factions.drafts import (
    make_faction_leadership_draft,
    make_faction_plan_draft,
    make_faction_plan_updated_draft,
    make_faction_subgroup_updated_draft,
    make_faction_updated_draft,
)
from resources.factions.model import (
    FactionLeadership,
    FactionState,
    FactionSubgroup,
)
from resources.npcs.model import AgentPlan, PlanStep


def _get_or_create_faction(factions: Dict[str, Dict[str, Any]], tag: str, name: Optional[str] = None) -> Dict[str, Any]:
    t = tag.upper()
    return factions.setdefault(
        t,
        {
            "tag": t,
            "name": name or t,
            "power": 3,
            "scale": "regional",
            "clock": "",
            "rivals": [],
            "leadership": None,
            "subgroups": {},
            "cohesion": 100,
            "active_plan": None,
            "resources": {},
            "collective_goals": [],
            "influence": {},
            "limitations": [],
            "internal_conflicts": [],
        },
    )


def project_factions_state(events: Sequence[Any]) -> Dict[str, FactionState]:
    """Reconstrói deterministicamente o mapa de FactionState a partir do log de eventos canônicos."""
    factions: Dict[str, Dict[str, Any]] = {}

    for ev in events:
        evt = getattr(ev, "event", ev)
        p = evt.payload or {}
        etype = evt.type

        if etype == "faction.reputation_changed":
            tag = p.get("tag") or p.get("faction") or ""
            if tag:
                _get_or_create_faction(factions, tag, p.get("faction") or p.get("name"))

        elif etype == "faction.updated":
            tag = p.get("tag") or ""
            if tag:
                cur = _get_or_create_faction(factions, tag, p.get("name"))
                if "power" in p:
                    cur["power"] = int(p["power"])
                if "scale" in p:
                    cur["scale"] = p["scale"]
                if "clock" in p:
                    cur["clock"] = p["clock"]
                if "rivals" in p and p["rivals"] is not None:
                    cur["rivals"] = list(p["rivals"])
                if "name" in p and p["name"]:
                    cur["name"] = p["name"]
                if "leadership" in p and p["leadership"]:
                    ld = p["leadership"]
                    cur["leadership"] = FactionLeadership(
                        leader_id=ld.get("leader_id", ""),
                        title=ld.get("title", "Líder"),
                        authority_level=int(ld.get("authority_level", 3)),
                        succession_law=ld.get("succession_law", "appointment"),
                        appointed_at=ld.get("appointed_at") or evt.game_time,
                    )
                    if "cohesion_delta" in ld:
                        cur["cohesion"] = max(0, min(100, cur["cohesion"] + int(ld["cohesion_delta"])))
                if "resources" in p and p["resources"]:
                    cur["resources"].update(p["resources"])
                if "collective_goals" in p and p["collective_goals"] is not None:
                    cur["collective_goals"] = list(p["collective_goals"])
                if "influence" in p and p["influence"] is not None:
                    cur["influence"].update(p["influence"])
                if "limitations" in p and p["limitations"] is not None:
                    cur["limitations"] = list(p["limitations"])
                if "internal_conflicts" in p and p["internal_conflicts"] is not None:
                    cur["internal_conflicts"] = list(p["internal_conflicts"])

        elif etype == "faction.subgroup_updated":
            tag = p.get("faction_tag") or ""
            sub_id = p.get("subgroup_id")
            if tag and sub_id:
                cur = _get_or_create_faction(factions, tag)
                loyalty = 100 if p.get("stance_towards_leadership") == "loyal" else (30 if p.get("stance_towards_leadership") == "rebellious" else 70)
                cur["subgroups"][sub_id] = FactionSubgroup(
                    subgroup_id=sub_id,
                    faction_id=tag.upper(),
                    name=p.get("name", sub_id),
                    leader_id=p.get("leader_id"),
                    agenda=p.get("agenda", ""),
                    loyalty_to_faction=loyalty,
                    resources=dict(p.get("resources", {})),
                )

        elif etype == "faction.plan_updated":
            tag = p.get("faction_tag") or ""
            if tag:
                cur = _get_or_create_faction(factions, tag)
                steps_data = p.get("steps", ())
                steps = tuple(
                    PlanStep(
                        step_id=s.get("step_id", f"s_{idx}"),
                        order=int(s.get("order", idx)),
                        action_kind=s.get("action_kind", "action"),
                        description=s.get("description", ""),
                        status=s.get("status", "pending"),
                        expected_outcome=s.get("expected_outcome", ""),
                    )
                    for idx, s in enumerate(steps_data)
                )
                raw_pid = p.get("plan_id")
                if raw_pid:
                    plan_id = raw_pid if raw_pid.startswith("pln_") else f"pln_{raw_pid}"
                else:
                    evt_id = getattr(evt, "event_id", getattr(evt, "id", ""))
                    if evt_id and evt_id.startswith("evt_"):
                        plan_id = f"pln_{evt_id[4:]}"
                    else:
                        seq = getattr(evt, "seq", 0)
                        plan_id = f"pln_{seq:026d}"
                cur["active_plan"] = AgentPlan(
                    plan_id=plan_id,
                    goal_id=p.get("goal_id") or "",
                    steps=steps,
                    current_step_index=0,
                    status=p.get("status", "active"),
                )

    result: Dict[str, FactionState] = {}
    for tag, d in factions.items():
        result[tag] = FactionState(
            tag=d["tag"],
            name=d["name"],
            power=d["power"],
            scale=d["scale"],
            clock=d["clock"],
            rivals=tuple(d["rivals"]),
            leadership=d["leadership"],
            subgroups=tuple(d["subgroups"].values()),
            cohesion=d["cohesion"],
            active_plan=d["active_plan"],
            resources=dict(d["resources"]),
            collective_goals=tuple(d["collective_goals"]),
            influence=dict(d["influence"]),
            limitations=tuple(d["limitations"]),
            internal_conflicts=tuple(d["internal_conflicts"]),
        )
    return result


__all__ = [
    "project_factions_state",
    "make_faction_updated_draft",
    "make_faction_leadership_draft",
    "make_faction_subgroup_updated_draft",
    "make_faction_plan_updated_draft",
    "make_faction_plan_draft",
]
