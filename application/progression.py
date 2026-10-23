"""Casos de uso de missões e progressão do protagonista."""

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
from application.transaction import _serialized_campaign_mutation


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

    diario_path = info["diario"]
    res = {}

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
    elif check_target:
        parts = check_target.split(":")
        qid = parts[0].strip().upper()
        idx = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 1
        res = upsert_quest_in_diario(diario_path, action="check", quest_id=qid, check_index=idx)
    elif complete_id:
        res = upsert_quest_in_diario(diario_path, action="complete", quest_id=complete_id.strip().upper(), evidence=evidence)
    elif fail_id:
        res = upsert_quest_in_diario(diario_path, action="fail", quest_id=fail_id.strip().upper(), reason=reason)
    elif block_id:
        res = upsert_quest_in_diario(diario_path, action="block", quest_id=block_id.strip().upper(), reason=reason)
    elif unblock_id:
        res = upsert_quest_in_diario(diario_path, action="unblock", quest_id=unblock_id.strip().upper())
    elif abandon_id:
        res = upsert_quest_in_diario(diario_path, action="abandon", quest_id=abandon_id.strip().upper(), reason=reason)
    elif reopen_id:
        res = upsert_quest_in_diario(diario_path, action="reopen", quest_id=reopen_id.strip().upper(), reason=reason)

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

    ficha_path = info["ficha"]
    res = {}

    if spend_attr:
        overrides = get_campaign_overrides(campaign_id)
        stat_ceil = get_stat_ceiling_from_overrides(overrides)
        res = spend_attribute_point_in_ficha(ficha_path, spend_attr, stat_ceiling=stat_ceil)
    elif spend_ability:
        res = spend_ability_point_in_ficha(ficha_path, spend_ability, training)
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

        diario_path = info["diario"]
        diario_ctx = parse_diario_md(diario_path)
        cur_turn = diario_ctx.get("last_turn_num")
        append_xp_ledger_entry(diario_path, xp_gain, reason=reason or f"Concessão avulsa: {code}", turn=cur_turn)

    progression = parse_progression_from_ficha(ficha_path)
    return {
        "campaign": campaign_id,
        "action_result": res if res else None,
        "progression": progression,
    }
