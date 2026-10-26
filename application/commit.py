"""Caso de uso `commit`: grava as consequências do turno no EventStore e projeta o SSOT."""

import re
from pathlib import Path

from council import (
    find_campaign,
    parse_ficha_md,
    parse_diario_md,
    parse_npcs_md,
    parse_cost_string,
    check_prose_lints,
    cmd_review,
)
from council.factions import parse_factions_from_mundo
from application.commit_stage import stage_commit_mutations
from application.commit_validation import _compute_commit_datetime, validate_commit_entities
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

    store, expected_last_seq, prev_event_id = ensure_campaign_event_log(camp_dir, campaign_id)

    drafts, new_dt, new_loc, new_pres, next_turn, vitals_snapshot = stage_commit_mutations(
        campaign_id=campaign_id,
        info=info,
        camp_dir=camp_dir,
        ficha_data=ficha_data,
        summary=summary,
        sum_low=sum_low,
        scene_type=scene_type,
        deltas=deltas,
        precomputed_new_dt=precomputed_new_dt,
        location=location,
        present_npcs=present_npcs,
        npc_updates=npc_updates,
        state_shift=state_shift,
        clock_advance=clock_advance,
        clock_resolve=clock_resolve,
        quest_progress=quest_progress,
        quest_complete=quest_complete,
        quest_fail=quest_fail,
        faction_rep=faction_rep,
        faction_favor=faction_favor,
        faction_debt=faction_debt,
        add_ability=add_ability,
        add_milestone=add_milestone,
        add_item=add_item,
        raw_prose=prose_to_audit or prose,
        known_factions=known_factions,
        prev_event_id=prev_event_id,
        applied=applied,
    )

    commit_events_and_project(camp_dir, campaign_id, drafts, store, expected_last_seq)

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
