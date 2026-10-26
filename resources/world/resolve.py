"""resources/world/resolve.py: resolução determinística de um item de trabalho.

Recebe um :class:`WorkItem` e a visão imutável do mundo e devolve drafts de evento
ou uma falha tipada. Não lê arquivos, não projeta e não decide desfecho de ação:
avança estados de tempo (relógios, passos de plano) e agenda cenas devidas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from contracts.event import ActorRef, EventDraft
from contracts.simulation import WorkItem, WorldView
from resources.world.cadence import active_plan_of, clock_advance, plan_progress

SIM_ACTOR = ActorRef(kind="system", id="world_simulation")


@dataclass(frozen=True)
class Resolution:
    """Resultado de resolução: drafts a gravar ou falha com motivo estável."""

    status: str
    summary: str = ""
    drafts: tuple[EventDraft, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""

    def __post_init__(self) -> None:
        if self.status not in ("completed", "failed"):
            raise ValueError(f"status de resolução inválido: {self.status!r}")
        object.__setattr__(self, "details", dict(self.details))


def _draft(
    item: WorkItem,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    game_time: str,
    game_time_sort: int,
    tick_id: str,
    tick_event_id: str,
) -> EventDraft:
    scheduled_by = str(item.payload.get("schedule_event_id", "") or "")
    return EventDraft(
        type=event_type,
        schema_version=1,
        actor=SIM_ACTOR,
        game_time=game_time,
        game_time_sort=game_time_sort,
        causation_id=scheduled_by or tick_event_id,
        correlation_id=tick_id,
        payload=dict(payload),
    )


def _find_clock(view: WorldView, name: str) -> Mapping[str, Any] | None:
    wanted = name.strip().lower()
    for clock in view.clocks:
        if str(clock.get("name", "")).strip().lower() == wanted:
            return clock
    return None


def _find_entity(view: WorldView, entity_kind: str, entity_id: str) -> Mapping[str, Any] | None:
    source = view.npcs if entity_kind == "npc" else view.factions
    entity = source.get(entity_id)
    if isinstance(entity, Mapping):
        return entity
    wanted = entity_id.strip().lower()
    for key, candidate in source.items():
        if str(key).strip().lower() == wanted:
            return candidate if isinstance(candidate, Mapping) else None
        if isinstance(candidate, Mapping) and str(candidate.get("name", "")).strip().lower() == wanted:
            return candidate
    return None


def _plan_payload(
    entity: Mapping[str, Any],
    plan: Mapping[str, Any],
    progress: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "steps": list(progress["steps"]),
        "current_step_index": int(progress["current_step_index"]),
        "status": str(plan.get("status", "active")),
    }


def _resolve_clock(
    item: WorkItem,
    view: WorldView,
    *,
    game_time: str,
    game_time_sort: int,
    tick_id: str,
    tick_event_id: str,
) -> Resolution:
    clock = _find_clock(view, item.entity_id)
    if clock is None:
        return Resolution(status="failed", error=f"clock_not_found:{item.entity_id}")
    status = str(clock.get("status", "ACTIVE")).upper()
    if status != "ACTIVE":
        return Resolution(status="failed", error=f"clock_not_active:{item.entity_id}:{status}")

    elapsed = int(item.payload.get("elapsed_minutes", view.elapsed_minutes))
    step_minutes = int(item.payload.get("step_minutes", 1440))
    advance = clock_advance(
        current=int(clock.get("current", 0)),
        maximum=int(clock.get("max", 4)),
        elapsed_minutes=elapsed,
        step_minutes=step_minutes,
    )
    if advance["delta"] <= 0:
        return Resolution(
            status="completed",
            summary=f"Relógio '{item.entity_id}' sem passo proporcional no intervalo.",
            details={"kind": "clock_advance", "delta": 0, "current": advance["current"], "noop": True},
        )

    draft = _draft(
        item,
        "clock.advanced",
        {
            "name": str(clock.get("name", item.entity_id)),
            "delta": int(advance["delta"]),
            "current": int(advance["current"]),
            "max": int(advance["max"]),
            "status": str(advance["status"]),
            "trigger": str(clock.get("trigger", "")),
        },
        game_time=game_time,
        game_time_sort=game_time_sort,
        tick_id=tick_id,
        tick_event_id=tick_event_id,
    )
    summary = (
        f"Relógio '{clock.get('name', item.entity_id)}' avançou {advance['delta']} passo(s) "
        f"para {advance['current']}/{advance['max']} [{advance['status']}]."
    )
    return Resolution(
        status="completed",
        summary=summary,
        drafts=(draft,),
        details={
            "kind": "clock_advance",
            "clock": str(clock.get("name", item.entity_id)),
            "delta": int(advance["delta"]),
            "current": int(advance["current"]),
            "max": int(advance["max"]),
            "status": str(advance["status"]),
            "breached": bool(advance["breached"]),
        },
    )


def _resolve_plan(
    item: WorkItem,
    view: WorldView,
    *,
    game_time: str,
    game_time_sort: int,
    tick_id: str,
    tick_event_id: str,
) -> Resolution:
    entity_kind = "npc" if item.kind == "npc_plan_step" else "faction"
    entity = _find_entity(view, entity_kind, item.entity_id)
    if entity is None:
        return Resolution(status="failed", error=f"{entity_kind}_not_found:{item.entity_id}")
    plan = active_plan_of(entity)
    if plan is None:
        return Resolution(status="failed", error=f"plan_not_active:{item.entity_id}")

    raw_steps = plan.get("steps") or ()
    elapsed = int(item.payload.get("elapsed_minutes", view.elapsed_minutes))
    step_minutes = int(item.payload.get("step_minutes", 2880))
    progress = plan_progress(
        steps=[dict(step) for step in raw_steps if isinstance(step, Mapping)],
        current_step_index=int(plan.get("current_step_index", 0)),
        elapsed_minutes=elapsed,
        step_minutes=step_minutes,
    )
    if progress["progressed"] <= 0:
        return Resolution(
            status="completed",
            summary=f"Plano de '{item.entity_id}' sem passo proporcional no intervalo.",
            details={"kind": item.kind, "progressed": 0, "noop": True},
        )

    plan_id = str(plan.get("plan_id", item.payload.get("plan_id", "")))
    goal_id = str(plan.get("goal_id", item.payload.get("goal_id", "")))
    title = str(item.payload.get("title") or plan.get("title") or plan_id or "Plano")
    payload = {
        "steps": list(progress["steps"]),
        "current_step_index": int(progress["current_step_index"]),
        "status": str(plan.get("status", "active")),
    }
    if entity_kind == "npc":
        payload.update({"npc_id": str(entity.get("id", item.entity_id)), "plan_id": plan_id,
                        "goal_id": goal_id, "title": title})
        event_type = "npc.plan_updated"
    else:
        tag = str(entity.get("tag", item.entity_id))
        payload.update({"faction_tag": tag, "plan_id": plan_id, "goal_id": goal_id, "title": title})
        event_type = "faction.plan_updated"

    draft = _draft(
        item,
        event_type,
        payload,
        game_time=game_time,
        game_time_sort=game_time_sort,
        tick_id=tick_id,
        tick_event_id=tick_event_id,
    )
    details = {
        "kind": item.kind,
        "entity_id": item.entity_id,
        "plan_id": plan_id,
        "progressed": int(progress["progressed"]),
        "current_step_index": int(progress["current_step_index"]),
        "plan_ready_for_resolution": bool(progress["ready"]),
    }
    return Resolution(
        status="completed",
        summary=(
            f"Plano de '{item.entity_id}' avançou {progress['progressed']} passo(s)"
            + (" e aguarda resolução de agência." if progress["ready"] else ".")
        ),
        drafts=(draft,),
        details=details,
    )


def _resolve_scene(
    item: WorkItem,
    *,
    game_time: str,
    game_time_sort: int,
    tick_id: str,
    tick_event_id: str,
) -> Resolution:
    beat = str(item.payload.get("beat", "")).strip()
    if not beat:
        return Resolution(status="failed", error="scene_payload_invalid:missing_beat")
    return Resolution(
        status="completed",
        summary=f"Cena agendada devida: {beat}",
        details={
            "kind": "scene_due",
            "scene_type": str(item.payload.get("scene_type", "interlude")),
            "beat": beat,
            "actors": str(item.payload.get("actors", "")),
            "due_game_time": str(item.payload.get("due_game_time", game_time)),
        },
    )


def resolve_work(
    item: WorkItem,
    view: WorldView,
    *,
    game_time: str,
    game_time_sort: int,
    tick_id: str,
    tick_event_id: str,
) -> Resolution:
    """Resolve um item de trabalho em drafts determinísticos ou falha tipada."""
    if not isinstance(item, WorkItem):
        return Resolution(status="failed", error="work_item_invalid")
    if item.work_id in view.completed_ids:
        return Resolution(
            status="completed",
            summary=f"Trabalho {item.work_id} já concluído; nada a fazer.",
            details={"kind": item.kind, "already_completed": True},
        )
    if item.kind == "clock_advance":
        return _resolve_clock(
            item, view, game_time=game_time, game_time_sort=game_time_sort,
            tick_id=tick_id, tick_event_id=tick_event_id,
        )
    if item.kind in ("npc_plan_step", "faction_plan_step"):
        return _resolve_plan(
            item, view, game_time=game_time, game_time_sort=game_time_sort,
            tick_id=tick_id, tick_event_id=tick_event_id,
        )
    if item.kind == "scene_due":
        return _resolve_scene(
            item, game_time=game_time, game_time_sort=game_time_sort,
            tick_id=tick_id, tick_event_id=tick_event_id,
        )
    return Resolution(status="failed", error=f"kind_not_resolvable:{item.kind}")


__all__ = ["Resolution", "SIM_ACTOR", "resolve_work"]
