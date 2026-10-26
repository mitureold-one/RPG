"""Caso de uso `prepare`: monta o contexto e o mandato do turno."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from council import (
    CAMPAIGN_DIRS,
    DEFAULT_RULESET,
    load_ruleset,
    get_campaign_overrides,
    find_campaign,
    parse_ficha_md,
    parse_diario_md,
    parse_npcs_md,
    derive_npc_initiative,
    find_scene_relational_tensions,
    query_aimemory,
    extract_turns_from_diario,
    cmd_review,
    extract_epistemic_forbidden_terms,
    derive_situational_scene_structures,
    MODE_PROSE_MANDATES,
    STRUCTURAL_SCENE_MANDATES,
    parse_quests_from_diario,
    parse_progression_from_ficha,
)
from council.factions import resolve_scene_factions
from application.arbitration import resolve_arbitration
from application.context.assembler import ContextAssembler, turn_context_to_payload
from application.context.providers import default_context_providers
from application.context.scene import (
    build_commit_hint,
    build_npc_dynamics,
    build_progression_data,
    build_quest_context,
    build_writer_mandates,
    resolve_scene_actors,
    resolve_scheduled_scene,
)
from application.context.state import ContextStateViewImpl
from application.showrunner import cmd_plan
from contracts.context import ContextRequest, ContextScene
from contracts.ports import create_event_store
from resources.context.policy import resolve_mode_policy


def cmd_prepare(
    campaign_id: str,
    action: str,
    variant: str = "normal",
    dc: int = 15,
    stat: str = "",
    force_roll: bool = False,
    no_roll: bool = False,
    mode: str = "gm",
    turns_spec: str = "",
    stakes: str = "normal",
    critical: bool = False,
    scene_type: str = "standard",
    actors: str = "",
    focus: str = "",
    contest_npc: str = "",
    vs_npc: str = "",
    npc_stat: str = "",
    vs_stat: str = "",
    npc_variant: str = "normal",
    vs_variant: str = "normal",
    audience: str = "",
):
    """Prepara o contexto completo do turno por relevância causal e mecânica agnóstica."""
    mode = mode.lower().strip()
    scene_type = scene_type.lower().strip() if scene_type else "standard"
    if mode not in MODE_PROSE_MANDATES:
        mode = "gm"

    if mode == "reviewer":
        return cmd_review(campaign_id)
    if mode == "director":
        return cmd_plan(campaign_id, list_plan=True)

    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada em {CAMPAIGN_DIRS}."}

    system_name = info.get("system", DEFAULT_RULESET)
    ruleset = load_ruleset(system_name)

    ficha = parse_ficha_md(info["ficha"])
    diario = parse_diario_md(info["diario"])
    all_npcs = parse_npcs_md(info["npcs"])

    plot_plan = diario.get("plot_plan", {})
    next_sched = plot_plan.get("next_scene")
    consec_std = diario.get("consecutive_standard_turns", 0)

    scheduled_info = resolve_scheduled_scene(scene_type, next_sched, actors, action)

    scene_present, scene_npcs, focal_npcs, background_npcs = resolve_scene_actors(
        action, actors, focus, diario, all_npcs
    )

    situational_pacing = derive_situational_scene_structures(
        action=action,
        last_turn_summary=diario.get("last_turn_summary", ""),
        recent_shifts=diario.get("recent_state_shifts", []),
        clocks=diario.get("clocks", []),
        consecutive_standard=consec_std,
        focal_npcs=focal_npcs,
    )

    background_cast = [f"{n['name']} ({n.get('attitude') or 'Presente'})" for n in background_npcs]

    header = f"[{diario['date_time']}] | [{diario['location']}] | [{scene_present}]"
    memories = query_aimemory(campaign_id, action[:60])
    mandate_cfg = MODE_PROSE_MANDATES[mode]
    pre_audit = cmd_review(campaign_id)

    arbitration = resolve_arbitration(
        action=action,
        ruleset=ruleset,
        ficha=ficha,
        all_npcs=all_npcs,
        scene_npcs=scene_npcs,
        focal_npcs=focal_npcs,
        scene_type=scene_type,
        mode=mode,
        variant=variant,
        dc=dc,
        stat=stat,
        force_roll=force_roll,
        no_roll=no_roll,
        contest_npc=contest_npc,
        vs_npc=vs_npc,
        npc_stat=npc_stat,
        vs_stat=vs_stat,
        npc_variant=npc_variant,
        vs_variant=vs_variant,
        stakes=stakes,
        critical=critical,
        pre_audit=pre_audit,
    )
    needs_roll = arbitration.needs_roll
    chosen_stat = arbitration.chosen_stat
    stat_val = arbitration.stat_val
    roll_data = arbitration.roll_data
    contest_data = arbitration.contest_data
    is_critical = arbitration.is_critical
    critical_reasons = list(arbitration.critical_reasons)
    cost_guide = arbitration.cost_guide
    focal_npcs = list(arbitration.focal_npcs)

    npc_dynamics_prompt = build_npc_dynamics(focal_npcs)
    scene_present_names = [p.strip().rstrip(".") for p in re.split(r",|\be\b", scene_present) if p.strip()]
    relational_tensions = find_scene_relational_tensions(scene_present_names, all_npcs, ficha.get("name", "Protagonista"))

    ficha_text = info["ficha"].read_text(encoding="utf-8") if info["ficha"].exists() else ""
    mundo_text = info["mundo"].read_text(encoding="utf-8") if (info.get("mundo") and info["mundo"].exists()) else ""
    forbidden_terms = extract_epistemic_forbidden_terms(ficha_text, mundo_text)

    clean_focal = [
        {
            "name": n["name"],
            "attitude": n.get("attitude", ""),
            "will": n.get("will", ""),
            "weakness": n.get("weakness", ""),
            "bonds": n.get("bonds", {}),
            "autonomous_initiative": derive_npc_initiative(n),
        }
        for n in focal_npcs
    ]

    next_turn_num = diario["last_turn_num"] + 1 if mandate_cfg["requires_commit"] else diario["last_turn_num"]

    mandates_by_type = STRUCTURAL_SCENE_MANDATES

    progression_data = build_progression_data(info["ficha"])
    quest_context, active_quests_summary = build_quest_context(info["diario"])
    commit_hint = build_commit_hint(
        campaign_id, focal_npcs, contest_data, roll_data, scene_type, active_quests_summary
    )

    # Inicializa pipeline de contexto determinístico da Fase 04
    camp_dir = info["ficha"].parent
    try:
        store = create_event_store(camp_dir)
    except Exception:
        store = None

    state = ContextStateViewImpl.load(
        campaign_id=campaign_id,
        campaign_dir=camp_dir,
        store=store,
        diario_data=diario,
    )

    policy = resolve_mode_policy(
        mode=mode,
        protagonist_id=ficha.get("name", "protagonist"),
        player_id="player",
        audience_override=audience,
    )
    req_scene = ContextScene(
        location=diario.get("location", ""),
        present=tuple(scene_present_names),
        game_time=diario.get("date_time", ""),
        game_time_sort=diario.get("last_turn_num", 0),
        scene_type=scene_type,
    )
    context_request = ContextRequest(
        campaign_id=campaign_id,
        mode=mode,
        action=action,
        scene=req_scene,
        viewer=policy.viewer,
        audience=policy.audience,
        purpose=policy.purpose,
        focus=tuple([f.strip() for f in focus.split() if f.strip()]) if focus else (),
    )
    providers = default_context_providers(ruleset, system_name, ficha, diario, all_npcs)
    turn_context = ContextAssembler(providers).assemble(context_request, state)

    payload = {
        "campaign": campaign_id,
        "system": system_name,
        "operation_mode": mode,
        "next_turn_number": next_turn_num,
        "canonical_header": header,
        "scene_type": scene_type,
        "stakes": stakes.lower(),
        "is_critical_turn": is_critical,
        "situational_pacing": situational_pacing,
        "scheduled_scene": scheduled_info if scheduled_info.get("has_scheduled") else None,
        "protagonist": {
            "name": ficha["name"],
            "vitals": ficha["raw_vitals_line"],
            "stats": ficha["stats"],
            "progression": progression_data,
        },
        "step_1_quest_context": quest_context,
        "step_1_faction_context": {
            "factions_in_scene": resolve_scene_factions(info, [n["name"] for n in focal_npcs], diario.get("location", "")),
        },
        "step_1_gm_arbitration": {
            "ruleset": system_name,
            "dc_ladder": getattr(ruleset, "DC_LADDER", {}),
            "overrides": get_campaign_overrides(campaign_id) or info.get("overrides", []),
            "dice_resolution": contest_data["summary"] if contest_data else (roll_data["summary"] if roll_data else "Sem rolagem de dados (Ação sem oposição mecânica direta)"),
            "cost_directive": cost_guide,
            **({"contest_resolution": contest_data, "npc_reaction_mandate": contest_data["npc_reaction_mandate"], "outcome_narrative_guidance": contest_data["outcome"]} if contest_data else {}),
        },
        "step_2_narrator_briefing": {
            "focal_npcs": clean_focal,
            "background_cast": background_cast if background_cast else [],
            **({"contest_npc_mandate": contest_data["npc_reaction_mandate"]} if contest_data else {}),
            "scene_relational_matrix": relational_tensions if relational_tensions else ["Nenhum atrito relacional prévio; postura determinada pelas Vontades Próprias."],
            "triangulation_mandate": (
                "INICIATIVA ATIVA & HIERARQUIA DE REGRAS: Pelo menos um NPC focal DEVE tomar uma iniciativa concreta no cenário (dar ordens, agir politicamente ou confrontar outro NPC) com base em sua Vontade Própria. Aplique as leis e costumes do cenário ativo (regras.md e mundo.md) filtrando rigorosamente cada atitude contra os pesos psicológicos individuais do NPC em npcs.md (Hexágono de Personalidade, Vontade e Fraquezas), garantindo voz própria, dignidade e agência ativa."
            ),
            "epistemic_barrier": {
                "forbidden_terms_for_npcs": forbidden_terms,
                "diegetic_rule": "BARREIRA DE VOCABULÁRIO DIEGÉTICO: NPCs NUNCA usam os termos proibidos acima (pertencem à origem privada do herói ou ao narrador OOC). Eles interpretam o protagonista estritamente pelos mitos e conceitos nativos do seu mundo (ex: 'aberração sem mana', 'demônio do céu', 'casulo de metal')."
            }
        },
        "step_3_writer_mandate": mandates_by_type.get(scene_type, mandates_by_type["standard"]),
        "step_4_post_turn_commit_template": {
            "command_template": commit_hint,
            "mandatory_npc_updates": [n["name"] for n in focal_npcs],
            "item_and_inventory_rule": "Se a cena concedeu, removeu ou alterou itens/armas, adicione obrigatoriamente --add-item '<Item>'.",
            "milestone_rule": "Se um marco dramático ou ponto de virada foi alcançado, adicione obrigatoriamente --add-milestone '<Marco>'."
        },
        **turn_context_to_payload(turn_context),
    }

    if memories:
        payload["ai_memory_recall"] = memories
    if mode == "writer":
        payload["source_turns"] = extract_turns_from_diario(info["diario"], turns_spec)
    return payload


__all__ = ["cmd_prepare"]
