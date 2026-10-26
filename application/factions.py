"""Caso de uso de facções, reputação, favores/débitos e tick off-screen."""

from pathlib import Path
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
    turn_num = int(diario_ctx.get("last_turn_num") or 1)
    gts = game_time_to_minutes(
        gt,
        calendar=calendar_cfg if isinstance(calendar_cfg, dict) else None,
        fallback_turn=turn_num,
    )
    return gt, gts, turn_num


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
    camp_dir = Path(info["dir"])
    mundo_path = info["mundo"]
    ficha_path = info["ficha"]
    diario_path = info["diario"]

    action_res = None
    mutating = bool(add_name or rep or favor or debt or tick)
    store = None
    expected_last_seq = 0
    prev_event_id = ""
    if mutating:
        store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)

    drafts: list[EventDraft] = []
    actor = ActorRef(kind="agent", id="showrunner")
    gt, gts, cur_turn = _current_time_info(diario_path, info.get("calendar"))

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
        drafts.append(
            EventDraft(
                type="command.executed",
                schema_version=1,
                actor=actor,
                game_time=gt,
                game_time_sort=gts,
                payload={"command": "faction.add", "status": "ok", "summary": f"Facção '{add_name}' cadastrada"},
            )
        )
    elif rep:
        parts = rep.rsplit(":", 1)
        fn = parts[0].strip()
        delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(("-", "+")) and parts[1].strip()[1:].isdigit())) else 1
        is_ok, msg = _check_faction_known(fn)
        if not is_ok:
            return {"error": msg}
        res = update_reputation_in_ficha(ficha_path, fn, score_delta=delta)
        rsn = reason or "Ajuste avulso de reputação"
        append_faction_ledger_entry(diario_path, fn, delta_rep=delta, new_score=res["new_score"], reason=rsn, turn=cur_turn)
        action_res = {"action": "reputation_updated", **res}
        if msg:
            action_res["warning"] = msg
        drafts.append(
            EventDraft(
                type="faction.reputation_changed",
                schema_version=1,
                actor=actor,
                game_time=gt,
                game_time_sort=gts,
                payload={
                    "faction": fn,
                    "delta_rep": delta,
                    "new_score": res["new_score"],
                    "delta_favors": 0,
                    "delta_debts": 0,
                    "favors": res.get("favors", 0),
                    "debts": res.get("debts", 0),
                    "turn": cur_turn,
                    "reason": rsn,
                },
            )
        )
    elif favor:
        parts = favor.rsplit(":", 1)
        fn = parts[0].strip()
        delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(("-", "+")) and parts[1].strip()[1:].isdigit())) else 1
        is_ok, msg = _check_faction_known(fn)
        if not is_ok:
            return {"error": msg}
        res = update_reputation_in_ficha(ficha_path, fn, favors_delta=delta)
        rsn = reason or "Ajuste de favores"
        append_faction_ledger_entry(diario_path, fn, delta_rep=0, new_score=res["new_score"], reason=rsn, turn=cur_turn, delta_favors=delta)
        action_res = {"action": "favors_updated", **res}
        if msg:
            action_res["warning"] = msg
        drafts.append(
            EventDraft(
                type="faction.reputation_changed",
                schema_version=1,
                actor=actor,
                game_time=gt,
                game_time_sort=gts,
                payload={
                    "faction": fn,
                    "delta_rep": 0,
                    "new_score": res["new_score"],
                    "delta_favors": delta,
                    "delta_debts": 0,
                    "favors": res.get("favors", 0),
                    "debts": res.get("debts", 0),
                    "turn": cur_turn,
                    "reason": rsn,
                },
            )
        )
    elif debt:
        parts = debt.rsplit(":", 1)
        fn = parts[0].strip()
        delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(("-", "+")) and parts[1].strip()[1:].isdigit())) else 1
        is_ok, msg = _check_faction_known(fn)
        if not is_ok:
            return {"error": msg}
        res = update_reputation_in_ficha(ficha_path, fn, debts_delta=delta)
        rsn = reason or "Ajuste de débitos"
        append_faction_ledger_entry(diario_path, fn, delta_rep=0, new_score=res["new_score"], reason=rsn, turn=cur_turn, delta_debts=delta)
        action_res = {"action": "debts_updated", **res}
        if msg:
            action_res["warning"] = msg
        drafts.append(
            EventDraft(
                type="faction.reputation_changed",
                schema_version=1,
                actor=actor,
                game_time=gt,
                game_time_sort=gts,
                payload={
                    "faction": fn,
                    "delta_rep": 0,
                    "new_score": res["new_score"],
                    "delta_favors": 0,
                    "delta_debts": delta,
                    "favors": res.get("favors", 0),
                    "debts": res.get("debts", 0),
                    "turn": cur_turn,
                    "reason": rsn,
                },
            )
        )
    elif tick:
        action_res = simulate_faction_tick(info)
        drafts.append(
            EventDraft(
                type="command.executed",
                schema_version=1,
                actor=actor,
                game_time=gt,
                game_time_sort=gts,
                payload={
                    "command": "faction.tick",
                    "status": "ok",
                    "summary": "Tick off-screen de facções",
                    "clock_updates": action_res.get("advancements", []),
                },
            )
        )

    if mutating and drafts and store is not None:
        record_command_mutation(camp_dir, campaign_id, store, expected_last_seq, prev_event_id, drafts)

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
