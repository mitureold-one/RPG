"""contracts/catalog.py: Schemas de payload dos 38 tipos canônicos v1 de eventos (25 base + 13 da Fase 03)."""

from __future__ import annotations

from typing import Any

_S = {"type": "string"}
_I = {"type": "integer"}
_B = {"type": "boolean"}
_A = {"type": "array"}
_O = {"type": "object"}
_SN = {"type": ["string", "null"]}
_IN = {"type": ["integer", "null"]}
_AS = {"type": ["array", "string"]}


def _obj(req: list[str], props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "required": req, "properties": props}


V1_EVENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "campaign.created": _obj(
        ["title", "system", "calendar", "start_game_time", "config_version"],
        {"title": _S, "system": _S, "calendar": {"type": ["string", "object"]}, "start_game_time": _S, "config_version": _I},
    ),
    "command.executed": _obj(
        ["command", "status", "summary"],
        {"command": _S, "args": _A, "status": _S, "summary": _S, "files": _O, "Clock": _S, "clock_updates": _A},
    ),
    "turn.proposed": _obj(
        ["turn", "action", "summary"],
        {"turn": _I, "action": _S, "summary": _S, "stakes": _S, "dc": _I, "stat": _S, "target": _O, "preconditions": _A},
    ),
    "turn.rejected": _obj(["turn", "reasons"], {"turn": _I, "reasons": _A}),
    "action.resolved": _obj(
        ["turn", "result", "outcome"],
        {"turn": _I, "result": _S, "outcome": _S, "costs": _O, "effects": _O},
    ),
    "turn.committed": _obj(
        ["turn", "summary"],
        {
            "turn": _I, "summary": _S, "scene_type": _S, "location": _S, "present": _AS,
            "vitals": _O, "vitals_line": _S, "costs": _O, "state_shift": _S, "alerts": _A,
            "restored_vitals": _B, "time_changed": _B, "location_changed": _B, "present_changed": _B,
        },
    ),
    "clock.created": _obj(
        ["name", "max", "trigger"],
        {"name": _S, "max": {"type": "integer", "minimum": 1}, "trigger": _S, "current": _I, "status": _S},
    ),
    "clock.advanced": _obj(
        ["name", "current", "max", "status"],
        {"name": _S, "steps": _I, "delta": _I, "current": _I, "max": _I, "status": _S, "trigger": _S},
    ),
    "clock.resolved": _obj(["name"], {"name": _S, "status": _S, "outcome": _S, "xp_granted": _I}),
    "quest.created": _obj(
        ["title", "type"],
        {
            "id": _S, "quest_id": _S, "title": _S, "type": _S, "objectives": _A,
            "contractor": _SN, "clock": _SN, "reward": {"type": ["object", "string", "null"]}, "phase": _SN,
        },
    ),
    "quest.objective_completed": _obj(
        [],
        {"id": _S, "quest_id": _S, "objective_idx": _I, "objective_index": _I, "xp_awarded": _I, "xp_granted": _I, "turn": _IN},
    ),
    "quest.completed": _obj(
        [],
        {"id": _S, "quest_id": _S, "xp_awarded": _I, "xp_granted": _I, "evidence": _S, "turn": _IN, "contractor_rep": _O},
    ),
    "quest.failed": _obj(
        ["reason"],
        {"id": _S, "quest_id": _S, "reason": _S, "turn": _IN, "contractor_rep": _O},
    ),
    "quest.status_changed": _obj(
        [],
        {"id": _S, "quest_id": _S, "status": _S, "action": _S, "objective": _S, "from": _S, "to": _S, "reason": _S, "turn": _IN},
    ),
    "arc.updated": _obj(
        [],
        {
            "title": _S, "question": _S, "stage": _S, "scene_name": _S, "date_time": _S,
            "location": _S, "present": _AS, "future_milestone": _S, "milestone": _S, "resolve_clocks": _B,
        },
    ),
    "scene.planned": _obj(["beat", "scene_type"], {"beat": _S, "scene_type": _S, "actors": _AS}),
    "scene.completed": _obj(["index"], {"index": _I}),
    "npc.updated": _obj(["npc_id", "changes"], {"npc_id": _S, "changes": _O}),
    "faction.reputation_changed": _obj(
        ["faction", "delta_rep", "new_score"],
        {
            "faction": _S, "delta_rep": _I, "new_score": _I, "delta_favors": _I, "delta_debts": _I,
            "favors": _I, "debts": _I, "turn": _IN, "quest_id": _S, "reason": _S,
        },
    ),
    "protagonist.progression_changed": _obj(
        ["xp_delta", "xp_total", "level"],
        {
            "xp_delta": _I, "xp_total": _I, "level": _I, "attribute_points": _I, "ability_points": _I,
            "base_step": _I, "turn": _IN, "skip_ledger": _B, "source": _S,
        },
    ),
    "protagonist.sheet_changed": _obj(
        ["kind", "target", "new_value"],
        {"kind": _S, "target": _S, "new_value": {}, "delta": _I, "points_remaining": _I, "training": _S, "source": _S},
    ),
    "prose.recorded": _obj(
        ["turn", "text_hash", "text_path"],
        {"turn": _I, "text_hash": _S, "text_path": _S, "source": _S, "bytes": _I, "scene_type": _S},
    ),
    "correction.issued": _obj(
        ["correction_id", "corrects", "reason", "changes"],
        {"correction_id": _S, "corrects": _A, "reason": _S, "changes": _A, "state": _S, "inconsistency_detected": _B},
    ),
    "correction.recomputed": _obj(
        ["correction_id", "affected", "outcome"],
        {"correction_id": _S, "affected": _A, "outcome": _S},
    ),
    "projection.rebuilt": _obj(
        ["from_seq", "to_seq", "projection_version", "hash"],
        {"from_seq": _I, "to_seq": _I, "projection_version": _I, "hash": _S},
    ),
    "knowledge.claim_registered": _obj(
        ["claim_id", "proposition", "claim_type"],
        {
            "claim_id": _S, "proposition": _O, "claim_type": _S,
            "valid_from": _IN, "valid_to": _IN, "source_event_id": _SN, "fact_ref": _SN,
        },
    ),
    "knowledge.acquired": _obj(
        ["record_id", "holder", "claim_id", "awareness", "stance", "confidence", "provenance"],
        {
            "record_id": _S, "holder": _O, "claim_id": _S, "awareness": _S,
            "stance": _S, "confidence": _I, "status": _SN, "provenance": _A,
            "acquired_at": _SN, "acquired_at_sort": _IN, "visibility": _SN,
        },
    ),
    "knowledge.inferred": _obj(
        ["record_id", "holder", "claim_id", "stance", "confidence", "derived_from"],
        {
            "record_id": _S, "holder": _O, "claim_id": _S, "stance": _S,
            "confidence": _I, "derived_from": _A, "method": _SN, "status": _SN,
            "provenance": _A, "acquired_at": _SN, "acquired_at_sort": _IN, "visibility": _SN,
        },
    ),
    "knowledge.revised": _obj(
        ["record_id", "holder", "claim_id", "stance", "confidence", "status", "reason"],
        {
            "record_id": _S, "holder": _O, "claim_id": _S, "stance": _S,
            "confidence": _I, "status": _S, "reason": _S, "supersedes": _A,
            "provenance": _A, "acquired_at": _SN, "acquired_at_sort": _IN, "visibility": _SN,
        },
    ),
    "knowledge.shared": _obj(
        ["record_id", "from_holder", "to_holder", "claim_id", "scope", "confidence"],
        {
            "record_id": _S, "from_holder": _O, "to_holder": _O, "claim_id": _S,
            "scope": _S, "confidence": _I, "stance": _SN, "visibility": _SN,
        },
    ),
    "npc.promoted": _obj(
        ["npc_id", "from_tier", "to_tier"],
        {"npc_id": _S, "from_tier": _S, "to_tier": _S, "goals": _A, "capabilities": _A, "resources": _O, "location": _S, "condition": _S},
    ),
    "npc.goal_updated": _obj(
        ["npc_id", "goal_id", "description", "horizon", "priority", "status"],
        {"npc_id": _S, "goal_id": _S, "description": _S, "horizon": _S, "priority": _I, "status": _S, "reason": _SN},
    ),
    "npc.plan_updated": _obj(
        ["npc_id", "plan_id", "goal_id", "title", "steps", "status"],
        {"npc_id": _S, "plan_id": _S, "goal_id": _S, "title": _S, "steps": _A, "status": _S, "alternatives": _A, "completion_conditions": _A},
    ),
    "npc.relationship_updated": _obj(
        ["npc_id", "target_id"],
        {"npc_id": _S, "target_id": _S, "trust": _I, "rivalry": _I, "dependency": _I, "debt": _I, "loyalty": _I, "note": _S},
    ),
    "faction.updated": _obj(
        ["tag", "name"],
        {"tag": _S, "name": _S, "leadership": _O, "collective_goals": _A, "resources": _O, "influence": _O, "limitations": _A, "internal_conflicts": _A},
    ),
    "faction.subgroup_updated": _obj(
        ["faction_tag", "subgroup_id", "name", "leader_id", "stance_towards_leadership"],
        {"faction_tag": _S, "subgroup_id": _S, "name": _S, "leader_id": _S, "stance_towards_leadership": _S, "agenda": _S, "members": _A, "resources": _O},
    ),
    "faction.plan_updated": _obj(
        ["faction_tag", "plan_id", "title", "steps", "status"],
        {"faction_tag": _S, "plan_id": _S, "title": _S, "steps": _A, "status": _S, "goal_id": _SN, "actor_subgroup_id": _SN},
    ),
    "proposal.rejected": _obj(
        ["proposal_kind", "actor_id", "reasons"],
        {"proposal_kind": _S, "actor_id": _S, "reasons": _A, "payload_summary": _O},
    ),
}

__all__ = ["V1_EVENT_SCHEMAS"]
