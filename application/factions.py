"""Caso de uso de facções, reputação, favores/débitos e tick off-screen."""

import sys
from typing import Optional, Tuple

from council import find_campaign, parse_diario_md, parse_clocks_from_diario
from council.factions import (
    parse_factions_from_mundo,
    upsert_faction_in_mundo,
    parse_reputation_from_ficha,
    update_reputation_in_ficha,
    append_faction_ledger_entry,
    simulate_faction_tick,
)
from application.transaction import _serialized_campaign_mutation


@_serialized_campaign_mutation
def cmd_faction(
    campaign_id: str,
    list_factions: bool = False,
    add_name: str = "",
    tag: str = "",
    power: int = 3,
    scale: str = "regional",
    clock: str = "",
    desc: str = "",
    rep: str = "",
    reason: str = "",
    favor: str = "",
    debt: str = "",
    tick: bool = False,
    create: bool = False,
) -> dict:
    """Gerencia facções, reputação numérica (-3 a +3), favores/débitos e turno off-screen (Fase 3)."""
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada."}

    info["id"] = campaign_id
    mundo_path = info["mundo"]
    ficha_path = info["ficha"]
    diario_path = info["diario"]

    action_res = None

    def _check_faction_known(fn_name: str) -> Tuple[bool, Optional[str]]:
        factions_in_mundo = parse_factions_from_mundo(mundo_path)
        known = any(f["name"].lower() == fn_name.lower() or f["tag"].lower() == fn_name.lower() for f in factions_in_mundo)
        if not known:
            if not create:
                err = f"Facção '{fn_name}' não encontrada em mundo.md. Registre-a previamente com 'faction --add' ou passe '--create' para permitir o cadastro na ficha."
                return False, err
            w = f"Facção '{fn_name}' não encontrada em mundo.md, mas cadastrada na ficha via --create."
            sys.stderr.write(f"[AVISO] {w}\n")
            return True, w
        return True, None

    if add_name:
        action_res = upsert_faction_in_mundo(
            mundo_path,
            name=add_name,
            tag=tag,
            power=power,
            scale=scale,
            clock=clock,
            desc=desc,
        )
    elif rep:
        parts = rep.rsplit(":", 1)
        fn = parts[0].strip()
        delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(('-', '+')) and parts[1].strip()[1:].isdigit())) else 1
        is_ok, msg = _check_faction_known(fn)
        if not is_ok:
            return {"error": msg}
        res = update_reputation_in_ficha(ficha_path, fn, score_delta=delta)
        cur_turn = parse_diario_md(diario_path).get("last_turn_num", 1)
        append_faction_ledger_entry(diario_path, fn, delta_rep=delta, new_score=res["new_score"], reason=reason or "Ajuste avulso de reputação", turn=cur_turn)
        action_res = {"action": "reputation_updated", **res}
        if msg:
            action_res["warning"] = msg
    elif favor:
        parts = favor.rsplit(":", 1)
        fn = parts[0].strip()
        delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(('-', '+')) and parts[1].strip()[1:].isdigit())) else 1
        is_ok, msg = _check_faction_known(fn)
        if not is_ok:
            return {"error": msg}
        res = update_reputation_in_ficha(ficha_path, fn, favors_delta=delta)
        cur_turn = parse_diario_md(diario_path).get("last_turn_num", 1)
        append_faction_ledger_entry(diario_path, fn, delta_rep=0, new_score=res["new_score"], reason=reason or "Ajuste de favores", turn=cur_turn, delta_favors=delta)
        action_res = {"action": "favors_updated", **res}
        if msg:
            action_res["warning"] = msg
    elif debt:
        parts = debt.rsplit(":", 1)
        fn = parts[0].strip()
        delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(('-', '+')) and parts[1].strip()[1:].isdigit())) else 1
        is_ok, msg = _check_faction_known(fn)
        if not is_ok:
            return {"error": msg}
        res = update_reputation_in_ficha(ficha_path, fn, debts_delta=delta)
        cur_turn = parse_diario_md(diario_path).get("last_turn_num", 1)
        append_faction_ledger_entry(diario_path, fn, delta_rep=0, new_score=res["new_score"], reason=reason or "Ajuste de débitos", turn=cur_turn, delta_debts=delta)
        action_res = {"action": "debts_updated", **res}
        if msg:
            action_res["warning"] = msg
    elif tick:
        action_res = simulate_faction_tick(info)

    factions = parse_factions_from_mundo(mundo_path)
    reps = parse_reputation_from_ficha(ficha_path)
    clocks = parse_clocks_from_diario(diario_path)
    clock_map = {c["name"].lower(): c for c in clocks}

    enriched_factions = []
    for f in factions:
        rep_data = reps.get(f["name"].lower(), reps.get(f["tag"].lower(), {}))
        c_name = f.get("clock")
        c_match = clock_map.get(c_name.lower()) if c_name else None
        enriched_factions.append({
            "tag": f["tag"],
            "name": f["name"],
            "description": f["description"],
            "power": f["power"],
            "scale": f["scale"],
            "clock": f.get("clock", ""),
            "clock_progress": f"{c_match['progress']} [{c_match['status']}]" if c_match else None,
            "protagonist_reputation": {
                "score": rep_data.get("score", 0),
                "tier": rep_data.get("tier", "Neutro"),
                "favors": rep_data.get("favors", 0),
                "debts": rep_data.get("debts", 0),
                "social_dc_modifier": rep_data.get("social_dc_modifier", 0),
            },
        })

    return {
        "campaign": campaign_id,
        "action_result": action_res,
        "factions": enriched_factions,
    }
