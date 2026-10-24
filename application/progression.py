"""Casos de uso de missões e progressão do protagonista."""

from pathlib import Path
import re

from council import (
    get_campaign_overrides,
    find_campaign,
    parse_diario_md,
    parse_quests_from_diario,
    upsert_quest_in_diario,
    append_xp_ledger_entry,
    parse_progression_from_ficha,
    update_progression_in_ficha,
    spend_attribute_point_in_ficha,
    spend_ability_point_in_ficha,
)
from rulesets.progression import evaluate_xp_gain, get_base_step_from_overrides, get_stat_ceiling_from_overrides
from application.transaction import (
    _serialized_campaign_mutation,
    ensure_campaign_event_log,
    record_command_mutation,
)
from contracts.event import ActorRef, EventDraft
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
def cmd_quest(
    campaign_id: str,
    list_quests: bool = False,
    add_title: str = "",
    quest_type: str = "main",
    objective: str = "",
    faction: str = "",
    clock: str = "",
    reward: str = "",
    phase: str = "",
    add_objective: str = "",
    check_target: str = "",
    complete_id: str = "",
    fail_id: str = "",
    block_id: str = "",
    unblock_id: str = "",
    abandon_id: str = "",
    reopen_id: str = "",
    reason: str = "",
    evidence: str = "",
) -> dict:
    """Gerencia missões, objetivos pontuais e máquina de estados em diario.md."""
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}

    camp_dir = Path(info["dir"])
    diario_path = info["diario"]
    res = {}
    mutating = bool(
        add_title or add_objective or objective or check_target or complete_id
        or fail_id or block_id or unblock_id or abandon_id or reopen_id
    )
    store = None
    expected_last_seq = 0
    prev_event_id = ""
    if mutating:
        store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)

    drafts: list[EventDraft] = []
    actor = ActorRef(kind="agent", id="showrunner")
    gt, gts, _ = _current_time_info(diario_path, info.get("calendar"))

    if add_title:
        res = upsert_quest_in_diario(
            diario_path,
            action="add",
            title=add_title,
            quest_type=quest_type,
            objective=objective,
            contractor=faction,
            clock=clock,
            reward=reward,
            phase=phase,
        )
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.created",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={
                        "id": str(res.get("id", "Q1")),
                        "title": add_title.strip(),
                        "type": quest_type.upper(),
                        "objectives": [objective.strip()] if objective else [],
                    },
                )
            )
    elif add_objective or (objective and not add_title):
        raw_obj = add_objective or objective
        parts = raw_obj.split(":", 1)
        if len(parts) == 2 and re.match(r"^Q\d+$", parts[0].strip(), re.IGNORECASE):
            qid = parts[0].strip().upper()
            obj_txt = parts[1].strip()
        else:
            qid = "Q1"
            obj_txt = raw_obj.strip()
        res = upsert_quest_in_diario(diario_path, action="add_objective", quest_id=qid, objective=obj_txt)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.status_changed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"id": qid, "status": "ACTIVE", "reason": f"Objetivo adicionado: {obj_txt}"},
                )
            )
    elif check_target:
        parts = check_target.split(":")
        qid = parts[0].strip().upper()
        idx = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 1
        res = upsert_quest_in_diario(diario_path, action="check", quest_id=qid, check_index=idx)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.objective_completed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"id": qid, "objective_idx": idx, "xp_awarded": 0},
                )
            )
    elif complete_id:
        qid = complete_id.strip().upper()
        res = upsert_quest_in_diario(diario_path, action="complete", quest_id=qid, evidence=evidence)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.completed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"id": qid, "xp_awarded": int(res.get("xp_paid") or 0)},
                )
            )
    elif fail_id:
        qid = fail_id.strip().upper()
        res = upsert_quest_in_diario(diario_path, action="fail", quest_id=qid, reason=reason)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.failed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"id": qid, "reason": reason or "Falha administrativa"},
                )
            )
    elif block_id:
        qid = block_id.strip().upper()
        res = upsert_quest_in_diario(diario_path, action="block", quest_id=qid, reason=reason)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.status_changed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"id": qid, "status": "BLOCKED", "reason": reason},
                )
            )
    elif unblock_id:
        qid = unblock_id.strip().upper()
        res = upsert_quest_in_diario(diario_path, action="unblock", quest_id=qid)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.status_changed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"id": qid, "status": "ACTIVE"},
                )
            )
    elif abandon_id:
        qid = abandon_id.strip().upper()
        res = upsert_quest_in_diario(diario_path, action="abandon", quest_id=qid, reason=reason)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.status_changed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"id": qid, "status": "ABANDONED", "reason": reason},
                )
            )
    elif reopen_id:
        qid = reopen_id.strip().upper()
        res = upsert_quest_in_diario(diario_path, action="reopen", quest_id=qid, reason=reason)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="quest.status_changed",
                    schema_version=1,
                    actor=actor,
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"id": qid, "status": "ACTIVE", "reason": reason},
                )
            )

    if mutating and drafts and store is not None:
        record_command_mutation(camp_dir, campaign_id, store, expected_last_seq, prev_event_id, drafts)

    quests = parse_quests_from_diario(diario_path)
    active_count = len([q for q in quests if q["status"] == "ACTIVE"])
    completed_count = len([q for q in quests if q["status"] == "COMPLETED"])

    return {
        "campaign": campaign_id,
        "action_result": res if res else None,
        "quests": quests,
        "active_count": active_count,
        "completed_count": completed_count,
    }


@_serialized_campaign_mutation
def cmd_progress(
    campaign_id: str,
    list_progress: bool = False,
    spend_attr: str = "",
    spend_ability: str = "",
    training: str = "",
    award: str = "",
    reason: str = "",
) -> dict:
    """Gerencia consulta de progresso, gasto de pontos de atributo/habilidade e concessão de XP em ficha.md."""
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}

    camp_dir = Path(info["dir"])
    ficha_path = info["ficha"]
    diario_path = info["diario"]
    res = {}
    mutating = bool(spend_attr or spend_ability or award)
    store = None
    expected_last_seq = 0
    prev_event_id = ""
    if mutating:
        store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)

    drafts: list[EventDraft] = []
    gt, gts, cur_turn = _current_time_info(diario_path, info.get("calendar"))

    if spend_attr:
        overrides = get_campaign_overrides(campaign_id)
        stat_ceil = get_stat_ceiling_from_overrides(overrides)
        res = spend_attribute_point_in_ficha(ficha_path, spend_attr, stat_ceiling=stat_ceil)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="protagonist.sheet_changed",
                    schema_version=1,
                    actor=ActorRef(kind="agent", id="narrative_engine"),
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"kind": "attribute", "target": spend_attr.strip(), "new_value": res.get("new_value"), "source": "spend_attr"},
                )
            )
    elif spend_ability:
        res = spend_ability_point_in_ficha(ficha_path, spend_ability, training)
        if not res.get("error"):
            drafts.append(
                EventDraft(
                    type="protagonist.sheet_changed",
                    schema_version=1,
                    actor=ActorRef(kind="agent", id="narrative_engine"),
                    game_time=gt,
                    game_time_sort=gts,
                    payload={"kind": "ability", "target": spend_ability.strip(), "new_value": spend_ability.strip(), "source": "spend_ability"},
                )
            )
    elif award:
        parts = award.split(":")
        code = parts[0].strip()
        amount = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else None
        if code.isdigit():
            amount = int(code)
            code = "custom"
        overrides = get_campaign_overrides(campaign_id)
        base_step = get_base_step_from_overrides(overrides)
        xp_gain = evaluate_xp_gain(code, amount=amount, overrides=overrides)
        res = update_progression_in_ficha(ficha_path, xp_add=xp_gain, base_step=base_step)
        res["source"] = code
        res["xp_granted"] = xp_gain

        src_txt = reason or f"Concessão avulsa: {code}"
        append_xp_ledger_entry(diario_path, xp_gain, reason=src_txt, turn=cur_turn)
        drafts.append(
            EventDraft(
                type="protagonist.progression_changed",
                schema_version=1,
                actor=ActorRef(kind="system", id="ruleset"),
                game_time=gt,
                game_time_sort=gts,
                payload={
                    "xp_delta": int(xp_gain),
                    "xp_total": int(res["new_xp"]),
                    "level": int(res["new_level"]),
                    "attribute_points": int(res.get("attribute_points", 0)),
                    "ability_points": int(res.get("ability_points", 0)),
                    "source": src_txt,
                },
            )
        )

    if mutating and drafts and store is not None:
        record_command_mutation(camp_dir, campaign_id, store, expected_last_seq, prev_event_id, drafts)

    progression = parse_progression_from_ficha(ficha_path)
    return {
        "campaign": campaign_id,
        "action_result": res if res else None,
        "progression": progression,
    }
