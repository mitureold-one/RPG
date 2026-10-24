"""Casos de uso do Showrunner: relógios, fila de cenas, transição de arco, rebuild e correções."""

from pathlib import Path

from council import (
    CAMPAIGN_DIRS,
    DEFAULT_RULESET,
    load_ruleset,
    get_campaign_overrides,
    find_campaign,
    parse_diario_md,
    upsert_clock_in_diario,
    parse_clocks_from_diario,
    upsert_planned_scene_in_diario,
    update_arc_in_diario,
    parse_quests_from_diario,
    append_xp_ledger_entry,
    update_progression_in_ficha,
)
from rulesets.progression import evaluate_xp_gain, get_base_step_from_overrides
from application.transaction import (
    _serialized_campaign_mutation,
    ensure_campaign_event_log,
    record_command_mutation,
)
from contracts.event import ActorRef, EventDraft
from contracts.ports import create_event_store
from application.rebuild import rebuild_projections
from application.correction import CorrectionService
from temporal.calendar import game_time_to_minutes


def _current_time_info(diario_path: Path, calendar_cfg=None) -> tuple[str, int, int]:
    diario_ctx = parse_diario_md(diario_path) if diario_path.exists() else {}
    gt = str(diario_ctx.get("date_time") or "Dia 1, 08:00")
    turn_num = int(diario_ctx.get("last_turn_num") or 0)
    gts = game_time_to_minutes(
        gt,
        calendar=calendar_cfg if isinstance(calendar_cfg, dict) else None,
        fallback_turn=turn_num,
    )
    return gt, gts, turn_num


@_serialized_campaign_mutation
def cmd_clock(
    campaign_id: str,
    list_clocks: bool = False,
    add_name: str = "",
    max_steps: int = 4,
    trigger: str = "",
    advance_name: str = "",
    advance_steps: int = 1,
    resolve_name: str = "",
    add_max: int = None,
    add_trigger: str = "",
) -> dict:
    """Gerencia relógios narrativos de facções, prazos e ameaças determinísticas em diario.md."""
    if add_max is not None:
        max_steps = add_max
    if add_trigger:
        trigger = add_trigger
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}

    camp_dir = Path(info["dir"])
    diario_path = info["diario"]
    res = {}
    mutating = bool(add_name or advance_name or resolve_name)
    store = None
    expected_last_seq = 0
    prev_event_id = ""
    if mutating:
        store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)

    drafts: list[EventDraft] = []
    actor = ActorRef(kind="agent", id="showrunner")
    gt, gts, cur_turn = _current_time_info(diario_path, info.get("calendar"))

    if add_name:
        res = upsert_clock_in_diario(diario_path, add_name, current=0, max_steps=max_steps, trigger=trigger)
        drafts.append(
            EventDraft(
                type="clock.created",
                schema_version=1,
                actor=actor,
                game_time=gt,
                game_time_sort=gts,
                payload={"name": add_name.strip(), "max": int(max_steps), "trigger": trigger.strip()},
            )
        )
    elif advance_name:
        res = upsert_clock_in_diario(
            diario_path, advance_name, advance=advance_steps, create_if_missing=False
        )
        if not res.get("error"):
            st_now = str(res.get("status", "ACTIVE"))
            drafts.append(
                EventDraft(
                    type="clock.advanced",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={
                        "name": advance_name.strip(),
                        "delta": int(advance_steps),
                        "current": int(res.get("current", 0)),
                        "max": int(res.get("max", 4)),
                        "status": st_now,
                    },
                )
            )
            if st_now in ("RESOLVED", "BREACHED"):
                drafts.append(
                    EventDraft(
                        type="clock.resolved",
                        schema_version=1,
                        actor=actor,
                        game_time=gt,
                        game_time_sort=gts,
                        payload={"name": advance_name.strip(), "outcome": st_now},
                    )
                )
    elif resolve_name:
        prior_clocks = parse_clocks_from_diario(diario_path)
        matched_prior = next((c for c in prior_clocks if c["name"].lower() == resolve_name.strip().lower()), None)
        was_active = matched_prior is not None and matched_prior.get("status") == "ACTIVE"

        res = upsert_clock_in_diario(
            diario_path, resolve_name, status="RESOLVED", create_if_missing=False
        )
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="clock.resolved",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"name": resolve_name.strip(), "outcome": "RESOLVED"},
                )
            )
        all_active_quests = parse_quests_from_diario(diario_path)
        linked_clock_names = {q["clock"].strip().lower() for q in all_active_quests if q.get("clock")}
        if was_active and resolve_name.strip().lower() not in linked_clock_names:
            camp_overrides = get_campaign_overrides(campaign_id)
            base_step = get_base_step_from_overrides(camp_overrides)
            clock_xp = evaluate_xp_gain("clock_resolved", overrides=camp_overrides)
            prog_res = update_progression_in_ficha(info["ficha"], xp_add=clock_xp, base_step=base_step)
            append_xp_ledger_entry(diario_path, clock_xp, reason=f"Relógio '{resolve_name}' resolvido", turn=cur_turn)
            res["xp_granted"] = clock_xp
            if prog_res.get("level_up"):
                res["level_up"] = prog_res["new_level"]
            drafts.append(
                EventDraft(
                    type="protagonist.progression_changed",
                    schema_version=1,
                    actor=ActorRef(kind="system", id="ruleset"),
                    game_time=gt,
                    game_time_sort=gts,
                    payload={
                        "xp_delta": int(clock_xp),
                        "xp_total": int(prog_res["new_xp"]),
                        "level": int(prog_res["new_level"]),
                        "attribute_points": int(prog_res.get("attribute_points", 0)),
                        "ability_points": int(prog_res.get("ability_points", 0)),
                        "source": f"Relógio '{resolve_name}' resolvido",
                    },
                )
            )
        elif not was_active:
            res["xp_warning"] = f"Relógio '{resolve_name}' já se encontrava em status '{matched_prior.get('status') if matched_prior else 'INEXISTENTE'}'. Recompensa de XP não duplicada."

    if mutating and drafts and store is not None:
        record_command_mutation(camp_dir, campaign_id, store, expected_last_seq, prev_event_id, drafts)

    clocks = parse_clocks_from_diario(diario_path)
    return {
        "campaign": campaign_id,
        "action_result": res if res else None,
        "clocks": clocks,
        "active_count": len([c for c in clocks if c["status"] == "ACTIVE"]),
        "breached_count": len([c for c in clocks if c["status"] == "BREACHED"]),
    }


@_serialized_campaign_mutation
def cmd_plan(
    campaign_id: str,
    list_plan: bool = False,
    add_beat: str = "",
    scene_type: str = "interlude",
    actors: str = "",
    complete_idx: int = None,
    add_milestone: str = "",
) -> dict:
    """Gerencia a Fila de Cenas Agendadas, Marcos Futuros e Ritmo em diario.md (Modo Diretor/Showrunner)."""
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada em {CAMPAIGN_DIRS}."}

    system_name = info.get("system", DEFAULT_RULESET)
    load_ruleset(system_name)
    camp_dir = Path(info["dir"])
    diario_path = info["diario"]

    action_res = None
    if add_beat or complete_idx is not None or add_milestone:
        store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)
        gt, gts, _ = _current_time_info(diario_path, info.get("calendar"))
        actor = ActorRef(kind="agent", id="showrunner")
        action_res = upsert_planned_scene_in_diario(
            diario_path,
            scene_type=scene_type,
            beat=add_beat,
            actors=actors,
            mark_done_idx=complete_idx,
            future_milestone=add_milestone,
        )
        drafts: list[EventDraft] = []
        if add_beat:
            drafts.append(
                EventDraft(
                    type="scene.planned",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"scene_type": scene_type, "beat": add_beat.strip(), "actors": actors.strip()},
                )
            )
        if complete_idx is not None:
            drafts.append(
                EventDraft(
                    type="scene.completed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"index": int(complete_idx)},
                )
            )
        if add_milestone:
            drafts.append(
                EventDraft(
                    type="arc.updated",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"future_milestone": add_milestone.strip()},
                )
            )
        if drafts:
            record_command_mutation(camp_dir, campaign_id, store, expected_last_seq, prev_event_id, drafts)

    diario = parse_diario_md(diario_path)
    plan_data = diario.get("plot_plan", {})
    consec_std = diario.get("consecutive_standard_turns", 0)

    pacing_advice = (
        f"ALERTA DE FADIGA DE RITMO ({consec_std} turnos padrão seguidos): O Mestre deve exercer iniciativa ativa e quebrar a linearidade intercalando um interlúdio, dossiê ou salto temporal na próxima cena."
        if consec_std >= 4
        else "Ritmo equilibrado."
    )

    return {
        "campaign": campaign_id,
        "action_result": action_res if action_res else "status_queried",
        "arc": diario.get("arc", {}),
        "consecutive_standard_turns": consec_std,
        "pacing_advice": pacing_advice,
        "active_clocks": [c for c in diario.get("clocks", []) if c["status"] == "ACTIVE"],
        "next_scene": plan_data.get("next_scene"),
        "planned_scenes": plan_data.get("planned_scenes", []),
        "future_milestones": plan_data.get("future_milestones", []),
    }


@_serialized_campaign_mutation
def cmd_arc(
    campaign_id: str,
    title: str = "",
    question: str = "",
    stage: str = "",
    scene_name: str = "",
    location: str = "",
    date_time: str = "",
    present: str = "",
    resolve_clocks: bool = False,
    milestone: str = "",
    date: str = "",
) -> dict:
    """Atualiza e faz a transição de Arco, cena ativa e marcos em diario.md."""
    if not date_time and date:
        date_time = date
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada em {CAMPAIGN_DIRS}."}

    system_name = info.get("system", DEFAULT_RULESET)
    load_ruleset(system_name)
    camp_dir = Path(info["dir"])
    diario_path = info["diario"]

    store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)

    diario_text_before = diario_path.read_text(encoding="utf-8") if diario_path.exists() else ""
    milestone_clean = milestone.strip() if milestone else ""
    already_archived = (
        milestone_clean
        and (f"* {milestone_clean}" in diario_text_before or f"- {milestone_clean}" in diario_text_before)
    )

    res = update_arc_in_diario(
        diario_path,
        title=title,
        central_question=question,
        stage=stage,
        scene_name=scene_name,
        date_time=date_time,
        location=location,
        present=present,
        resolve_clocks=resolve_clocks,
        archive_milestone=milestone,
    )
    gt, gts, cur_turn = _current_time_info(diario_path, info.get("calendar"))
    drafts: list[EventDraft] = [
        EventDraft(
            type="arc.updated",
            schema_version=1,
            actor=ActorRef(kind="agent", id="showrunner"),
            game_time=gt,
            game_time_sort=gts,
            payload={
                "title": title,
                "question": question,
                "stage": stage,
                "scene_name": scene_name,
                "date_time": date_time,
                "location": location,
                "present": present,
                "resolve_clocks": bool(resolve_clocks),
                "milestone": milestone_clean,
            },
        )
    ]

    if milestone_clean and not already_archived:
        camp_overrides = get_campaign_overrides(campaign_id)
        base_step = get_base_step_from_overrides(camp_overrides)
        arc_xp = evaluate_xp_gain("arc_milestone", overrides=camp_overrides)
        prog_res = update_progression_in_ficha(info["ficha"], xp_add=arc_xp, base_step=base_step)
        append_xp_ledger_entry(diario_path, arc_xp, reason=f"Marco de arco arquivado: '{milestone_clean}'", turn=cur_turn)
        res["arc_milestone_xp"] = arc_xp
        if prog_res.get("level_up"):
            res["level_up"] = prog_res["new_level"]
        drafts.append(
            EventDraft(
                type="protagonist.progression_changed",
                schema_version=1,
                actor=ActorRef(kind="system", id="ruleset"),
                game_time=gt,
                game_time_sort=gts,
                payload={
                    "xp_delta": int(arc_xp),
                    "xp_total": int(prog_res["new_xp"]),
                    "level": int(prog_res["new_level"]),
                    "attribute_points": int(prog_res.get("attribute_points", 0)),
                    "ability_points": int(prog_res.get("ability_points", 0)),
                    "source": f"Marco de arco arquivado: '{milestone_clean}'",
                },
            )
        )
    elif milestone_clean and already_archived:
        res["arc_milestone_warning"] = f"Marco de arco '{milestone_clean}' já constava no diário; XP não duplicado."
    if resolve_clocks:
        quests = parse_quests_from_diario(diario_path)
        orphaned = [q for q in quests if q["status"] == "ACTIVE" and q.get("clock")]
        if orphaned:
            res["orphaned_quests_warning"] = [
                f"Aviso de Orfandade: Missão '{q['title']}' ({q['id']}) permanece ACTIVE mas seu relógio '{q['clock']}' foi arquivado/resolvido na transição de arco."
                for q in orphaned
            ]

    if res.get("updates") or len(drafts) > 1:
        record_command_mutation(camp_dir, campaign_id, store, expected_last_seq, prev_event_id, drafts)

    diario = parse_diario_md(diario_path)
    return {
        "campaign": campaign_id,
        "action_result": res,
        "current_scene_header": f"[{diario['date_time']}] | [{diario['location']}] | [{diario['present']}]",
        "arc": diario.get("arc", {}),
        "active_clocks": [c for c in diario.get("clocks", []) if c["status"] == "ACTIVE"],
    }


@_serialized_campaign_mutation
def cmd_rebuild(campaign_id: str, force: bool = False) -> dict:
    """Reconstrói as projeções canônicas a partir do log de eventos causal (C3)."""
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}
    camp_dir = Path(info["dir"])

    store = create_event_store(camp_dir)
    if store.last_seq(campaign_id) == 0:
        store, _, _ = ensure_campaign_event_log(camp_dir, campaign_id)
    count, proj_hash = rebuild_projections(store, campaign_id, camp_dir, force=force)
    return {
        "status": "ok",
        "campaign": campaign_id,
        "events_replayed": count,
        "projection_hash": proj_hash,
    }


@_serialized_campaign_mutation
def cmd_correct(
    campaign_id: str,
    event: str = "",
    reason: str = "",
    delta_xp: int = 0,
    contradiction: bool = False,
    resolve: bool = False,
) -> dict:
    """Aplica correção append-only reavaliando dependentes e anotando inconsistências (C4)."""
    if not event:
        return {"error": "Argumento --event é obrigatório para correções."}
    if not reason:
        return {"error": "Argumento --reason é obrigatório para correções."}
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}
    camp_dir = Path(info["dir"])

    store, _, _ = ensure_campaign_event_log(camp_dir, campaign_id)
    service = CorrectionService(store)
    changes = []
    if delta_xp != 0:
        changes.append({"field": "xp", "delta": delta_xp})
    if contradiction:
        changes.append({"field": "outcome", "new_value": "voided", "type": "combat.resolved", "contradiction": True})

    all_evts = tuple(store.read(campaign_id))
    gt = all_evts[-1].game_time if all_evts else "Dia 1, 08:00"
    gts = all_evts[-1].game_time_sort if all_evts else 0

    actor = ActorRef(kind="agent", id="showrunner")
    try:
        res = service.issue_correction(
            campaign_id=campaign_id,
            actor=actor,
            corrects=[event],
            reason=reason,
            changes=changes,
            game_time=gt,
            game_time_sort=gts,
            resolve=resolve,
        )
        rebuild_projections(store, campaign_id, camp_dir, emit_audit_event=False)
    except Exception as exc:
        return {"error": str(exc)}
    inconsistency = any(
        (e.type == "correction.issued" and e.payload.get("inconsistency_detected"))
        or (e.type == "correction.recomputed" and e.payload.get("outcome") == "INCONSISTENCY_PENDING_REVIEW")
        for e in res.events
    )
    return {
        "status": "ok",
        "campaign": campaign_id,
        "first_seq": res.first_seq,
        "last_seq": res.last_seq,
        "events_appended": len(res.events),
        "inconsistency_detected": inconsistency,
    }
