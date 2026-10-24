"""Caso de uso `commit`: grava as consequências do turno no EventStore e projeta o SSOT."""

import re
import shutil
from pathlib import Path

from council.helpers import atomic_write_text
from council import (
    get_campaign_overrides,
    find_campaign,
    parse_ficha_md,
    parse_diario_md,
    parse_npcs_md,
    parse_cost_string,
    apply_npc_updates_to_md,
    upsert_ficha_feature,
    check_prose_lints,
    cmd_review,
    upsert_clock_in_diario,
    parse_clocks_from_diario,
    upsert_planned_scene_in_diario,
    parse_quests_from_diario,
    upsert_quest_in_diario,
    append_xp_ledger_entry,
    update_progression_in_ficha,
)
from rulesets.progression import evaluate_xp_gain, get_base_step_from_overrides, DEFAULT_QUEST_REWARDS
from council.factions import parse_factions_from_mundo, update_reputation_in_ficha, append_faction_ledger_entry
from application.commit_events import build_commit_event_drafts
from application.commit_validation import _split_name_value, _compute_commit_datetime, validate_commit_entities
from application.transaction import (
    _serialized_campaign_mutation,
    commit_events_and_project,
    ensure_campaign_event_log,
)


def _infer_scene_type(scene_type: str, sum_low: str, applied: list[str]) -> str:
    if scene_type != "standard":
        return scene_type
    inferences = (
        (("[salto temporal]", "salto temporal", "[timeskip]"), "timeskip"),
        (("[interlúdio]", "[interludio]", "interlúdio", "interludio"), "interlude"),
        (("[cena paralela]", "cena paralela"), "parallel"),
        (("[dossiê]", "[dossie]", "dossiê", "dossie"), "dossier"),
        (("[flashback]",), "flashback"),
        (("[prólogo]", "[prologo]"), "prologue"),
        (("[epílogo]", "[epilogo]"), "epilogue"),
        (("[pós-créditos]", "[pos-creditos]"), "post_credits"),
        (("[fade to black]", "fade to black", "[fade-to-black]", "corte para preto"), "fade_to_black"),
    )
    for markers, inferred in inferences:
        if any(m in sum_low for m in markers):
            applied.append(f"Auto-inferência: scene_type inferido como '{inferred}' pelo texto.")
            return inferred
    return scene_type


@_serialized_campaign_mutation
def cmd_commit(
    campaign_id: str,
    summary: str,
    cost: str = "",
    time_str: str = "",
    location: str = "",
    present_npcs: str = "",
    npc_updates: str = "",
    state_shift: str = "",
    clock_advance: str = "",
    scene_type: str = "standard",
    time: str = "",
    add_ability: str = "",
    add_milestone: str = "",
    add_item: str = "",
    prose: str = "",
    prose_file: str = "",
    force: bool = False,
    quest_progress: str = "",
    quest_complete: str = "",
    quest_fail: str = "",
    clock_resolve: str = "",
    faction_rep: str = "",
    faction_favor: str = "",
    faction_debt: str = "",
):
    """Registra eventos causais do turno no EventStore, reconstrói projeções canônicas e roda auditoria."""
    if not time_str and time:
        time_str = time
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha Markdown '{campaign_id}' não encontrada."}

    validation_errors = validate_commit_entities(
        info,
        clock_advance=clock_advance,
        clock_resolve=clock_resolve,
        quest_progress=quest_progress,
        quest_complete=quest_complete,
        quest_fail=quest_fail,
        faction_rep=faction_rep,
        faction_favor=faction_favor,
        faction_debt=faction_debt,
    )
    if validation_errors:
        return {
            "error": "Commit recusado: entidades inexistentes no SSOT. Nenhum arquivo foi alterado.",
            "validation_errors": validation_errors,
        }

    known_factions = set()
    if info.get("mundo") and info["mundo"].exists():
        for faction in parse_factions_from_mundo(info["mundo"]):
            known_factions.add(faction["name"].strip().lower())
            known_factions.add(faction["tag"].strip().lower())

    applied: list[str] = []
    camp_dir = Path(info.get("dir") or info["ficha"].parent)
    orig_ficha_path = Path(info["ficha"])
    orig_diario_path = Path(info["diario"])
    orig_npcs_path = Path(info["npcs"])

    scene_type = _infer_scene_type(
        scene_type.lower().strip() if scene_type else "standard",
        summary.lower(),
        applied,
    )
    sum_low = summary.lower()
    ficha_data = parse_ficha_md(orig_ficha_path)

    prose_to_audit = ""
    prose_issues = []
    if prose_file:
        pf = Path(prose_file)
        if not pf.exists():
            return {"error": f"Arquivo de prosa '{prose_file}' não encontrado.", "status": "FILE_NOT_FOUND"}
        prose_to_audit = pf.read_text(encoding="utf-8")
    elif prose:
        prose_to_audit = prose

    if prose_to_audit:
        all_npcs = parse_npcs_md(orig_npcs_path) if orig_npcs_path.exists() else []
        known_speakers = set()
        if ficha_data.get("name"):
            known_speakers.add(ficha_data["name"].strip())
            for tok in re.split(r"[\s(),&_-]+", ficha_data["name"]):
                if len(tok) >= 3 and tok[0].isupper():
                    known_speakers.add(tok)
        for npc_obj in all_npcs:
            n_name = npc_obj.get("name", "").strip()
            if n_name:
                known_speakers.add(n_name)
                for tok in re.split(r"[\s(),&_-]+", n_name):
                    if len(tok) >= 3 and tok[0].isupper():
                        known_speakers.add(tok)

        prose_issues = check_prose_lints(prose_to_audit, context_label=prose_file or "--prose", known_speakers=known_speakers)
        high_issues = [i for i in prose_issues if i.get("severity") in ("HIGH", "CRITICAL")]
        if high_issues and not force:
            return {
                "error": "Commit recusado: a prosa entregue viola regras duras de estilo literário (SCRIPT_FORMAT_DETECTED). Use --force para ignorar.",
                "prose_status": "REJECTED",
                "issues": prose_issues,
            }

    deltas, time_advance_mins = parse_cost_string(cost, ficha_data["vitals"])
    diario_ctx_for_time = parse_diario_md(orig_diario_path)
    try:
        precomputed_new_dt = _compute_commit_datetime(
            diario_ctx_for_time["date_time"],
            time_str,
            time_advance_mins,
            info.get("calendar"),
        )
    except ValueError as exc:
        return {
            "error": f"Commit recusado: {exc}",
            "validation_errors": [str(exc)],
        }

    # Inicializa/sincroniza o EventStore antes de encenar as mutações do turno
    store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)

    stage_dir = camp_dir / ".staging"
    stage_dir.mkdir(parents=True, exist_ok=True)
    ficha_path = stage_dir / "ficha.md"
    diario_path = stage_dir / "diario.md"
    npcs_path = stage_dir / "npcs.md"

    try:
        for src, dst in ((orig_ficha_path, ficha_path), (orig_diario_path, diario_path), (orig_npcs_path, npcs_path)):
            if src.exists():
                dst.write_bytes(src.read_bytes())

        clock_events: list[dict] = []
        quest_events: list[dict] = []
        xp_events: list[dict] = []
        faction_events: list[dict] = []
        scene_completed_idx: int | None = None

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
            for key, v in ficha_data["vitals"].items():
                if v["max"] > 0 and v["current"] < v["max"]:
                    pattern = rf"(\*\s*\*\*{re.escape(v['label'])}:\*\*\s*)\d+(\s*/\s*{v['max']})"
                    ficha_text = re.sub(pattern, rf"\g<1>{v['max']}\g<2>", ficha_text)
                    restored.append(f"{v['label']}: {v['max']}/{v['max']} (pleno descanso)")
            if restored:
                atomic_write_text(ficha_path, ficha_text)
                applied.extend(restored)

        if add_ability or add_milestone or add_item:
            feat_applied = upsert_ficha_feature(ficha_path, ability=add_ability, milestone=add_milestone, item=add_item)
            applied.extend(feat_applied)

        if npc_updates:
            npc_changes = apply_npc_updates_to_md(npcs_path, npc_updates)
            applied.extend(npc_changes)
        else:
            diario_check = parse_diario_md(diario_path)
            pres_str = present_npcs or diario_check.get("present", "")
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
            cur_clocks = parse_clocks_from_diario(diario_path)
            for c in cur_clocks:
                if c["status"] == "ACTIVE":
                    c_tokens = [tok.lower() for tok in re.split(r"[\s:,&()-]+", c["name"] + " " + c.get("trigger", "")) if len(tok) >= 4]
                    matches = sum(1 for tok in c_tokens if tok in sum_low)
                    if matches >= 2:
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
            all_active_quests = parse_quests_from_diario(diario_path)
            linked_clock_names = {q["clock"].strip().lower() for q in all_active_quests if q.get("clock")}
            for c_name in resolved_clocks:
                if c_name.strip().lower() not in linked_clock_names:
                    clock_xp = evaluate_xp_gain("clock_resolved", overrides=camp_overrides)
                    prog_res = update_progression_in_ficha(ficha_path, xp_add=clock_xp, base_step=base_step)
                    append_xp_ledger_entry(diario_path, clock_xp, reason=f"Relógio '{c_name}' resolvido", turn=next_turn)
                    xp_events.append({"xp_delta": clock_xp, "xp_total": prog_res["new_xp"], "level": prog_res["new_level"], "source": f"Relógio '{c_name}' resolvido"})
                    applied.append(f"Relógio Resolvido: '{c_name}' concluído com sucesso (+{clock_xp} XP concedido).")
                    if prog_res.get("level_up"):
                        applied.append(f"EVOLUÇÃO DE NÍVEL: O protagonista atingiu o Nível {prog_res['new_level']}! (+{prog_res['bonuses']['attribute_points']} Ponto(s) de Atributo, vitais expandidos).")

        if quest_progress and diario_path.exists():
            for item in quest_progress.split("|"):
                parts = item.split(":")
                qid = parts[0].strip().upper()
                idx = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 1
                ups_res = upsert_quest_in_diario(diario_path, "check", quest_id=qid, check_index=idx, current_turn=next_turn)
                if ups_res.get("action") == "objective_checked":
                    all_q = parse_quests_from_diario(diario_path)
                    q_match = next((q for q in all_q if q["id"].upper() == qid), None)
                    code = "obj_main" if (q_match and q_match.get("type") == "MAIN") else "obj_side"
                    xp_gain = evaluate_xp_gain(code, overrides=camp_overrides)
                    prog_res = update_progression_in_ficha(ficha_path, xp_add=xp_gain, base_step=base_step)
                    append_xp_ledger_entry(diario_path, xp_gain, reason=f"Objetivo {qid}:{idx} concluído", turn=next_turn)
                    quest_events.append({"type": "quest.objective_completed", "payload": {"id": qid, "objective_idx": idx, "xp_awarded": xp_gain}})
                    xp_events.append({"xp_delta": xp_gain, "xp_total": prog_res["new_xp"], "level": prog_res["new_level"], "source": f"Objetivo {qid}:{idx} concluído"})
                    applied.append(f"Progresso de Missão: Objetivo {qid}:{idx} marcado como concluído (+{xp_gain} XP).")
                    if prog_res.get("level_up"):
                        applied.append(f"EVOLUÇÃO DE NÍVEL: O protagonista atingiu o Nível {prog_res['new_level']}! (+{prog_res['bonuses']['attribute_points']} Ponto(s) de Atributo, vitais expandidos).")

        duplicate_quest_attempts = []
        if quest_complete and diario_path.exists():
            for qid in quest_complete.split("|"):
                qid = qid.strip().upper()
                all_q = parse_quests_from_diario(diario_path)
                q_match = next((q for q in all_q if q["id"].upper() == qid), None)
                if q_match:
                    if q_match.get("xp_paid") is not None and q_match.get("xp_paid") > 0:
                        applied.append(f"Aviso de Idempotência: Missão '{q_match['title']}' ({qid}) já teve recompensa de XP concedida ({q_match['xp_paid']} XP).")
                        applied.append(f"ALERTA_CRITICO: Tentativa de pagamento duplicado de XP barrada para missão '{q_match['title']}' ({qid}).")
                        duplicate_quest_attempts.append(q_match)
                        upsert_quest_in_diario(diario_path, "complete", quest_id=qid, current_turn=next_turn)
                    elif q_match.get("status") == "COMPLETED":
                        applied.append(f"Aviso de Idempotência: Missão '{q_match['title']}' ({qid}) já está COMPLETED; XP não concedido novamente. Use 'quest --reopen' antes de concluir outra vez.")
                    else:
                        reward_xp = q_match.get("reward_xp") or DEFAULT_QUEST_REWARDS.get(q_match.get("type", "MAIN").upper(), 150)
                        upsert_quest_in_diario(diario_path, "complete", quest_id=qid, xp_paid=reward_xp, current_turn=next_turn)
                        prog_res = update_progression_in_ficha(ficha_path, xp_add=reward_xp, base_step=base_step)
                        quest_events.append({"type": "quest.completed", "payload": {"id": qid, "xp_awarded": reward_xp}})
                        xp_events.append({"xp_delta": reward_xp, "xp_total": prog_res["new_xp"], "level": prog_res["new_level"], "source": f"Missão '{q_match['title']}' ({qid}) concluída"})
                        applied.append(f"Missão Concluída: '{q_match['title']}' ({qid}) finalizada com sucesso (+{reward_xp} XP concedido).")
                        if prog_res.get("level_up"):
                            applied.append(f"EVOLUÇÃO DE NÍVEL: O protagonista atingiu o Nível {prog_res['new_level']}! (+{prog_res['bonuses']['attribute_points']} Ponto(s) de Atributo, vitais expandidos).")

                        contractor = (q_match.get("contractor") or "").strip()
                        if contractor and contractor.lower() not in known_factions:
                            applied.append(f"Contrato Cumprido: facção contratante '{contractor}' não está cadastrada em mundo.md; reputação e favores não foram alterados.")
                        elif contractor:
                            f_res = update_reputation_in_ficha(ficha_path, contractor, score_delta=1, favors_delta=1)
                            reason_txt = f"Cumprimento de missão contratada ({qid})"
                            append_faction_ledger_entry(diario_path, contractor, delta_rep=1, new_score=f_res["new_score"], reason=reason_txt, turn=next_turn, delta_favors=1, quest_id=qid)
                            faction_events.append({"faction": contractor, "delta_rep": 1, "new_score": f_res["new_score"], "delta_favors": 1, "delta_debts": 0, "reason": reason_txt})
                            applied.append(f"Contrato Cumprido: Reputação com '{contractor}' +1 -> {f_res['new_score']} [{f_res['new_tier']}], Favores +1.")

        if quest_fail and diario_path.exists():
            for item in quest_fail.split("|"):
                parts = item.split(":")
                qid = parts[0].strip().upper()
                reason_text = parts[1].strip() if len(parts) > 1 else ""
                all_q_before = parse_quests_from_diario(diario_path)
                q_match = next((q for q in all_q_before if q["id"].upper() == qid), None)
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
                        faction_events.append({"faction": contractor, "delta_rep": -1, "new_score": f_res["new_score"], "delta_favors": 0, "delta_debts": 1, "reason": reason_txt})
                        applied.append(f"Contrato Fracassado: Reputação com '{contractor}' -1 -> {f_res['new_score']} [{f_res['new_tier']}], Débitos +1.")

        if faction_rep and ficha_path.exists():
            for item in faction_rep.split("|"):
                parts = item.split(":")
                fn = parts[0].strip()
                delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(("-", "+")) and parts[1].strip()[1:].isdigit())) else 1
                f_res = update_reputation_in_ficha(ficha_path, fn, score_delta=delta)
                append_faction_ledger_entry(diario_path, fn, delta_rep=delta, new_score=f_res["new_score"], reason="Ajuste de reputação no commit", turn=next_turn)
                faction_events.append({"faction": fn, "delta_rep": delta, "new_score": f_res["new_score"], "delta_favors": 0, "delta_debts": 0, "reason": "Ajuste de reputação no commit"})
                applied.append(f"Reputação com '{fn}': {delta:+d} -> {f_res['new_score']} [{f_res['new_tier']}].")

        if faction_favor and ficha_path.exists():
            for item in faction_favor.split("|"):
                parts = item.split(":")
                fn = parts[0].strip()
                delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(("-", "+")) and parts[1].strip()[1:].isdigit())) else 1
                f_res = update_reputation_in_ficha(ficha_path, fn, favors_delta=delta)
                append_faction_ledger_entry(diario_path, fn, delta_rep=0, new_score=f_res["new_score"], reason="Ajuste de favores no commit", turn=next_turn, delta_favors=delta)
                faction_events.append({"faction": fn, "delta_rep": 0, "new_score": f_res["new_score"], "delta_favors": delta, "delta_debts": 0, "reason": "Ajuste de favores no commit"})
                applied.append(f"Favores com '{fn}': {delta:+d} -> {f_res['favors']}.")

        if faction_debt and ficha_path.exists():
            for item in faction_debt.split("|"):
                parts = item.split(":")
                fn = parts[0].strip()
                delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(("-", "+")) and parts[1].strip()[1:].isdigit())) else 1
                f_res = update_reputation_in_ficha(ficha_path, fn, debts_delta=delta)
                append_faction_ledger_entry(diario_path, fn, delta_rep=0, new_score=f_res["new_score"], reason="Ajuste de débitos no commit", turn=next_turn, delta_debts=delta)
                faction_events.append({"faction": fn, "delta_rep": 0, "new_score": f_res["new_score"], "delta_favors": 0, "delta_debts": delta, "reason": "Ajuste de débitos no commit"})
                applied.append(f"Débitos com '{fn}': {delta:+d} -> {f_res['debts']}.")

        plan_data = diario_ctx.get("plot_plan", {})
        next_sc = plan_data.get("next_scene")
        if next_sc and not next_sc.get("done"):
            sc_type_match = next_sc["scene_type"].lower() == scene_type.lower()
            actors_match = any(act.strip().lower() in sum_low for act in re.split(r"[\s,]+", next_sc.get("actors", "")) if len(act.strip()) > 3) if next_sc.get("actors") else False
            if sc_type_match or actors_match:
                upsert_planned_scene_in_diario(diario_path, mark_done_idx=0)
                scene_completed_idx = 0
                applied.append(f"Fila de Trama: Cena agendada [{next_sc['scene_type']}] concluída e marcada como [x].")

        ficha_after = parse_ficha_md(ficha_path)
        vitals_snapshot = ", ".join(
            f"{v['label'].split('(')[0].strip()} {v['current']}/{v['max']}"
            for v in ficha_after["vitals"].values()
        )
        vitals_after_dict = {k: v["current"] for k, v in ficha_after["vitals"].items()} if ficha_after.get("vitals") else {}

        new_dt = precomputed_new_dt
        new_loc = location.strip() if location else diario_ctx["location"]
        new_pres = present_npcs.strip() if present_npcs else diario_ctx["present"]

        if diario_path.exists():
            diario_text = diario_path.read_text(encoding="utf-8").rstrip()
            if new_dt != diario_ctx["date_time"] or new_loc != diario_ctx["location"]:
                diario_text = re.sub(
                    r"(\*\s*\*\*Data\s*&\s*Local:\*\*\s*)[^\n]+",
                    rf"\g<1>{new_dt} — {new_loc}.",
                    diario_text,
                    count=1,
                )
                if new_dt != diario_ctx["date_time"]:
                    applied.append(f"Relógio atualizado -> {new_dt}")
                if new_loc != diario_ctx["location"]:
                    applied.append(f"Local atualizado -> {new_loc}")

            if new_pres != diario_ctx["present"]:
                diario_text = re.sub(
                    r"(\*\s*\*\*Presentes:\*\*\s*)[^\n]+",
                    rf"\g<1>{new_pres}.",
                    diario_text,
                    count=1,
                )
                applied.append(f"Presentes atualizados -> {new_pres}")

            scene_tags = {
                "interlude": "[INTERLÚDIO] ",
                "parallel": "[CENA PARALELA] ",
                "timeskip": "[SALTO TEMPORAL] ",
                "dossier": "[DOSSIÊ] ",
                "flashback": "[FLASHBACK] ",
                "prologue": "[PRÓLOGO] ",
                "epilogue": "[EPÍLOGO] ",
                "post_credits": "[PÓS-CRÉDITOS] ",
                "fade_to_black": "[FADE TO BLACK] ",
            }
            tag_prefix = scene_tags.get(scene_type, "")

            clean_summary = re.sub(r"\s*Vitais:\s*[^\n]+$", "", summary.strip()).rstrip(".")
            turn_entry = f"\n* **Turno {next_turn} {tag_prefix.strip()}:** {clean_summary}. Vitais: {vitals_snapshot}.\n" if tag_prefix else f"\n* **Turno {next_turn}:** {clean_summary}. Vitais: {vitals_snapshot}.\n"
            if state_shift.strip():
                clean_shift = state_shift.strip().rstrip(".")
                turn_entry += f"  * **Mudança de Estado:** {clean_shift}.\n"
                applied.append(f"Mudança de Estado registrada: '{clean_shift}'")
            for dup in duplicate_quest_attempts:
                turn_entry += f"  * **Alerta:** Tentativa de pagamento duplicado de XP barrada para missão '{dup['title']}' ({dup['id']}).\n"
            atomic_write_text(diario_path, diario_text + turn_entry)
            applied.append(f"Diário atualizado: Turno {next_turn} registrado.")

        drafts = build_commit_event_drafts(
            camp_dir=camp_dir,
            next_turn=next_turn,
            summary=summary,
            scene_type=scene_type,
            new_dt=new_dt,
            new_loc=new_loc,
            new_pres=new_pres,
            calendar_cfg=info.get("calendar"),
            prev_event_id=prev_event_id,
            deltas=deltas,
            add_ability=add_ability,
            add_milestone=add_milestone,
            add_item=add_item,
            npc_updates=npc_updates,
            clock_events=clock_events,
            quest_events=quest_events,
            xp_events=xp_events,
            faction_events=faction_events,
            scene_completed_idx=scene_completed_idx,
            raw_prose=prose_to_audit or prose,
            ficha_after_path=ficha_path,
            diario_after_path=diario_path,
            npcs_after_path=npcs_path,
            vitals_after=vitals_after_dict,
        )
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)

    # Grava eventos no EventStore PRIMEIRO e materializa projeções + raiz atomicamente
    commit_events_and_project(camp_dir, campaign_id, drafts, store, expected_last_seq)

    # Auditoria Automática Pós-Commit (Modo Revisor)
    post_audit = cmd_review(campaign_id)
    final_header = f" [{new_dt}] |  [{new_loc}] |  [{new_pres}]"
    commit_res = {
        "status": "ok",
        "turn_committed": next_turn,
        "canonical_header_for_response": final_header,
        "vitals_now": vitals_snapshot,
        "updates": applied,
        "post_commit_audit": {
            "ssot_status": post_audit["ssot_status"],
            "issues": post_audit["issues"],
        },
    }
    if prose_to_audit:
        commit_res["prose_status"] = "PASSED"
        if prose_issues:
            commit_res["prose_issues"] = prose_issues
    return commit_res
