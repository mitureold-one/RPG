"""Caso de uso `commit`: grava as consequências do turno no SSOT da campanha."""

import re
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
from application.transaction import _serialized_campaign_mutation
from application.commit_validation import _split_name_value, _compute_commit_datetime, validate_commit_entities


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
    """Atualiza ficha.md, diario.md e npcs.md atomicamente no fim do turno e roda a auditoria automática do Modo Revisor."""
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

    applied = []
    ficha_path = info["ficha"]
    diario_path = info["diario"]
    npcs_path = info["npcs"]
    scene_type = scene_type.lower().strip() if scene_type else "standard"
    sum_low = summary.lower()

    # 0. Auto-inferência de scene_type se o modelo omitir a flag no commit
    if scene_type == "standard":
        if "[salto temporal]" in sum_low or "salto temporal" in sum_low or "[timeskip]" in sum_low:
            scene_type = "timeskip"
            applied.append("Auto-inferência: scene_type inferido como 'timeskip' pelo texto.")
        elif "[interlúdio]" in sum_low or "[interludio]" in sum_low or "interlúdio" in sum_low or "interludio" in sum_low:
            scene_type = "interlude"
            applied.append("Auto-inferência: scene_type inferido como 'interlude' pelo texto.")
        elif "[cena paralela]" in sum_low or "cena paralela" in sum_low:
            scene_type = "parallel"
            applied.append("Auto-inferência: scene_type inferido como 'parallel' pelo texto.")
        elif "[dossiê]" in sum_low or "[dossie]" in sum_low or "dossiê" in sum_low or "dossie" in sum_low:
            scene_type = "dossier"
            applied.append("Auto-inferência: scene_type inferido como 'dossier' pelo texto.")
        elif "[flashback]" in sum_low:
            scene_type = "flashback"
            applied.append("Auto-inferência: scene_type inferido como 'flashback' pelo texto.")
        elif "[prólogo]" in sum_low or "[prologo]" in sum_low:
            scene_type = "prologue"
            applied.append("Auto-inferência: scene_type inferido como 'prologue' pelo texto.")
        elif "[epílogo]" in sum_low or "[epilogo]" in sum_low:
            scene_type = "epilogue"
            applied.append("Auto-inferência: scene_type inferido como 'epilogue' pelo texto.")
        elif "[pós-créditos]" in sum_low or "[pos-creditos]" in sum_low:
            scene_type = "post_credits"
            applied.append("Auto-inferência: scene_type inferido como 'post_credits' pelo texto.")
        elif "[fade to black]" in sum_low or "fade to black" in sum_low or "[fade-to-black]" in sum_low or "corte para preto" in sum_low:
            scene_type = "fade_to_black"
            applied.append("Auto-inferência: scene_type inferido como 'fade_to_black' pelo texto.")

    # 1. Atualiza ficha.md dinamicamente para qualquer recurso vital cadastrado
    ficha_data = parse_ficha_md(ficha_path)

    # 0a. Auditoria preventiva da prosa se fornecida (--prose ou --prose-file)
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
        all_npcs = parse_npcs_md(npcs_path) if npcs_path.exists() else []
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

    # Valida e resolve o tempo antes de qualquer escrita. Um calendário
    # desconhecido deve falhar alto, não deixar o SSOT parcialmente alterado.
    diario_ctx_for_time = parse_diario_md(diario_path)
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
        # Restauração automática de vitais em Timeskips prolongados (sem custo explícito de dano)
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

    # 2. Atualiza npcs.md com separação estrita por NPC (Integridade Referencial)
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

    # 3. Avança relógios de facções ou prazos especificados em --clock-advance ou auto-detectados
    resolved_clocks = []
    if clock_resolve and diario_path.exists():
        for item in clock_resolve.split("|"):
            c_name = item.strip()
            if c_name:
                ups_res = upsert_clock_in_diario(diario_path, c_name, status="RESOLVED", create_if_missing=False)
                applied.append(f"Relógio '{c_name}' resolvido via commit [{ups_res.get('status')}].")
                resolved_clocks.append(c_name)
    if clock_advance and diario_path.exists():
        for item in clock_advance.split("|"):
            c_name, c_steps_raw = _split_name_value(item)
            c_steps = int(c_steps_raw) if c_steps_raw.isdigit() else 1
            ups_res = upsert_clock_in_diario(diario_path, c_name, advance=c_steps, create_if_missing=False)
            applied.append(f"Relógio '{c_name}' avançado em +{c_steps} -> {ups_res.get('current', '?')}/{ups_res.get('max', '?')} [{ups_res.get('status', 'ACTIVE')}].")
            if ups_res.get("status") == "RESOLVED":
                resolved_clocks.append(c_name)
    elif diario_path.exists():
        cur_clocks = parse_clocks_from_diario(diario_path)
        for c in cur_clocks:
            if c["status"] == "ACTIVE":
                c_tokens = [tok.lower() for tok in re.split(r"[\s:,&()-]+", c["name"] + " " + c.get("trigger", "")) if len(tok) >= 4]
                matches = sum(1 for tok in c_tokens if tok in sum_low)
                if matches >= 2:
                    ups_res = upsert_clock_in_diario(diario_path, c["name"], advance=1, create_if_missing=False)
                    applied.append(f"Auto-avanço: Relógio '{c['name']}' avançado em +1 ({ups_res.get('current')}/{ups_res.get('max')} [{ups_res.get('status')}]).")
                    if ups_res.get("status") == "RESOLVED":
                        resolved_clocks.append(c["name"])

    # 4a. Determina o número do próximo turno antes do processamento de missões e XP (P0-1)
    diario_ctx = parse_diario_md(diario_path)
    next_turn = diario_ctx["last_turn_num"] + 1

    camp_overrides = get_campaign_overrides(campaign_id)
    base_step = get_base_step_from_overrides(camp_overrides)

    # Concede XP para relógios de ameaça resolvidos não vinculados a missões ativas (T014)
    if resolved_clocks:
        all_active_quests = parse_quests_from_diario(diario_path)
        linked_clock_names = {q["clock"].strip().lower() for q in all_active_quests if q.get("clock")}
        for c_name in resolved_clocks:
            if c_name.strip().lower() not in linked_clock_names:
                clock_xp = evaluate_xp_gain("clock_resolved", overrides=camp_overrides)
                prog_res = update_progression_in_ficha(ficha_path, xp_add=clock_xp, base_step=base_step)
                append_xp_ledger_entry(diario_path, clock_xp, reason=f"Relógio '{c_name}' resolvido", turn=next_turn)
                applied.append(f"Relógio Resolvido: '{c_name}' concluído com sucesso (+{clock_xp} XP concedido).")
                if prog_res.get("level_up"):
                    applied.append(f"EVOLUÇÃO DE NÍVEL: O protagonista atingiu o Nível {prog_res['new_level']}! (+{prog_res['bonuses']['attribute_points']} Ponto(s) de Atributo, vitais expandidos).")

    # 3b. Atualiza Missões & Concessão de XP (--quest-progress, --quest-complete, --quest-fail)
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
                    applied.append(
                        f"Aviso de Idempotência: Missão '{q_match['title']}' ({qid}) já está COMPLETED; "
                        f"XP não concedido novamente. Use 'quest --reopen' antes de concluir outra vez."
                    )
                else:
                    reward_xp = q_match.get("reward_xp") or DEFAULT_QUEST_REWARDS.get(q_match.get("type", "MAIN").upper(), 150)
                    upsert_quest_in_diario(diario_path, "complete", quest_id=qid, xp_paid=reward_xp, current_turn=next_turn)
                    prog_res = update_progression_in_ficha(ficha_path, xp_add=reward_xp, base_step=base_step)
                    applied.append(f"Missão Concluída: '{q_match['title']}' ({qid}) finalizada com sucesso (+{reward_xp} XP concedido).")
                    if prog_res.get("level_up"):
                        applied.append(f"EVOLUÇÃO DE NÍVEL: O protagonista atingiu o Nível {prog_res['new_level']}! (+{prog_res['bonuses']['attribute_points']} Ponto(s) de Atributo, vitais expandidos).")

                    # Repercussão diplomática automática com a facção contratante
                    contractor = (q_match.get("contractor") or "").strip()
                    if contractor and contractor.lower() not in known_factions:
                        applied.append(
                            f"Contrato Cumprido: facção contratante '{contractor}' não está cadastrada em mundo.md; "
                            f"reputação e favores não foram alterados."
                        )
                    elif contractor:
                        f_res = update_reputation_in_ficha(ficha_path, contractor, score_delta=1, favors_delta=1)
                        append_faction_ledger_entry(
                            diario_path,
                            contractor,
                            delta_rep=1,
                            new_score=f_res["new_score"],
                            reason=f"Cumprimento de missão contratada ({qid})",
                            turn=next_turn,
                            delta_favors=1,
                            quest_id=qid,
                        )
                        applied.append(f"Contrato Cumprido: Reputação com '{contractor}' +1 -> {f_res['new_score']} [{f_res['new_tier']}], Favores +1.")

    if quest_fail and diario_path.exists():
        for item in quest_fail.split("|"):
            parts = item.split(":")
            qid = parts[0].strip().upper()
            reason_text = parts[1].strip() if len(parts) > 1 else ""
            all_q_before = parse_quests_from_diario(diario_path)
            q_match = next((q for q in all_q_before if q["id"].upper() == qid), None)
            upsert_quest_in_diario(diario_path, "fail", quest_id=qid, reason=reason_text, current_turn=next_turn)
            applied.append(f"Missão Fracassada: '{qid}' encerrada com status FAILED ({reason_text or 'Sem justificativa'}).")
            if q_match and q_match.get("contractor"):
                contractor = q_match["contractor"].strip()
                if contractor and contractor.lower() not in known_factions:
                    applied.append(
                        f"Contrato Fracassado: facção contratante '{contractor}' não está cadastrada em mundo.md; "
                        f"reputação e débitos não foram alterados."
                    )
                elif contractor:
                    f_res = update_reputation_in_ficha(ficha_path, contractor, score_delta=-1, debts_delta=1)
                    append_faction_ledger_entry(
                        diario_path,
                        contractor,
                        delta_rep=-1,
                        new_score=f_res["new_score"],
                        reason=f"Fracasso de missão contratada ({qid}): {reason_text or 'Falha de execução'}",
                        turn=next_turn,
                        delta_debts=1,
                        quest_id=qid,
                    )
                    applied.append(f"Contrato Fracassado: Reputação com '{contractor}' -1 -> {f_res['new_score']} [{f_res['new_tier']}], Débitos +1.")

    # 3c. Atualizações Manuais de Facções & Reputação (--faction-rep, --faction-favor, --faction-debt)
    if faction_rep and ficha_path.exists():
        for item in faction_rep.split("|"):
            parts = item.split(":")
            fn = parts[0].strip()
            delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(('-', '+')) and parts[1].strip()[1:].isdigit())) else 1
            f_res = update_reputation_in_ficha(ficha_path, fn, score_delta=delta)
            append_faction_ledger_entry(diario_path, fn, delta_rep=delta, new_score=f_res["new_score"], reason="Ajuste de reputação no commit", turn=next_turn)
            applied.append(f"Reputação com '{fn}': {delta:+d} -> {f_res['new_score']} [{f_res['new_tier']}].")

    if faction_favor and ficha_path.exists():
        for item in faction_favor.split("|"):
            parts = item.split(":")
            fn = parts[0].strip()
            delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(('-', '+')) and parts[1].strip()[1:].isdigit())) else 1
            f_res = update_reputation_in_ficha(ficha_path, fn, favors_delta=delta)
            append_faction_ledger_entry(diario_path, fn, delta_rep=0, new_score=f_res["new_score"], reason="Ajuste de favores no commit", turn=next_turn, delta_favors=delta)
            applied.append(f"Favores com '{fn}': {delta:+d} -> {f_res['favors']}.")

    if faction_debt and ficha_path.exists():
        for item in faction_debt.split("|"):
            parts = item.split(":")
            fn = parts[0].strip()
            delta = int(parts[1].strip()) if len(parts) > 1 and (parts[1].strip().isdigit() or (parts[1].strip().startswith(('-', '+')) and parts[1].strip()[1:].isdigit())) else 1
            f_res = update_reputation_in_ficha(ficha_path, fn, debts_delta=delta)
            append_faction_ledger_entry(diario_path, fn, delta_rep=0, new_score=f_res["new_score"], reason="Ajuste de débitos no commit", turn=next_turn, delta_debts=delta)
            applied.append(f"Débitos com '{fn}': {delta:+d} -> {f_res['debts']}.")

    # 4b. Atualiza diario.md (Data/Hora, Local, Presentes, Mudança de Estado e anexa Turno N)

    # Auto-baixa de cena agendada caso executada
    plan_data = diario_ctx.get("plot_plan", {})
    next_sc = plan_data.get("next_scene")
    if next_sc and not next_sc.get("done"):
        sc_type_match = next_sc["scene_type"].lower() == scene_type.lower()
        actors_match = any(act.strip().lower() in sum_low for act in re.split(r"[\s,]+", next_sc.get("actors", "")) if len(act.strip()) > 3) if next_sc.get("actors") else False
        if sc_type_match or actors_match:
            upsert_planned_scene_in_diario(diario_path, mark_done_idx=0)
            applied.append(f"Fila de Trama: Cena agendada [{next_sc['scene_type']}] concluída e marcada como [x].")
    ficha_after = parse_ficha_md(ficha_path)
    vitals_snapshot = ", ".join(
        f"{v['label'].split('(')[0].strip()} {v['current']}/{v['max']}"
        for v in ficha_after["vitals"].values()
    )

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

        # Prefixo de tipo de cena caso não seja padrão
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

    # 4c. Persistência Causal & Projeções Determinísticas (Fase 02 / R1)
    camp_dir = info.get("dir") or info.get("ficha").parent
    if (camp_dir / "events").exists():
        try:
            from adapters.persistence.event_store import JsonlEventStore
            from application.prose_store import ProseStore
            from contracts.event import ActorRef, EventDraft
            from application.rebuild import rebuild_projections

            drafts = []
            turn_draft = EventDraft(
                type="turn.proposed",
                schema_version=1,
                actor=ActorRef(kind="agent", id="narrative_engine"),
                game_time=new_dt,
                game_time_sort=next_turn * 100,
                payload={"turn": next_turn, "action": summary.strip(), "summary": summary.strip()},
            )
            drafts.append(turn_draft)

            raw_prose = prose_to_audit or prose
            if raw_prose:
                p_store = ProseStore(camp_dir)
                rel_p, p_hash, p_len = p_store.store_turn_prose(next_turn, raw_prose, scene_type=scene_type)
                drafts.append(
                    EventDraft(
                        type="prose.recorded",
                        schema_version=1,
                        actor=ActorRef(kind="agent", id="narrative_engine"),
                        game_time=new_dt,
                        game_time_sort=next_turn * 100 + 1,
                        payload={
                            "turn": next_turn,
                            "text_hash": p_hash,
                            "text_path": rel_p,
                            "source": "writer_mode",
                            "bytes": p_len,
                            "scene_type": scene_type,
                        },
                    )
                )

            drafts.append(
                EventDraft(
                    type="turn.committed",
                    schema_version=1,
                    actor=ActorRef(kind="agent", id="narrative_engine"),
                    game_time=new_dt,
                    game_time_sort=next_turn * 100 + 2,
                    payload={
                        "turn": next_turn,
                        "summary": summary.strip(),
                        "scene_type": scene_type,
                        "location": new_loc,
                        "present": [p.strip() for p in new_pres.split(",") if p.strip()],
                        "vitals": {k: v["current"] for k, v in ficha_after["vitals"].items()} if ficha_after.get("vitals") else {},
                    },
                )
            )

            store = JsonlEventStore(camp_dir)
            store.append(campaign_id, drafts)
            rebuild_projections(store, campaign_id, camp_dir, emit_audit_event=False)
        except Exception:
            pass

    # 5. Fase 5 do Conselho: Auditoria Automática Pós-Commit (Modo Revisor)
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
