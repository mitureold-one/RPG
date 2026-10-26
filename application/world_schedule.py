"""application/world_schedule.py: agendamento futuro e leitura da fila (Fase 05).

`cmd_schedule` valida a proposta da IA e grava `world.scheduled` (ou
`proposal.rejected`); `cmd_queue` lê a fila reconstruída sem mutar o log.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from application.context.state import ContextStateViewImpl
from application.transaction import (
    _serialized_campaign_mutation,
    ensure_campaign_event_log,
    record_command_mutation,
)
from contracts.ports import create_event_store
from council import find_campaign
from kernel.errors import DuplicateBatchError
from resources.ledger import parse_diario_md
from resources.world.config import normalize_simulation
from resources.world.drafts import proposal_rejected_draft, scheduled_draft
from resources.world.ids import make_work_id
from resources.world.queue import collect
from resources.world.workqueue import queue_document
from temporal.calendar import (
    game_time_to_minutes,
    minutes_to_game_time,
    validate_game_time,
)

_KIND_ENTITY = {
    "clock_advance": "clock",
    "npc_plan_step": "npc",
    "faction_plan_step": "faction",
    "scene_due": "scene",
}
_SCHEDULABLE = tuple(_KIND_ENTITY)


def _parse_payload(raw: Sequence[str] | str | None) -> dict[str, Any]:
    if not raw:
        return {}
    chunks = [raw] if isinstance(raw, str) else list(raw)
    payload: dict[str, Any] = {}
    for chunk in chunks:
        for part in str(chunk).split(";"):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"payload inválido: '{part}' (use chave=valor)")
            key, value = part.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(f"payload inválido: '{part}'")
            trimmed = value.strip()
            if trimmed.lstrip("-").isdigit():
                payload[key] = int(trimmed)
            else:
                payload[key] = trimmed
    return payload


def _validate_entity(
    state: ContextStateViewImpl,
    diario: Mapping[str, Any],
    entity_kind: str,
    entity: str,
) -> str:
    target = entity.strip()
    if entity_kind == "clock":
        names = {str(clock.get("name", "")).strip().lower() for clock in (diario.get("clocks") or [])}
        return "" if target.lower() in names else f"relógio inexistente: '{target}'"
    source = state.npcs() if entity_kind == "npc" else state.factions()
    label = "NPC" if entity_kind == "npc" else "facção"
    if target in source:
        return ""
    for candidate in source.values():
        if isinstance(candidate, Mapping) and str(candidate.get("name", "")).strip().lower() == target.lower():
            return ""
    return f"{label} inexistente: '{target}'"


@_serialized_campaign_mutation
def cmd_schedule(
    campaign_id: str,
    at: str = "",
    kind: str = "",
    entity: str = "",
    payload: Sequence[str] | str | None = None,
    priority: int = 50,
) -> dict[str, Any]:
    """Agenda trabalho futuro validado (proposta da IA), ou registra a rejeição."""
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as exc:
        return {"error": str(exc)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}

    camp_dir = Path(info["dir"])
    diario = parse_diario_md(info["diario"])
    calendar = info.get("calendar") or {}
    calendar_arg = calendar if isinstance(calendar, dict) and calendar else None
    now_time = str(diario.get("date_time") or "Dia 1, 08:00")
    from_sort = game_time_to_minutes(now_time, calendar=calendar_arg)

    reasons: list[str] = []
    try:
        validate_game_time(now_time, calendar_arg)
    except ValueError as exc:
        return {"error": f"Data canônica inválida ('{now_time}'): {exc}"}
    normalized_payload: dict[str, Any] = {}
    try:
        normalized_payload = _parse_payload(payload)
    except ValueError as exc:
        reasons.append(str(exc))

    if kind not in _SCHEDULABLE:
        reasons.append(f"kind inválido: '{kind}' (use {', '.join(_SCHEDULABLE)})")
    if not str(entity).strip():
        reasons.append("entity é obrigatório")
    if isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 100:
        reasons.append("priority deve ser inteiro entre 1 e 100")

    due_sort = from_sort
    if at:
        try:
            validate_game_time(at, calendar_arg)
            due_sort = game_time_to_minutes(at, calendar=calendar_arg)
        except ValueError as exc:
            reasons.append(f"data inválida: {exc}")
        else:
            if due_sort < from_sort:
                reasons.append(f"--at ('{at}') é anterior ao tempo atual ('{now_time}')")
    else:
        reasons.append("--at é obrigatório")

    entity_kind = _KIND_ENTITY.get(kind, "world")
    store = create_event_store(camp_dir)
    if store.last_seq(campaign_id) == 0:
        store, _expected, _prev = ensure_campaign_event_log(camp_dir, campaign_id)

    if not reasons and entity_kind != "scene":
        state = ContextStateViewImpl.load(campaign_id, camp_dir, store=store, diario_data=diario)
        problem = _validate_entity(state, diario, entity_kind, str(entity))
        if problem:
            reasons.append(problem)

    if reasons:
        draft = proposal_rejected_draft(
            reasons=reasons,
            summary={"kind": kind, "entity": str(entity), "at": at, "priority": priority},
            game_time=now_time,
            game_time_sort=from_sort,
        )
        record_command_mutation(
            camp_dir, campaign_id, store, store.last_seq(campaign_id), "", [draft]
        )
        return {"status": "rejected", "reasons": reasons}

    target = str(entity).strip()
    work_id = make_work_id(kind, entity_kind, target, due_sort, normalized_payload)
    due_time = minutes_to_game_time(due_sort, now_time, calendar=calendar_arg)

    existing = collect(tuple(store.read(campaign_id)))
    if work_id in existing.get("completed", set()):
        return {
            "status": "already_completed",
            "work_id": work_id,
            "kind": kind,
            "entity_id": target,
            "due_game_time": due_time,
            "due_at_sort": int(due_sort),
        }
    if (
        work_id in (existing.get("scheduled") or {})
        or work_id in (existing.get("deferred") or {})
        or work_id in (existing.get("failed") or {})
    ):
        return {
            "status": "already_scheduled",
            "work_id": work_id,
            "kind": kind,
            "entity_kind": entity_kind,
            "entity_id": target,
            "due_game_time": due_time,
            "due_at_sort": int(due_sort),
            "priority": int(priority),
        }

    draft = scheduled_draft(
        work_id=work_id,
        kind=kind,
        entity_kind=entity_kind,
        entity_id=target,
        due_game_time=due_time,
        due_at_sort=due_sort,
        priority=priority,
        payload=normalized_payload,
        game_time=now_time,
        game_time_sort=from_sort,
    )
    try:
        result = record_command_mutation(
            camp_dir, campaign_id, store, store.last_seq(campaign_id), "", [draft]
        )
    except DuplicateBatchError:
        return {
            "status": "already_scheduled",
            "work_id": work_id,
            "kind": kind,
            "entity_kind": entity_kind,
            "entity_id": target,
            "due_game_time": due_time,
            "due_at_sort": int(due_sort),
            "priority": int(priority),
        }
    return {
        "status": "scheduled",
        "work_id": work_id,
        "kind": kind,
        "entity_kind": entity_kind,
        "entity_id": target,
        "due_game_time": due_time,
        "due_at_sort": int(due_sort),
        "priority": int(priority),
        "seq": result.last_seq,
    }


def cmd_queue(campaign_id: str) -> dict[str, Any]:
    """Lê a fila de simulação reconstruída dos eventos ``world.*`` (sem mutação)."""
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as exc:
        return {"error": str(exc)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}

    camp_dir = Path(info["dir"])
    config = normalize_simulation(info.get("simulation") or {})
    store = create_event_store(camp_dir)
    events = tuple(store.read(campaign_id))
    domain_events = [event for event in events if not event.type.startswith("projection.")]
    last_seq = domain_events[-1].seq if domain_events else 0
    index = collect(events)
    document = queue_document(index, last_seq, config)
    queue_file = camp_dir / "queue.json"
    if queue_file.exists():
        import json

        try:
            document["queue_hash"] = json.loads(queue_file.read_text(encoding="utf-8")).get("hash", "")
        except (OSError, ValueError):
            document["queue_hash"] = ""
    else:
        document["queue_hash"] = ""
    return document


__all__ = ["cmd_queue", "cmd_schedule"]
