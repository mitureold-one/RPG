"""resources/npcs/service.py: Serviço de Projeção e Mutações de NPCs em Dois Níveis.

Reconstrói deterministicamente os NpcStates a partir dos eventos canônicos,
gerenciando promoção de minor a major, metas, planos operacionais e vetores relacionais.
Determinismo estrito: sem geração de IDs aleatórios no replay (P1-5).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from resources.npcs.drafts import (
    make_npc_goal_updated_draft,
    make_npc_plan_draft,
    make_npc_plan_updated_draft,
    make_npc_promoted_draft,
    make_npc_relationship_draft,
    make_npc_relationship_updated_draft,
    make_npc_updated_draft,
)
from resources.npcs.model import (
    AgentGoal,
    AgentPlan,
    NpcState,
    PlanStep,
    RelationalVector,
)


def _get_or_create_npc(npcs: Dict[str, Dict[str, Any]], nid: str, name: Optional[str] = None) -> Dict[str, Any]:
    return npcs.setdefault(
        nid,
        {
            "id": nid,
            "name": name or nid,
            "tier": "minor",
            "archetype": "",
            "goals": {},
            "active_plan": None,
            "plans": [],
            "relationships": {},
            "faction_id": None,
            "subgroup_id": None,
            "capabilities": [],
            "resources": {},
            "location": None,
            "condition": "normal",
            "commitments": [],
        },
    )


def project_npcs_state(events: Sequence[Any]) -> Dict[str, NpcState]:
    """Reconstrói deterministicamente o mapa de NpcState a partir do log de eventos."""
    npcs: Dict[str, Dict[str, Any]] = {}

    for ev in events:
        evt = getattr(ev, "event", ev)
        p = evt.payload or {}
        etype = evt.type

        if etype == "npc.updated":
            nid = p.get("npc_id") or p.get("name") or ""
            if not nid:
                continue
            cur = _get_or_create_npc(npcs, nid, p.get("name"))
            if "role" in p:
                cur["archetype"] = p["role"]
            if "faction" in p:
                cur["faction_id"] = p["faction"]
            changes = p.get("changes") or {}
            for k, v in changes.items():
                if k == "role":
                    cur["archetype"] = v
                elif k == "faction":
                    cur["faction_id"] = v
                elif k == "location":
                    cur["location"] = v
                elif k == "condition":
                    cur["condition"] = v
                elif k == "tier":
                    cur["tier"] = v
                elif k == "commitments":
                    cur["commitments"] = list(v) if isinstance(v, (list, tuple)) else [v]
            if "commitments" in p and p["commitments"] is not None:
                cur["commitments"] = list(p["commitments"])

        elif etype == "npc.promoted":
            nid = p.get("npc_id") or ""
            if not nid:
                continue
            cur = _get_or_create_npc(npcs, nid, p.get("name"))
            cur["tier"] = p.get("to_tier", "major")
            if "capabilities" in p and p["capabilities"]:
                cur["capabilities"] = list(p["capabilities"])
            if "resources" in p and p["resources"]:
                cur["resources"].update(p["resources"])
            if "location" in p and p["location"] is not None:
                cur["location"] = p["location"]
            if "condition" in p and p["condition"] is not None:
                cur["condition"] = p["condition"]
            if "goals" in p and p["goals"]:
                for g in p["goals"]:
                    if isinstance(g, dict):
                        gid = g.get("goal_id") or "g_init"
                        cur["goals"][gid] = AgentGoal(
                            goal_id=gid,
                            description=g.get("description", ""),
                            priority=int(g.get("priority", 3)),
                            status=g.get("status", "active"),
                            target_ref=g.get("target_ref"),
                            success_criteria=g.get("reason") or g.get("success_criteria") or "",
                        )
            if "commitments" in p and p["commitments"] is not None:
                cur["commitments"] = list(p["commitments"])

        elif etype in ("npc.goal_updated", "npc.goal_set"):
            nid = p.get("npc_id")
            gid = p.get("goal_id")
            if nid and gid:
                cur = _get_or_create_npc(npcs, nid)
                cur["goals"][gid] = AgentGoal(
                    goal_id=gid,
                    description=p.get("description", ""),
                    priority=int(p.get("priority", 3)),
                    status=p.get("status", "active"),
                    target_ref=p.get("target_ref"),
                    success_criteria=p.get("reason") or p.get("success_criteria") or "",
                )

        elif etype == "npc.plan_updated":
            nid = p.get("npc_id")
            if nid:
                cur = _get_or_create_npc(npcs, nid)
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
                plan = AgentPlan(
                    plan_id=plan_id,
                    goal_id=p.get("goal_id", ""),
                    steps=steps,
                    current_step_index=int(p.get("current_step_index", 0)),
                    status=p.get("status", "active"),
                )
                cur["active_plan"] = plan
                plans_list = cur["plans"]
                p_idx = next((i for i, pl in enumerate(plans_list) if pl.plan_id == plan.plan_id), None)
                if p_idx is not None:
                    plans_list[p_idx] = plan
                else:
                    plans_list.append(plan)

        elif etype in ("npc.relationship_updated", "npc.relationship_mutated"):
            nid = p.get("npc_id")
            tid = p.get("target_id")
            if nid and tid:
                cur = _get_or_create_npc(npcs, nid)
                cur["relationships"][tid] = RelationalVector(
                    target_id=tid,
                    trust=int(p.get("trust", 0)),
                    rivalry=int(p.get("rivalry", 0)),
                    dependency=int(p.get("dependency", 0)),
                    debt=int(p.get("debt", 0)),
                    loyalty=int(p.get("loyalty", 0)),
                )

    result: Dict[str, NpcState] = {}
    for nid, d in npcs.items():
        result[nid] = NpcState(
            id=d["id"],
            name=d["name"],
            tier=d["tier"],
            archetype=d["archetype"],
            goals=tuple(d["goals"].values()),
            active_plan=d["active_plan"],
            plans=tuple(d["plans"]),
            relationships=tuple(d["relationships"].values()),
            faction_id=d["faction_id"],
            subgroup_id=d["subgroup_id"],
            capabilities=tuple(d["capabilities"]),
            resources=dict(d["resources"]),
            location=d["location"],
            condition=d["condition"],
            commitments=tuple(d["commitments"]),
        )
    return result


__all__ = [
    "project_npcs_state",
    "make_npc_promoted_draft",
    "make_npc_updated_draft",
    "make_npc_goal_updated_draft",
    "make_npc_plan_updated_draft",
    "make_npc_plan_draft",
    "make_npc_relationship_updated_draft",
    "make_npc_relationship_draft",
]
