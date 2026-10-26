"""application/commit_events.py: Construção determinística dos eventos causais de um turno (commit)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from application.prose_store import ProseStore
from contracts.event import ActorRef, EventDraft
from resources.progression import parse_progression_from_ficha
from temporal.calendar import game_time_to_minutes


def build_commit_event_drafts(
    *,
    camp_dir: Path,
    next_turn: int,
    summary: str,
    scene_type: str,
    new_dt: str,
    new_loc: str,
    new_pres: str,
    calendar_cfg: Any,
    prev_event_id: str,
    deltas: dict[str, int],
    add_ability: str,
    add_milestone: str,
    add_item: str,
    npc_updates: str,
    clock_events: list[dict[str, Any]],
    quest_events: list[dict[str, Any]],
    xp_events: list[dict[str, Any]],
    faction_events: list[dict[str, Any]],
    scene_completed_idx: int | None,
    raw_prose: str,
    ficha_after_path: Path,
    diario_after_path: Path,
    npcs_after_path: Path,
    vitals_after: dict[str, int],
    vitals_line: str = "",
    state_shift: str = "",
    alerts: list[str] | None = None,
    restored_vitals: bool = False,
    time_changed: bool = True,
    location_changed: bool = False,
    present_changed: bool = False,
    base_step: int = 250,
) -> list[EventDraft]:
    actor_gm = ActorRef(kind="agent", id="narrative_engine")
    actor_rule = ActorRef(kind="system", id="ruleset")
    base_sort = game_time_to_minutes(
        new_dt,
        calendar=calendar_cfg if isinstance(calendar_cfg, dict) else None,
        fallback_turn=next_turn,
    )

    drafts: list[EventDraft] = []

    # 0. turn.proposed
    drafts.append(
        EventDraft(
            type="turn.proposed",
            schema_version=1,
            actor=actor_gm,
            game_time=new_dt,
            game_time_sort=base_sort,
            payload={
                "turn": next_turn,
                "action": summary.strip(),
                "summary": summary.strip(),
            },
            meta={"dependencies": [prev_event_id] if prev_event_id else []},
        )
    )

    # 1. action.resolved
    drafts.append(
        EventDraft(
            type="action.resolved",
            schema_version=1,
            actor=actor_rule,
            game_time=new_dt,
            game_time_sort=base_sort,
            payload={
                "turn": next_turn,
                "result": "SUCCESS",
                "outcome": summary.strip(),
                "costs": dict(deltas),
                "effects": {"scene_type": scene_type, "location": new_loc},
            },
            meta={"dependencies": ["batch:0"]},
        )
    )

    # 2. protagonist.sheet_changed
    for k, dv in deltas.items():
        drafts.append(
            EventDraft(
                type="protagonist.sheet_changed",
                schema_version=1,
                actor=actor_rule,
                game_time=new_dt,
                game_time_sort=base_sort,
                payload={
                    "kind": "vital",
                    "target": k,
                    "new_value": vitals_after.get(k, dv),
                    "delta": int(dv),
                    "source": "commit_cost",
                },
                meta={"dependencies": ["batch:1"]},
            )
        )
    for kind, val in (("ability", add_ability), ("milestone", add_milestone), ("item", add_item)):
        if val and val.strip():
            drafts.append(
                EventDraft(
                    type="protagonist.sheet_changed",
                    schema_version=1,
                    actor=actor_gm,
                    game_time=new_dt,
                    game_time_sort=base_sort,
                    payload={
                        "kind": kind,
                        "target": val.strip(),
                        "new_value": val.strip(),
                        "source": "commit",
                    },
                    meta={"dependencies": ["batch:1"]},
                )
            )

    # 3. npc.updated
    if npc_updates and npc_updates.strip():
        from council.narrator import parse_npc_update_fields, split_npc_updates

        for npc_name, raw_update in split_npc_updates(npc_updates):
            changes: dict[str, Any] = {
                "name": npc_name,
                "mode": "turn_update",
                "raw_update": raw_update,
            }
            changes.update(parse_npc_update_fields(raw_update))
            drafts.append(
                EventDraft(
                    type="npc.updated",
                    schema_version=1,
                    actor=actor_gm,
                    game_time=new_dt,
                    game_time_sort=base_sort,
                    payload={
                        "npc_id": npc_name.lower().replace(" ", "_"),
                        "changes": changes,
                    },
                    meta={"dependencies": ["batch:1"]},
                )
            )

    # 4. clock.advanced / clock.resolved
    for ce in clock_events:
        drafts.append(
            EventDraft(
                type=ce["type"],
                schema_version=1,
                actor=actor_gm,
                game_time=new_dt,
                game_time_sort=base_sort,
                payload=ce["payload"],
                meta={"dependencies": ["batch:1"]},
            )
        )

    # 5. quest.*
    for qe in quest_events:
        q_payload = dict(qe["payload"])
        q_payload.setdefault("turn", next_turn)
        drafts.append(
            EventDraft(
                type=qe["type"],
                schema_version=1,
                actor=actor_gm,
                game_time=new_dt,
                game_time_sort=base_sort,
                payload=q_payload,
                meta={"dependencies": ["batch:1"]},
            )
        )

    # 6. protagonist.progression_changed
    prog_now = parse_progression_from_ficha(ficha_after_path)
    for xe in xp_events:
        drafts.append(
            EventDraft(
                type="protagonist.progression_changed",
                schema_version=1,
                actor=actor_rule,
                game_time=new_dt,
                game_time_sort=base_sort,
                payload={
                    "xp_delta": int(xe["xp_delta"]),
                    "xp_total": int(xe.get("xp_total", prog_now["xp"])),
                    "level": int(xe.get("level", prog_now["level"])),
                    "attribute_points": int(prog_now["attribute_points"]),
                    "ability_points": int(prog_now["ability_points"]),
                    "base_step": int(base_step),
                    "turn": next_turn,
                    "source": str(xe.get("source", "commit")),
                },
                meta={"dependencies": ["batch:1"]},
            )
        )

    # 7. faction.reputation_changed
    for fe in faction_events:
        f_payload = dict(fe)
        f_payload.setdefault("turn", next_turn)
        drafts.append(
            EventDraft(
                type="faction.reputation_changed",
                schema_version=1,
                actor=actor_gm,
                game_time=new_dt,
                game_time_sort=base_sort,
                payload=f_payload,
                meta={"dependencies": ["batch:1"]},
            )
        )

    # 8. scene.completed
    if scene_completed_idx is not None:
        drafts.append(
            EventDraft(
                type="scene.completed",
                schema_version=1,
                actor=actor_gm,
                game_time=new_dt,
                game_time_sort=base_sort,
                payload={"index": int(scene_completed_idx)},
                meta={"dependencies": ["batch:1"]},
            )
        )

    # 9. prose.recorded
    if raw_prose:
        p_store = ProseStore(camp_dir)
        rel_p, p_hash, p_len = p_store.store_turn_prose(next_turn, raw_prose, scene_type=scene_type)
        drafts.append(
            EventDraft(
                type="prose.recorded",
                schema_version=1,
                actor=actor_gm,
                game_time=new_dt,
                game_time_sort=base_sort + 1,
                payload={
                    "turn": next_turn,
                    "text_hash": p_hash,
                    "text_path": rel_p,
                    "source": "writer_mode",
                    "bytes": p_len,
                    "scene_type": scene_type,
                },
                meta={"dependencies": ["batch:0", "batch:1"]},
            )
        )

    # 10. turn.committed (sem snapshots *_after em meta!)
    preceding_deps = [f"batch:{i}" for i in range(len(drafts))]

    drafts.append(
        EventDraft(
            type="turn.committed",
            schema_version=1,
            actor=actor_gm,
            game_time=new_dt,
            game_time_sort=base_sort + 2,
            payload={
                "turn": next_turn,
                "summary": summary.strip(),
                "scene_type": scene_type,
                "location": new_loc,
                "present": new_pres,
                "vitals": vitals_after,
                "vitals_line": vitals_line,
                "costs": dict(deltas),
                "state_shift": state_shift.strip(),
                "alerts": list(alerts or []),
                "restored_vitals": bool(restored_vitals),
                "time_changed": bool(time_changed),
                "location_changed": bool(location_changed),
                "present_changed": bool(present_changed),
            },
            meta={"dependencies": preceding_deps},
        )
    )

    return drafts


__all__ = ["build_commit_event_drafts"]
