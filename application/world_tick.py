"""application/world_tick.py: caso de uso do ciclo de simulação de mundo (Fase 05).

Avança o tempo, seleciona o trabalho devido sob orçamento, resolve cada item de
forma determinística e grava um lote único (evento + projeções). Não narra, não
chama LLM e não altera XP, reputação ou missão.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from application.context.state import ContextStateViewImpl
from application.transaction import (
    _serialized_campaign_mutation,
    ensure_campaign_event_log,
    record_command_mutation,
)
from contracts.simulation import TRIGGERS, WorldView
from council import find_campaign
from plugins.budget_policy import PriorityBudgetPolicy
from plugins.simulation_policy import TimedSimulationPolicy
from resources.ledger import parse_diario_md
from resources.world.config import budget_from_config, normalize_simulation, retry_settings
from resources.world.drafts import (
    work_completed_draft,
    work_deferred_draft,
    work_failed_draft,
    world_ticked_draft,
)
from resources.world.ids import make_tick_id
from resources.world.queue import collect
from resources.world.resolve import resolve_work
from resources.world.state import apply_draft_effects, clone_state, silent_entities
from resources.world.workqueue import deferred_items, retry_items, scheduled_items
from temporal.calendar import game_time_to_minutes, minutes_to_game_time, validate_game_time


def _build_view(
    campaign_id: str,
    camp_dir: Path,
    store: Any,
    from_sort: int,
    to_sort: int,
    elapsed: int,
    diario: Mapping[str, Any],
    config: Mapping[str, Any],
) -> tuple[WorldView, dict[str, Any]]:
    state = ContextStateViewImpl.load(campaign_id, camp_dir, store=store, diario_data=diario)
    index = collect(tuple(store.read(campaign_id)))
    failures = tuple(item.to_dict() for item in retry_items(index, to_sort, config))
    view = WorldView(
        campaign_id=campaign_id,
        from_sort=from_sort,
        to_sort=to_sort,
        elapsed_minutes=elapsed,
        clocks=tuple(diario.get("clocks") or ()),
        npcs=state.npcs(),
        factions=state.factions(),
        planned_scenes=tuple((diario.get("plot_plan") or {}).get("planned_scenes") or ()),
        scheduled=scheduled_items(index, to_sort),
        deferred=deferred_items(index),
        failures=failures,
        completed_ids=frozenset(index.get("completed", set())),
        config=dict(config),
    )
    return view, index


def _queue_hash(camp_dir: Path) -> str:
    queue_file = camp_dir / "queue.json"
    if not queue_file.exists():
        return ""
    try:
        return str(json.loads(queue_file.read_text(encoding="utf-8")).get("hash") or "")
    except (OSError, ValueError):
        return ""


@_serialized_campaign_mutation
def cmd_world_tick(
    campaign_id: str,
    minutes: int | None = None,
    to: str = "",
    trigger: str = "manual",
    seed: int = 0,
    budget: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Executa um ciclo de simulação: tempo, trabalho devido, orçamento e retry."""
    if trigger not in TRIGGERS:
        return {"error": f"trigger inválido: '{trigger}' (use {', '.join(TRIGGERS)})"}
    if isinstance(seed, bool) or not isinstance(seed, int):
        return {"error": "seed deve ser inteiro."}
    if budget is not None and (
        isinstance(budget, bool) or not isinstance(budget, int) or budget < 1
    ):
        return {"error": "--budget deve ser inteiro >= 1."}
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as exc:
        return {"error": str(exc)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}

    camp_dir = Path(info["dir"])
    config = normalize_simulation(info.get("simulation") or {})
    calendar = info.get("calendar") or {}
    calendar_arg = calendar if isinstance(calendar, dict) and calendar else None
    diario = parse_diario_md(info["diario"])
    from_time = str(diario.get("date_time") or "Dia 1, 08:00")
    try:
        validate_game_time(from_time, calendar_arg)
        from_sort = game_time_to_minutes(from_time, calendar=calendar_arg)
    except ValueError as exc:
        return {"error": f"Data canônica inválida ('{from_time}'): {exc}"}

    if to:
        try:
            validate_game_time(to, calendar_arg)
        except ValueError as exc:
            return {"error": f"--to inválido ('{to}'): {exc}"}
        to_sort = game_time_to_minutes(to, calendar=calendar_arg)
        if to_sort < from_sort:
            return {"error": f"--to ('{to}') é anterior ao tempo atual ('{from_time}')."}
        elapsed = to_sort - from_sort
    elif minutes is not None:
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 0:
            return {"error": "--minutes deve ser inteiro >= 0."}
        elapsed = minutes
        to_sort = from_sort + minutes
    else:
        return {"error": "Informe --minutes N ou --to \"<data>\"; tick implícito não existe."}

    try:
        to_time = minutes_to_game_time(to_sort, from_time, calendar=calendar_arg)
    except ValueError as exc:
        return {"error": f"Calendário inválido para avançar '{from_time}': {exc}"}

    store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)
    view, index = _build_view(
        campaign_id, camp_dir, store, from_sort, to_sort, elapsed, diario, config
    )

    decision = PriorityBudgetPolicy().select(
        TimedSimulationPolicy().due(view),
        budget_from_config(config, override=budget),
        elapsed,
    )
    tick_id = make_tick_id(
        campaign_id, from_sort, to_sort, trigger, seed, int(index.get("queue_revision", 0))
    )

    drafts: list[Any] = []
    if elapsed > 0 or decision.selected or decision.deferred:
        drafts.append(
            world_ticked_draft(
                tick_id=tick_id,
                from_game_time=from_time,
                to_game_time=to_time,
                game_time_sort=to_sort,
                elapsed_minutes=elapsed,
                trigger=trigger,
                budget_limit=decision.limit,
                selected=len(decision.selected),
                deferred=len(decision.deferred),
                seed=seed,
            )
        )

    outcomes: list[dict[str, Any]] = []
    max_attempts, backoff = retry_settings(config)
    work_clocks, work_npcs, work_factions = clone_state(view.clocks, view.npcs, view.factions)
    for item in decision.selected:
        cause = str(item.payload.get("schedule_event_id") or tick_id)
        item_view = replace(
            view,
            clocks=tuple(work_clocks),
            npcs=work_npcs,
            factions=work_factions,
        )
        resolution = resolve_work(
            item,
            item_view,
            game_time=to_time,
            game_time_sort=to_sort,
            tick_id=tick_id,
            tick_event_id=tick_id,
        )
        if resolution.status == "completed":
            apply_draft_effects(
                work_clocks, work_npcs, work_factions, resolution.drafts
            )
            drafts.extend(resolution.drafts)
            drafts.append(
                work_completed_draft(
                    item,
                    summary=resolution.summary,
                    details=resolution.details,
                    game_time=to_time,
                    game_time_sort=to_sort,
                    tick_id=tick_id,
                    causation_id=cause,
                )
            )
            outcomes.append(
                {
                    "work_id": item.work_id,
                    "kind": item.kind,
                    "entity_id": item.entity_id,
                    "status": "completed",
                    "summary": resolution.summary,
                    "details": dict(resolution.details),
                }
            )
        else:
            attempts = item.attempts + 1
            retry_at = to_sort + backoff * attempts
            drafts.append(
                work_failed_draft(
                    item,
                    error=resolution.error,
                    attempts=attempts,
                    retry_at_sort=retry_at,
                    game_time=to_time,
                    game_time_sort=to_sort,
                    tick_id=tick_id,
                    causation_id=cause,
                )
            )
            outcomes.append(
                {
                    "work_id": item.work_id,
                    "kind": item.kind,
                    "entity_id": item.entity_id,
                    "status": "failed",
                    "error": resolution.error,
                    "attempts": attempts,
                    "retry_at_sort": retry_at,
                    "permanent": attempts >= max_attempts,
                }
            )

    for item in decision.deferred:
        drafts.append(
            work_deferred_draft(
                item,
                game_time=to_time,
                game_time_sort=to_sort,
                tick_id=tick_id,
            )
        )

    report: dict[str, Any] = {
        "campaign": campaign_id,
        "status": "idempotent" if not drafts else "ok",
        "tick_id": tick_id,
        "from": from_time,
        "to": to_time,
        "elapsed_minutes": int(elapsed),
        "trigger": trigger,
        "budget_limit": int(decision.limit),
        "budget_adaptive": bool(decision.adaptive),
        "selected": [item.to_dict() for item in decision.selected],
        "deferred": [item.to_dict() for item in decision.deferred],
        "silent_entities": list(silent_entities(view, decision.selected)),
        "outcomes": outcomes,
        "dry_run": bool(dry_run),
        "events_planned": len(drafts),
    }

    if dry_run or not drafts:
        report["last_seq"] = int(expected_last_seq)
        report["queue_hash"] = _queue_hash(camp_dir)
        return report

    result = record_command_mutation(
        camp_dir, campaign_id, store, expected_last_seq, prev_event_id, drafts
    )
    report["events_appended"] = len(result.events)
    report["first_seq"] = result.first_seq
    report["last_seq"] = result.last_seq
    report["queue_hash"] = _queue_hash(camp_dir)
    report["status"] = "ok"
    return report


__all__ = ["cmd_world_tick"]
