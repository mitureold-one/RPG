"""Execução em staging e montagem de eventos para `cmd_commit`."""

import re
import shutil
from pathlib import Path
from typing import Any

from council.helpers import atomic_write_text
from council import (
    get_campaign_overrides, parse_ficha_md, parse_diario_md, apply_npc_updates_to_md,
    upsert_ficha_feature, upsert_clock_in_diario, parse_clocks_from_diario,
    upsert_planned_scene_in_diario, parse_quests_from_diario, upsert_quest_in_diario,
    append_xp_ledger_entry, update_progression_in_ficha,
)
from rulesets.progression import evaluate_xp_gain, get_base_step_from_overrides, DEFAULT_QUEST_REWARDS
from council.factions import update_reputation_in_ficha, append_faction_ledger_entry
from application.commit_events import build_commit_event_drafts
from application.commit_validation import _split_name_value


def _parse_faction_delta(raw: str) -> int:
    s = raw.strip()
    return int(s) if (s.isdigit() or (s.startswith(("-", "+")) and s[1:].isdigit())) else 1


def _append_lvl_up(applied: list[str], prog_res: dict[str, Any]) -> None:
    if prog_res.get("level_up"):
        applied.append(
            f"EVOLUÇÃO DE NÍVEL: O protagonista atingiu o Nível {prog_res['new_level']}! "
            f"(+{prog_res['bonuses']['attribute_points']} Ponto(s) de Atributo, vitais expandidos)."
        )


def stage_commit_mutations(
    *, campaign_id: str, info: dict[str, Any], camp_dir: Path, ficha_data: dict[str, Any],
    summary: str, sum_low: str, scene_type: str, deltas: dict[str, int], precomputed_new_dt: str,
    location: str, present_npcs: str, npc_updates: str, state_shift: str,
    clock_advance: str, clock_resolve: str, quest_progress: str, quest_complete: str, quest_fail: str,
    faction_rep: str, faction_favor: str, faction_debt: str, add_ability: str, add_milestone: str,
    add_item: str, raw_prose: str, known_factions: set[str], prev_event_id: str, applied: list[str],
) -> tuple[list, str, str, str, int, str]:
    orig_ficha_path, orig_diario_path, orig_npcs_path = Path(info["ficha"]), Path(info["diario"]), Path(info["npcs"])
    stage_dir = camp_dir / ".staging"
    stage_dir.mkdir(parents=True, exist_ok=True)
    ficha_path, diario_path, npcs_path = stage_dir / "ficha.md", stage_dir / "diario.md", stage_dir / "npcs.md"

    try:
        for src, dst in ((orig_ficha_path, ficha_path), (orig_diario_path, diario_path), (orig_npcs_path, npcs_path)):
            if src.exists():
                dst.write_bytes(src.read_bytes())

        clock_events, quest_events, xp_events, faction_events = [], [], [], []
        scene_completed_idx: int | None = None
        restored_vitals = False

        if deltas and ficha_path.exists():
            ficha_text = ficha_path.read_text(encoding="utf-8")
            for key, delta in deltas.items():
                if key in ficha_data["vitals"]:
                    v = ficha_data["vitals"][key]
                    new_val = max(0, min(v["max"], v["current"] + delta))
                    v["current"] = new_val
                    pattern = rf"(\*\s*\*\*{re.escape(v['label'])}:\*\*\s*)\d+(\s*/\s*{v['max']})"
                    ficha_text = re.sub(pattern, rf"\g<1>{new_val}\g<2>", ficha_text)
                    applied.append(f"{v['label']}: {new_val}/{v['max']} ({delta:+d})")
            atomic_write_text(ficha_path, ficha_text)
        elif scene_type == "timeskip" and not deltas and ficha_path.exists():
            ficha_text = ficha_path.read_text(encoding="utf-8")
            restored = []
            for v in ficha_data["vitals"].values():
                if v["max"] > 0 and v["current"] < v["max"]:
                    pattern = rf"(\*\s*\*\*{re.escape(v['label'])}:\*\*\s*)\d+(\s*/\s*{v['max']})"
                    ficha_text = re.sub(pattern, rf"\g<1>{v['max']}\g<2>", ficha_text)
                    restored.append(f"{v['label']}: {v['max']}/{v['max']} (pleno descanso)")
            if restored:
                restored_vitals = True
                atomic_write_text(ficha_path, ficha_text)
                applied.extend(restored)

        if add_ability or add_milestone or add_item:
            applied.extend(upsert_ficha_feature(ficha_path, ability=add_ability, milestone=add_milestone, item=add_item))

        if npc_updates:
            applied.extend(apply_npc_updates_to_md(npcs_path, npc_updates))
        else:
            pres_str = present_npcs or parse_diario_md(diario_path).get("present", "")
            p_names = [p.strip() for p in re.split(r",|\be\b", re.sub(r"\([^)]*\)", "", pres_str)) if p.strip()]
            npc_names_in_scene = [p for p in p_names if p.lower() != ficha_data.get("name", "").lower() and p and p[0].isupper()]
            if npc_names_in_scene:
                applied.append(f"ALERTA_SSOT: Nenhum --npc-updates fornecido no commit para os NPCs ativos em cena ({', '.join(npc_names_in_scene)}).")

        resolved_clocks = []
        if clock_resolve and diario_path.exists():
            for item in clock_resolve.split("|"):
                c_name = item.strip()
                if c_name:
                    ups_res = upsert_clock_in_diario(diario_path, c_name, status="RESOLVED", create_if_missing=False)
                    applied.append(f"Relógio '{c_name}' resolvido via commit [{ups_res.get('status')}].")
                    resolved_clocks.append(c_name)
                    clock_events.append({"type": "clock.resolved", "payload": {"name": c_name, "outcome": "RESOLVED"}})
        if clock_advance and diario_path.exists():
            for item in clock_advance.split("|"):
                c_name, c_steps_raw = _split_name_value(item)
                c_steps = int(c_steps_raw) if c_steps_raw.isdigit() else 1
                ups_res = upsert_clock_in_diario(diario_path, c_name, advance=c_steps, create_if_missing=False)
                st_now = ups_res.get("status", "ACTIVE")
                applied.append(f"Relógio '{c_name}' avançado em +{c_steps} -> {ups_res.get('current', '?')}/{ups_res.get('max', '?')} [{st_now}].")
                clock_events.append({"type": "clock.advanced", "payload": {"name": c_name, "delta": c_steps, "current": int(ups_res.get("current", 0)), "max": int(ups_res.get("max", 4)), "status": st_now}})
                if st_now == "RESOLVED":
                    resolved_clocks.append(c_name)
                    clock_events.append({"type": "clock.resolved", "payload": {"name": c_name, "outcome": "RESOLVED"}})
        elif diario_path.exists():
            for c in parse_clocks_from_diario(diario_path):
                if c["status"] == "ACTIVE":
                    c_tokens = [tok.lower() for tok in re.split(r"[\s:,&()-]+", c["name"] + " " + c.get("trigger", "")) if len(tok) >= 4]
                    if sum(1 for tok in c_tokens if tok in sum_low) >= 2:
                        ups_res = upsert_clock_in_diario(diario_path, c["name"], advance=1, create_if_missing=False)
                        st_now = ups_res.get("status", "ACTIVE")
                        applied.append(f"Auto-avanço: Relógio '{c['name']}' avançado em +1 ({ups_res.get('current')}/{ups_res.get('max')} [{st_now}]).")
                        clock_events.append({"type": "clock.advanced", "payload": {"name": c["name"], "delta": 1, "current": int(ups_res.get("current", 0)), "max": int(ups_res.get("max", 4)), "status": st_now}})
                        if st_now == "RESOLVED":
                            resolved_clocks.append(c["name"])
                            clock_events.append({"type": "clock.resolved", "payload": {"name": c["name"], "outcome": "RESOLVED"}})

        diario_ctx = parse_diario_md(diario_path)
        next_turn = diario_ctx["last_turn_num"] + 1
        camp_overrides = get_campaign_overrides(campaign_id)
        base_step = get_base_step_from_overrides(camp_overrides)

        if resolved_clocks:
            linked_clock_names = {q["clock"].strip().lower() for q in parse_quests_from_diario(diario_path) if q.get("clock")}
            for c_name in resolved_clocks:
                if c_name.strip().lower() not in linked_clock_names:
                    clock_xp = evaluate_xp_gain("clock_resolved", overrides=camp_overrides)
                    prog_res = update_progression_in_ficha(ficha_path, xp_add=clock_xp, base_step=base_step)
                    append_xp_ledger_entry(diario_path, clock_xp, reason=f"Relógio '{c_name}' resolvido", turn=next_turn)
                    xp_events.append({"xp_delta": clock_xp, "xp_total": prog_res["new_xp"], "level": prog_res["new_level"], "source": f"Relógio '{c_name}' resolvido"})
                    applied.append(f"Relógio Resolvido: '{c_name}' concluído com sucesso (+{clock_xp} XP concedido).")
                    _append_lvl_up(applied, prog_res)

        if quest_progress and diario_path.exists():
            for item in quest_progress.split("|"):
                parts = item.split(":")
                qid = parts[0].strip().upper()
                idx = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 1
                ups_res = upsert_quest_in_diario(diario_path, "check", quest_id=qid, check_index=idx, current_turn=next_turn)
                if ups_res.get("action") == "objective_checked":
                    q_match = next((q for q in parse_quests_from_diario(diario_path) if q["id"].upper() == qid), None)
                    code = "obj_main" if (q_match and q_match.get("type") == "MAIN") else "obj_side"
                    xp_gain = evaluate_xp_gain(code, overrides=camp_overrides)
                    prog_res = update_progression_in_ficha(ficha_path, xp_add=xp_gain, base_step=base_step)
                    append_xp_ledger_entry(diario_path, xp_gain, reason=f"Objetivo {qid}:{idx} concluído", turn=next_turn)
                    quest_events.append({"type": "quest.objective_completed", "payload": {"id": qid, "objective_idx": idx, "xp_awarded": xp_gain}})
                    xp_events.append({"xp_delta": xp_gain, "xp_total": prog_res["new_xp"], "level": prog_res["new_level"], "source": f"Objetivo {qid}:{idx} concluído"})
                    applied.append(f"Progresso de Missão: Objetivo {qid}:{idx} marcado como concluído (+{xp_gain} XP).")
                    _append_lvl_up(applied, prog_res)

        duplicate_quest_attempts = []
        if quest_complete and diario_path.exists():
            for qid in quest_complete.split("|"):
                qid = qid.strip().upper()
                q_match = next((q for q in parse_quests_from_diario(diario_path) if q["id"].upper() == qid), None)
                if q_match:
                    if q_match.get("xp_paid") is not None and q_match.get("xp_paid") > 0:
                        applied.append(f"Aviso de Idempotência: Missão '{q_match['title']}' ({qid}) já teve recompensa de XP concedida ({q_match['xp_paid']} XP).")
                        applied.append(f"ALERTA_CRITICO: Tentativa de pagamento duplicado de XP barrada para missão '{q_match['title']}' ({qid}).")
                        duplicate_quest_attempts.append(q_match)
                        upsert_quest_in_diario(diario_path, "complete", quest_id=qid, current_turn=next_turn)
                        quest_events.append({"type": "quest.completed", "payload": {"id": qid, "xp_awarded": 0}})
                    elif q_match.get("status") == "COMPLETED":
                        applied.append(f"Aviso de Idempotência: Missão '{q_match['title']}' ({qid}) já está COMPLETED; XP não concedido novamente. Use 'quest --reopen' antes de concluir outra vez.")
                    else:
                        reward_xp = q_match.get("reward_xp") or DEFAULT_QUEST_REWARDS.get(q_match.get("type", "MAIN").upper(), 150)
                        upsert_quest_in_diario(diario_path, "complete", quest_id=qid, xp_paid=reward_xp, current_turn=next_turn)
                        prog_res = update_progression_in_ficha(ficha_path, xp_add=reward_xp, base_step=base_step)
                        quest_events.append({"type": "quest.completed", "payload": {"id": qid, "xp_awarded": reward_xp}})
                        xp_events.append({"xp_delta": reward_xp, "xp_total": prog_res["new_xp"], "level": prog_res["new_level"], "source": f"Missão '{q_match['title']}' ({qid}) concluída"})
                        applied.append(f"Missão Concluída: '{q_match['title']}' ({qid}) finalizada com sucesso (+{reward_xp} XP concedido).")
                        _append_lvl_up(applied, prog_res)
                        contractor = (q_match.get("contractor") or "").strip()
                        if contractor and contractor.lower() not in known_factions:
                            applied.append(f"Contrato Cumprido: facção contratante '{contractor}' não está cadastrada em mundo.md; reputação e favores não foram alterados.")
                        elif contractor:
                            f_res = update_reputation_in_ficha(ficha_path, contractor, score_delta=1, favors_delta=1)
                            reason_txt = f"Cumprimento de missão contratada ({qid})"
                            append_faction_ledger_entry(diario_path, contractor, delta_rep=1, new_score=f_res["new_score"], reason=reason_txt, turn=next_turn, delta_favors=1, quest_id=qid)
                            faction_events.append({"faction": contractor, "delta_rep": 1, "new_score": f_res["new_score"], "delta_favors": 1, "delta_debts": 0, "reason": reason_txt, "quest_id": qid})
                            applied.append(f"Contrato Cumprido: Reputação com '{contractor}' +1 -> {f_res['new_score']} [{f_res['new_tier']}], Favores +1.")

        if quest_fail and diario_path.exists():
            for item in quest_fail.split("|"):
                parts = item.split(":")
                qid, reason_text = parts[0].strip().upper(), (parts[1].strip() if len(parts) > 1 else "")
                q_match = next((q for q in parse_quests_from_diario(diario_path) if q["id"].upper() == qid), None)
                upsert_quest_in_diario(diario_path, "fail", quest_id=qid, reason=reason_text, current_turn=next_turn)
                quest_events.append({"type": "quest.failed", "payload": {"id": qid, "reason": reason_text or "Sem justificativa"}})
                applied.append(f"Missão Fracassada: '{qid}' encerrada com status FAILED ({reason_text or 'Sem justificativa'}).")
                if q_match and q_match.get("contractor"):
                    contractor = q_match["contractor"].strip()
                    if contractor and contractor.lower() not in known_factions:
                        applied.append(f"Contrato Fracassado: facção contratante '{contractor}' não está cadastrada em mundo.md; reputação e débitos não foram alterados.")
                    elif contractor:
                        f_res = update_reputation_in_ficha(ficha_path, contractor, score_delta=-1, debts_delta=1)
                        reason_txt = f"Fracasso de missão contratada ({qid}): {reason_text or 'Falha de execução'}"
                        append_faction_ledger_entry(diario_path, contractor, delta_rep=-1, new_score=f_res["new_score"], reason=reason_txt, turn=next_turn, delta_debts=1, quest_id=qid)
                        faction_events.append({"faction": contractor, "delta_rep": -1, "new_score": f_res["new_score"], "delta_favors": 0, "delta_debts": 1, "reason": reason_txt, "quest_id": qid})
                        applied.append(f"Contrato Fracassado: Reputação com '{contractor}' -1 -> {f_res['new_score']} [{f_res['new_tier']}], Débitos +1.")

        for raw_arg, mode_key, reason_lbl in (
            (faction_rep, "rep", "Ajuste de reputação no commit"),
            (faction_favor, "favor", "Ajuste de favores no commit"),
            (faction_debt, "debt", "Ajuste de débitos no commit"),
        ):
            if raw_arg and ficha_path.exists():
                for item in raw_arg.split("|"):
                    parts = item.split(":")
                    fn, delta = parts[0].strip(), (_parse_faction_delta(parts[1]) if len(parts) > 1 else 1)
                    d_rep, d_fav, d_deb = (delta if mode_key == "rep" else 0), (delta if mode_key == "favor" else 0), (delta if mode_key == "debt" else 0)
                    f_res = update_reputation_in_ficha(ficha_path, fn, score_delta=d_rep, favors_delta=d_fav, debts_delta=d_deb)
                    append_faction_ledger_entry(diario_path, fn, delta_rep=d_rep, new_score=f_res["new_score"], reason=reason_lbl, turn=next_turn, delta_favors=d_fav, delta_debts=d_deb)
                    faction_events.append({"faction": fn, "delta_rep": d_rep, "new_score": f_res["new_score"], "delta_favors": d_fav, "delta_debts": d_deb, "reason": reason_lbl})
                    if mode_key == "rep":
                        applied.append(f"Reputação com '{fn}': {delta:+d} -> {f_res['new_score']} [{f_res['new_tier']}].")
                    elif mode_key == "favor":
                        applied.append(f"Favores com '{fn}': {delta:+d} -> {f_res['favors']}.")
                    else:
                        applied.append(f"Débitos com '{fn}': {delta:+d} -> {f_res['debts']}.")

        next_sc = diario_ctx.get("plot_plan", {}).get("next_scene")
        if next_sc and not next_sc.get("done"):
            sc_type_match = next_sc["scene_type"].lower() == scene_type.lower()
            actors_match = any(act.strip().lower() in sum_low for act in re.split(r"[\s,]+", next_sc.get("actors", "")) if len(act.strip()) > 3) if next_sc.get("actors") else False
            if sc_type_match or actors_match:
                upsert_planned_scene_in_diario(diario_path, mark_done_idx=0)
                scene_completed_idx = 0
                applied.append(f"Fila de Trama: Cena agendada [{next_sc['scene_type']}] concluída e marcada como [x].")

        ficha_after = parse_ficha_md(ficha_path)
        vitals_snapshot = ", ".join(f"{v['label'].split('(')[0].strip()} {v['current']}/{v['max']}" for v in ficha_after["vitals"].values())
        vitals_after_dict = {k: v["current"] for k, v in ficha_after["vitals"].items()} if ficha_after.get("vitals") else {}

        new_dt, new_loc, new_pres = precomputed_new_dt, (location.strip() if location else diario_ctx["location"]), (present_npcs.strip() if present_npcs else diario_ctx["present"])
        time_changed, loc_changed, pres_changed = (new_dt != diario_ctx["date_time"]), (new_loc != diario_ctx["location"]), (new_pres != diario_ctx["present"])
        if time_changed:
            applied.append(f"Relógio atualizado -> {new_dt}")
        if loc_changed:
            applied.append(f"Local atualizado -> {new_loc}")
        if pres_changed:
            applied.append(f"Presentes atualizados -> {new_pres}")
        if state_shift.strip():
            applied.append(f"Mudança de Estado registrada: '{state_shift.strip().rstrip('.')}'")
        applied.append(f"Diário atualizado: Turno {next_turn} registrado.")

        alerts_list = [f"Tentativa de pagamento duplicado de XP barrada para missão '{dup['title']}' ({dup['id']})." for dup in duplicate_quest_attempts]
        drafts = build_commit_event_drafts(
            camp_dir=camp_dir, next_turn=next_turn, summary=summary, scene_type=scene_type,
            new_dt=new_dt, new_loc=new_loc, new_pres=new_pres, calendar_cfg=info.get("calendar"),
            prev_event_id=prev_event_id, deltas=deltas, add_ability=add_ability,
            add_milestone=add_milestone, add_item=add_item, npc_updates=npc_updates,
            clock_events=clock_events, quest_events=quest_events, xp_events=xp_events,
            faction_events=faction_events, scene_completed_idx=scene_completed_idx,
            raw_prose=raw_prose, ficha_after_path=ficha_path, diario_after_path=diario_path,
            npcs_after_path=npcs_path, vitals_after=vitals_after_dict, vitals_line=vitals_snapshot,
            state_shift=state_shift, alerts=alerts_list, restored_vitals=restored_vitals,
            time_changed=time_changed, location_changed=loc_changed, present_changed=pres_changed,
            base_step=base_step,
        )
        return drafts, new_dt, new_loc, new_pres, next_turn, vitals_snapshot
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
