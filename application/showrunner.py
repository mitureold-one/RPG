"""Casos de uso do Showrunner: relógios, fila de cenas e transição de arco."""

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
from application.transaction import _serialized_campaign_mutation


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

    diario_path = info["diario"]
    res = {}
    if add_name:
        res = upsert_clock_in_diario(diario_path, add_name, current=0, max_steps=max_steps, trigger=trigger)
    elif advance_name:
        res = upsert_clock_in_diario(
            diario_path, advance_name, advance=advance_steps, create_if_missing=False
        )
    elif resolve_name:
        prior_clocks = parse_clocks_from_diario(diario_path)
        matched_prior = next((c for c in prior_clocks if c["name"].lower() == resolve_name.strip().lower()), None)
        was_active = matched_prior is not None and matched_prior.get("status") == "ACTIVE"

        res = upsert_clock_in_diario(
            diario_path, resolve_name, status="RESOLVED", create_if_missing=False
        )
        all_active_quests = parse_quests_from_diario(diario_path)
        linked_clock_names = {q["clock"].strip().lower() for q in all_active_quests if q.get("clock")}
        if was_active and resolve_name.strip().lower() not in linked_clock_names:
            camp_overrides = get_campaign_overrides(campaign_id)
            base_step = get_base_step_from_overrides(camp_overrides)
            clock_xp = evaluate_xp_gain("clock_resolved", overrides=camp_overrides)
            prog_res = update_progression_in_ficha(info["ficha"], xp_add=clock_xp, base_step=base_step)
            diario_ctx = parse_diario_md(diario_path)
            cur_turn = diario_ctx.get("last_turn_num")
            append_xp_ledger_entry(diario_path, clock_xp, reason=f"Relógio '{resolve_name}' resolvido", turn=cur_turn)
            res["xp_granted"] = clock_xp
            if prog_res.get("level_up"):
                res["level_up"] = prog_res["new_level"]
        elif not was_active:
            res["xp_warning"] = f"Relógio '{resolve_name}' já se encontrava em status '{matched_prior.get('status') if matched_prior else 'INEXISTENTE'}'. Recompensa de XP não duplicada."

    clocks = parse_clocks_from_diario(diario_path)
    return {
        "campaign": campaign_id,
        "action_result": res if res else None,
        "clocks": clocks,
        "active_count": len([c for c in clocks if c["status"] == "ACTIVE"]),
        "breached_count": len([c for c in clocks if c["status"] == "BREACHED"]),
    }


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
    ruleset = load_ruleset(system_name)

    action_res = None
    if add_beat or complete_idx is not None or add_milestone:
        action_res = upsert_planned_scene_in_diario(
            info["diario"],
            scene_type=scene_type,
            beat=add_beat,
            actors=actors,
            mark_done_idx=complete_idx,
            future_milestone=add_milestone,
        )

    diario = parse_diario_md(info["diario"])
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
    ruleset = load_ruleset(system_name)

    diario_text_before = info["diario"].read_text(encoding="utf-8") if info["diario"].exists() else ""
    milestone_clean = milestone.strip() if milestone else ""
    already_archived = (
        milestone_clean
        and (f"* {milestone_clean}" in diario_text_before or f"- {milestone_clean}" in diario_text_before)
    )

    res = update_arc_in_diario(
        info["diario"],
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
    if milestone_clean and not already_archived:
        camp_overrides = get_campaign_overrides(campaign_id)
        base_step = get_base_step_from_overrides(camp_overrides)
        arc_xp = evaluate_xp_gain("arc_milestone", overrides=camp_overrides)
        prog_res = update_progression_in_ficha(info["ficha"], xp_add=arc_xp, base_step=base_step)
        diario_ctx = parse_diario_md(info["diario"])
        cur_turn = diario_ctx.get("last_turn_num")
        append_xp_ledger_entry(info["diario"], arc_xp, reason=f"Marco de arco arquivado: '{milestone_clean}'", turn=cur_turn)
        res["arc_milestone_xp"] = arc_xp
        if prog_res.get("level_up"):
            res["level_up"] = prog_res["new_level"]
    elif milestone_clean and already_archived:
        res["arc_milestone_warning"] = f"Marco de arco '{milestone_clean}' já constava no diário; XP não duplicado."
    if resolve_clocks:
        quests = parse_quests_from_diario(info["diario"])
        orphaned = [q for q in quests if q["status"] == "ACTIVE" and q.get("clock")]
        if orphaned:
            res["orphaned_quests_warning"] = [
                f"Aviso de Orfandade: Missão '{q['title']}' ({q['id']}) permanece ACTIVE mas seu relógio '{q['clock']}' foi arquivado/resolvido na transição de arco."
                for q in orphaned
            ]
    diario = parse_diario_md(info["diario"])
    return {
        "campaign": campaign_id,
        "action_result": res,
        "current_scene_header": f"[{diario['date_time']}] | [{diario['location']}] | [{diario['present']}]",
        "arc": diario.get("arc", {}),
        "active_clocks": [c for c in diario.get("clocks", []) if c["status"] == "ACTIVE"],
    }
