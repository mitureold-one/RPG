"""lazy_turn.py: Orquestrador Determinístico de Turno para RPG (SSOT Markdown + ai-memory).

Ponto de entrada (CLI) enxuto que delega a lógica para os módulos especializados em council/:
- council.helpers: Manipulação de tempo, constantes e localização de campanhas
- council.ssot: Ficha, diário, relógios e arcos
- council.gm: Dados (3 Portões) e custos de vitais
- council.narrator: Perfis de NPCs, psicologia e barreira epistêmica
- council.reviewer: Auditoria de SSOT, paradoxos temporais e estagnação
- council.writer: Integração com ai-memory e mandatos literários
"""

import argparse
import json
import re
import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from council import (
    CAMPAIGN_DIRS,
    TEMPLATES_DIR,
    CURRENT_SCHEMA_VERSION,
    DEFAULT_RULESET,
    load_ruleset,
    get_campaign_system,
    get_campaign_overrides,
    find_campaign,
    init_campaign_from_templates,
    parse_ficha_md,
    parse_diario_md,
    parse_npcs_md,
    upsert_npc_to_md,
    derive_npc_initiative,
    find_scene_relational_tensions,
    roll_3_gates,
    extract_npc_contest_modifier,
    roll_contest,
    query_aimemory,
    parse_time_increment,
    advance_time_str,
    parse_cost_string,
    apply_npc_updates_to_md,
    extract_turns_from_diario,
    upsert_ficha_feature,
    check_prose_lints,
    cmd_review,
    extract_epistemic_forbidden_terms,
    derive_situational_scene_structures,
    upsert_clock_in_diario,
    parse_clocks_from_diario,
    parse_plot_from_diario,
    upsert_planned_scene_in_diario,
    update_arc_in_diario,
    MODE_PROSE_MANDATES,
    STRUCTURAL_SCENE_MANDATES,
    parse_quests_from_diario,
    upsert_quest_in_diario,
    append_xp_ledger_entry,
    parse_progression_from_ficha,
    update_progression_in_ficha,
    spend_attribute_point_in_ficha,
    spend_ability_point_in_ficha,
)
from rulesets.progression import (
    evaluate_xp_gain,
    get_base_step_from_overrides,
    get_stat_ceiling_from_overrides,
    DEFAULT_QUEST_REWARDS,
)


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
):
    """Prepara o contexto completo do turno de forma 100% agnóstica de sistema/cenário, guiada pela situação avaliada pelo Mestre e pelo estado mecânico."""
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

    if scene_type == "standard" and next_sched and not actors:
        scheduled_info = {
            "has_scheduled": True,
            "scene_type": next_sched["scene_type"],
            "actors": next_sched["actors"],
            "beat": next_sched["beat"],
            "recommendation": (
                f"SEMENTE DRAMÁTICA AGENDADA: A fila de trama possui uma cena sugerida como [{next_sched['scene_type']}] "
                f"com atores '{next_sched['actors'] or 'Protagonista'}': '{next_sched['beat']}'. "
                f"PROTOCOLO DE CONCILIAÇÃO: Avalie a ação do jogador '{action[:45]}'. "
                f"Se a ação do jogador concluir a batida atual ou se a situação pedir corte cinematográfico imediato, "
                f"execute a transição usando --scene-type {next_sched['scene_type']} e --actors '{next_sched['actors']}'. "
                f"Se a ação do jogador abrir novo atrito em tempo real que deve ser resolvido antes, resolva a ação "
                f"e mantenha a semente na fila para o momento oportuno."
            ),
        }
    else:
        scheduled_info = {"has_scheduled": False}

    # Determina personagens presentes na cena
    if actors and actors.strip():
        scene_present = actors.strip()
    else:
        scene_present = diario["present"]

    present_lower = scene_present.lower()

    # Identifica NPCs que constam como presentes na cena
    scene_npcs = [
        n for n in all_npcs
        if any(part.strip().lower() in present_lower for part in re.split(r"[\s(),&]+", n["name"]) if len(part.strip()) > 2)
    ]

    # Se a cena não listou NPCs explicitamente, verifica se a ação ou foco citam alguém conhecido
    if not scene_npcs:
        target_text = f"{action} {focus}".lower()
        scene_npcs = [
            n for n in all_npcs
            if any(part.strip().lower() in target_text for part in re.split(r"[\s(),&]+", n["name"]) if len(part.strip()) > 2)
        ]

    # Determina NPCs Focais vs Figurantes (Background)
    focal_names = set()
    if focus and focus.strip():
        focus_lower = focus.lower()
        for n in all_npcs:
            if any(part.strip().lower() in focus_lower for part in re.split(r"[\s(),&]+", n["name"]) if len(part.strip()) > 2):
                focal_names.add(n["name"])

    # Heurística automática: detecta NPCs citados diretamente na ação
    action_lower = action.lower()
    for n in (scene_npcs or all_npcs):
        if any(part.strip().lower() in action_lower for part in re.split(r"[\s(),&]+", n["name"]) if len(part.strip()) > 2):
            focal_names.add(n["name"])

    # Se nenhum foco foi especificado ou inferido, limita aos 2 primeiros da cena
    if not focal_names and scene_npcs:
        for n in scene_npcs[:2]:
            focal_names.add(n["name"])

    focal_npcs = []
    background_npcs = []
    seen_names = set()

    for n in all_npcs:
        if n["name"] in focal_names:
            focal_npcs.append(n)
            seen_names.add(n["name"])

    for n in scene_npcs:
        if n["name"] not in seen_names:
            background_npcs.append(n)
            seen_names.add(n["name"])

    situational_pacing = derive_situational_scene_structures(
        action=action,
        last_turn_summary=diario.get("last_turn_summary", ""),
        recent_shifts=diario.get("recent_state_shifts", []),
        clocks=diario.get("clocks", []),
        consecutive_standard=consec_std,
        focal_npcs=focal_npcs,
    )

    def clean_npc_profile(n: dict) -> dict:
        return {
            "name": n["name"],
            "attitude": n.get("attitude", ""),
            "psychology": n.get("psychology", ""),
            "will": n.get("will", ""),
            "weakness": n.get("weakness", ""),
            "dynamics": n.get("dynamics", ""),
            "bonds": n.get("bonds", {}),
            "autonomous_initiative": derive_npc_initiative(n),
        }

    background_cast = [f"{n['name']} ({n.get('attitude') or 'Presente'})" for n in background_npcs]

    # Decisão de Rolagem: Se cena for cutscene (interlude, parallel, dossier) sem protagonista, waive roll
    if scene_type in ("interlude", "parallel", "dossier"):
        needs_roll = False
    elif mode in ("writer", "architect"):
        needs_roll = False
    elif mode == "narrator":
        needs_roll = force_roll or bool(stat)
    else:
        needs_roll = (not no_roll) and (force_roll or bool(stat))

    chosen_stat = stat.upper().strip() if stat else ""
    if needs_roll and not chosen_stat and ficha["stats"]:
        chosen_stat = next(iter(ficha["stats"].keys()))

    stat_val = ficha["stats"].get(chosen_stat, 10)
    
    # Resolução de Disputa (PC vs NPC ou NPC vs NPC) sob o Framework Universal dos 3 Portões
    contest_data = None
    if contest_npc and contest_npc.strip():
        raw_c1 = contest_npc.strip()
        raw_c2 = vs_npc.strip() if vs_npc else ""

        # Detecção de sintaxe "NPC_A vs NPC_B" em --contest-npc
        if not raw_c2 and " vs " in raw_c1.lower():
            parts = re.split(r"\s+vs\s+", raw_c1, flags=re.IGNORECASE)
            if len(parts) >= 2:
                raw_c1, raw_c2 = parts[0].strip(), parts[1].strip()

        def find_npc_match(q: str):
            q_lower = q.lower()
            return next(
                (n for n in all_npcs if any(p.lower() in q_lower or q_lower in n["name"].lower() for p in re.split(r"[\s(),&]+", n["name"]) if len(p) > 2)),
                None
            )

        if raw_c2:
            # DISPUTA NPC vs NPC (Triangulação Horizontal Autônoma)
            m_npc1 = find_npc_match(raw_c1) or {"name": raw_c1, "psychology": "", "classification": "Elite"}
            m_npc2 = find_npc_match(raw_c2) or {"name": raw_c2, "psychology": "", "classification": "Elite"}

            for m in (m_npc1, m_npc2):
                if not any(n["name"] == m["name"] for n in focal_npcs):
                    focal_npcs.append(m)

            n1_stat_name, n1_stat_mod = ruleset.extract_npc_contest_modifier(m_npc1, npc_stat)
            n2_stat_name, n2_stat_mod = ruleset.extract_npc_contest_modifier(m_npc2, vs_stat)

            contest_data = ruleset.roll_contest(
                pc_name=m_npc1["name"],
                pc_stat_name=n1_stat_name,
                pc_stat_val=n1_stat_mod,
                npc_name=m_npc2["name"],
                npc_stat_name=n2_stat_name,
                npc_stat_mod=n2_stat_mod,
                pc_variant=npc_variant,
                npc_variant=vs_variant if vs_variant != "normal" else "normal",
                p1_is_npc=True,
            )
            roll_data = None
        else:
            # DISPUTA PC vs NPC
            matched_npc = find_npc_match(raw_c1)
            if not matched_npc:
                matched_npc = scene_npcs[0] if scene_npcs else {"name": raw_c1, "psychology": "", "classification": "Elite"}

            if not any(n["name"] == matched_npc["name"] for n in focal_npcs):
                focal_npcs.append(matched_npc)

            n_stat_name, n_stat_mod = ruleset.extract_npc_contest_modifier(matched_npc, npc_stat)
            contest_data = ruleset.roll_contest(
                pc_name=ficha.get("name", "Protagonista"),
                pc_stat_name=chosen_stat,
                pc_stat_val=stat_val,
                npc_name=matched_npc["name"],
                npc_stat_name=n_stat_name,
                npc_stat_mod=n_stat_mod,
                pc_variant=variant,
                npc_variant=npc_variant,
                p1_is_npc=False,
            )
            roll_data = None
    else:
        roll_data = ruleset.roll_3_gates(action[:35], variant, dc, chosen_stat, stat_val) if needs_roll else None

    header = f"[{diario['date_time']}] | [{diario['location']}] | [{scene_present}]"
    memories = query_aimemory(campaign_id, action[:60])
    mandate_cfg = MODE_PROSE_MANDATES[mode]

    # Auditoria pré-turno e detecção de Turno Crítico baseada na SITUAÇÃO + ESTADO MECÂNICO (Zero palavras-chave fixas)
    pre_audit = cmd_review(campaign_id)
    critical_reasons = []

    if critical or stakes.lower() in ("high", "climax"):
        critical_reasons.append(f"Tensão dramática declarada pelo Mestre para a situação atual (stakes='{stakes}').")
    if needs_roll and dc >= 20:
        critical_reasons.append(f"Dificuldade mecânica extrema (DC {dc}).")
    if contest_data is not None:
        if contest_data.get("is_npc_vs_npc"):
            if "Catástrofe" in contest_data["tier"] or "Dádiva" in contest_data["tier"] or contest_data["p1"]["natural"] in (1, 20) or contest_data["p2"]["natural"] in (1, 20):
                critical_reasons.append(f"Clímax de disputa direta entre NPCs ({contest_data['tier']}).")
        else:
            if contest_data["p1"]["natural"] in (1, 20) or contest_data["p2"]["natural"] in (1, 20) or "Catástrofe" in contest_data["tier"] or "Dádiva" in contest_data["tier"]:
                critical_reasons.append(f"Desfecho extremo na disputa de dados PC vs NPC ({contest_data['tier']}).")
            elif contest_data["delta"] < 0:
                critical_reasons.append(f"NPC venceu o confronto ({contest_data['p2']['name']} superou o herói por {abs(contest_data['delta'])}).")
    elif roll_data is not None and (roll_data["natural"] in (1, 20) or "Catástrofe" in roll_data["tier"] or "Dádiva" in roll_data["tier"]):
        critical_reasons.append(f"Desfecho extremo nos dados ({roll_data['tier'].split('(')[0].strip()}).")
    for v in ficha["vitals"].values():
        if v["max"] > 0 and (v["current"] / v["max"]) <= 0.30:
            critical_reasons.append(f"Recurso vital em nível crítico: {v['label']} em {v['current']}/{v['max']} (<= 30%).")
    if pre_audit["ssot_status"] != "CLEAN":
        critical_reasons.append(f"Anomalia de integridade detectada na pré-auditoria ({pre_audit['ssot_status']}).")
    for iss in pre_audit.get("issues", []):
        if iss["type"] == "CLOCK_BREACHED":
            critical_reasons.append(f"Relógio narrativo rompido: {iss['detail']}")
        elif iss["type"] == "NARRATIVE_STAGNATION":
            critical_reasons.append(f"Inércia narrativa detectada: {iss['detail']}")

    is_critical = len(critical_reasons) > 0

    if contest_data:
        cost_guide = contest_data["cost_directive"]
    elif roll_data:
        if "Custo" in roll_data["tier"] or "Falha" in roll_data["tier"] or "Catástrofe" in roll_data["tier"]:
            cost_guide = "OBRIGATÓRIO deduzir recursos vitais no --cost do commit devido ao atrito/revés do dado."
        else:
            cost_guide = "Deduza recursos (energia/fôlego/munição) caso a ação tenha exigido esforço ou habilidade ativa."
    else:
        cost_guide = "Resolução sem rolagem: aplique avanço de tempo (time +Xm) ou alteração de recursos conforme a situação narrada."

    npc_dynamics_prompt = []
    if len(focal_npcs) >= 2:
        for n_obj in focal_npcs:
            n_desc = f"{n_obj['name']}"
            if n_obj.get("will"):
                n_desc += f" (Vontade: {n_obj['will']})"
            if n_obj.get("weakness"):
                n_desc += f" (Fraqueza/Ponto Cego: {n_obj['weakness']})"
            if n_obj.get("dynamics"):
                n_desc += f" (Atritos/Laços: {n_obj['dynamics']})"
            npc_dynamics_prompt.append(n_desc)
    elif len(focal_npcs) == 1:
        n_obj = focal_npcs[0]
        n_desc = f"{n_obj['name']}"
        if n_obj.get("will"):
            n_desc += f" (Vontade: {n_obj['will']})"
        if n_obj.get("weakness"):
            n_desc += f" (Fraqueza/Ponto Cego: {n_obj['weakness']})"
        if n_obj.get("dynamics"):
            n_desc += f" (Atritos/Laços: {n_obj['dynamics']})"
        npc_dynamics_prompt.append(n_desc)

    scene_present_names = [p.strip().rstrip(".") for p in re.split(r",|\be\b", scene_present) if p.strip()]
    relational_tensions = find_scene_relational_tensions(scene_present_names, all_npcs, ficha.get("name", "Protagonista"))

    # Extração da Barreira Epistêmica de Vocabulário (Anti-Metagaming / Anti-Vazamento OOC)
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

    # Contexto de Missões e Objetivos (step_1_quest_context)
    all_quests = parse_quests_from_diario(info["diario"])
    active_quests = [q for q in all_quests if q["status"] == "ACTIVE"]

    clock_map = {c["name"].lower(): c for c in diario.get("clocks", [])}
    critical_quest_alerts = []
    active_quests_summary = []

    for q in active_quests:
        clk_name = q.get("clock", "").strip()
        is_clk_crit = False
        c_obj = clock_map.get(clk_name.lower()) if clk_name else None
        if c_obj:
            if c_obj.get("current", 0) >= c_obj.get("max", 4) - 1 and c_obj.get("status") == "ACTIVE":
                is_clk_crit = True
                critical_quest_alerts.append(
                    f"ALERTA CRÍTICO: O relógio '{c_obj['name']}' vinculado à missão '{q['title']}' está em {c_obj['progress']} (a 1 passo da ruptura iminente). A cena DEVE gerar atrito extremo sobre esta missão."
                )
        pending_objs = [o["text"] for o in q.get("objectives", []) if not o.get("done")]
        active_quests_summary.append({
            "id": q["id"],
            "title": q["title"],
            "type": q["type"],
            "phase": q.get("phase", ""),
            "contractor": q.get("contractor", ""),
            "clock": clk_name,
            "clock_status": c_obj["status"] if c_obj else "NONE",
            "clock_progress": c_obj["progress"] if c_obj else "",
            "clock_critical": is_clk_crit,
            "pending_objectives": pending_objs,
            "reward": q.get("reward", ""),
        })

    quest_mandate = " ".join(critical_quest_alerts) if critical_quest_alerts else (
        "Uma missão ativa deve produzir atrito concreto nesta cena. Vincule as decisões do protagonista aos seus objetivos declarados."
        if active_quests_summary else "Nenhuma missão ativa no momento; o protagonista pode buscar novos objetivos ou investigar o cenário."
    )

    progression_data = dict(ficha.get("progression") or parse_progression_from_ficha(info["ficha"]))
    lvl = progression_data.get("level", 1)
    scale_guide = (
        f"Protagonista Nível {lvl}: Calibre a escala de oponentes e atrito para desafios "
        + ("iniciais de sobrevivência e reputação local." if lvl == 1 else
           ("moderados condizentes com um herói em ascensão." if lvl <= 3 else
            ("veteranos e ameaças regionais de alta letalidade." if lvl <= 6 else
             "épicos e forças transcendentais de nível mestre.")))
    )
    progression_data["scale_guidance"] = scale_guide

    if focal_npcs:
        prefilled_npc = " | ".join(f"{n['name']}: Atitude: <postura pós-cena>; Relação: <relação pós-cena>" for n in focal_npcs)
    else:
        prefilled_npc = "<NPC: Atitude: ...; Relação: ...>"

    commit_hint = f'python lazy_turn.py commit --campaign {campaign_id} --summary "<resumo_factual>" --state-shift "<mudança_concreta>" --npc-updates "{prefilled_npc}"'
    if contest_data and not contest_data.get("is_npc_vs_npc") and ("Catástrofe" in contest_data["tier"] or "Revés" in contest_data["tier"] or "Impasse" in contest_data["tier"] or contest_data["delta"] <= 0):
        commit_hint += ' --cost "<HP -X, Stamina -Y>"'
    elif roll_data and ("Custo" in roll_data["tier"] or "Falha" in roll_data["tier"] or "Catástrofe" in roll_data["tier"]):
        commit_hint += ' --cost "<HP -X, Stamina -Y>"'
    if scene_type != "standard":
        commit_hint += f' --scene-type {scene_type}'
    if active_quests_summary:
        commit_hint += f' --quest-progress "{active_quests_summary[0]["id"]}:1"'

    mandates_by_type = STRUCTURAL_SCENE_MANDATES

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
        "step_1_quest_context": {
            "active_quests": active_quests_summary,
            "quest_pressure_mandate": quest_mandate,
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
    }
    if memories:
        payload["ai_memory_recall"] = memories
    if mode == "writer":
        payload["source_turns"] = extract_turns_from_diario(info["diario"], turns_spec)
    return payload


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
        res = upsert_clock_in_diario(diario_path, advance_name, advance=advance_steps)
    elif resolve_name:
        res = upsert_clock_in_diario(diario_path, resolve_name, status="RESOLVED")
        all_active_quests = parse_quests_from_diario(diario_path)
        linked_clock_names = {q["clock"].strip().lower() for q in all_active_quests if q.get("clock")}
        if resolve_name.strip().lower() not in linked_clock_names:
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
    if milestone:
        camp_overrides = get_campaign_overrides(campaign_id)
        base_step = get_base_step_from_overrides(camp_overrides)
        arc_xp = evaluate_xp_gain("arc_milestone", overrides=camp_overrides)
        prog_res = update_progression_in_ficha(info["ficha"], xp_add=arc_xp, base_step=base_step)
        diario_ctx = parse_diario_md(info["diario"])
        cur_turn = diario_ctx.get("last_turn_num")
        append_xp_ledger_entry(info["diario"], arc_xp, reason=f"Marco de arco arquivado: '{milestone}'", turn=cur_turn)
        res["arc_milestone_xp"] = arc_xp
        if prog_res.get("level_up"):
            res["level_up"] = prog_res["new_level"]
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


def cmd_check_prose(campaign_id: str = "", file_path: str = "", text: str = "") -> dict:
    """Audita rascunho de prosa literária contra regras de estilo (emojis, formato script, 4ª parede)."""
    prose_content = ""
    label = "prosa_inline"
    if file_path:
        f = Path(file_path)
        if not f.exists():
            return {"error": f"Arquivo de prosa '{file_path}' não encontrado.", "status": "FILE_NOT_FOUND", "has_violations": True, "issues": []}
        prose_content = f.read_text(encoding="utf-8")
        label = file_path
    elif text:
        prose_content = text
    else:
        if not sys.stdin.isatty():
            prose_content = sys.stdin.read()
            label = "stdin"
        else:
            return {"error": "Nenhum texto fornecido para check-prose. Use --file ou --text.", "status": "EMPTY", "has_violations": False, "issues": []}

    known_speakers = None
    if campaign_id:
        try:
            info = find_campaign(campaign_id)
            if info:
                ficha = parse_ficha_md(info["ficha"])
                all_npcs = parse_npcs_md(info["npcs"])
                known_speakers = set()
                if ficha.get("name"):
                    known_speakers.add(ficha["name"].strip())
                    for tok in re.split(r"[\s(),&_-]+", ficha["name"]):
                        if len(tok) >= 3 and tok[0].isupper():
                            known_speakers.add(tok)
                for npc_obj in all_npcs:
                    n_name = npc_obj.get("name", "").strip()
                    if n_name:
                        known_speakers.add(n_name)
                        for tok in re.split(r"[\s(),&_-]+", n_name):
                            if len(tok) >= 3 and tok[0].isupper():
                                known_speakers.add(tok)
        except Exception:
            pass

    issues = check_prose_lints(prose_content, context_label=label, known_speakers=known_speakers)
    return {
        "status": "CLEAN" if not issues else f"FOUND_{len(issues)}_ISSUES",
        "has_violations": len(issues) > 0,
        "campaign": campaign_id or None,
        "target": label,
        "issues": issues,
    }


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
    if prose_file:
        pf = Path(prose_file)
        if pf.exists():
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
        ficha_path.write_text(ficha_text, encoding="utf-8")
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
            ficha_path.write_text(ficha_text, encoding="utf-8")
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
                ups_res = upsert_clock_in_diario(diario_path, c_name, status="RESOLVED")
                applied.append(f"Relógio '{c_name}' resolvido via commit [{ups_res.get('status')}].")
                resolved_clocks.append(c_name)
    if clock_advance and diario_path.exists():
        for item in clock_advance.split("|"):
            parts = item.split(":")
            c_name = parts[0].strip()
            c_steps = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 1
            ups_res = upsert_clock_in_diario(diario_path, c_name, advance=c_steps)
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
                    ups_res = upsert_clock_in_diario(diario_path, c["name"], advance=1)
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
                else:
                    reward_xp = q_match.get("reward_xp") or DEFAULT_QUEST_REWARDS.get(q_match.get("type", "MAIN").upper(), 150)
                    upsert_quest_in_diario(diario_path, "complete", quest_id=qid, xp_paid=reward_xp, current_turn=next_turn)
                    prog_res = update_progression_in_ficha(ficha_path, xp_add=reward_xp, base_step=base_step)
                    applied.append(f"Missão Concluída: '{q_match['title']}' ({qid}) finalizada com sucesso (+{reward_xp} XP concedido).")
                    if prog_res.get("level_up"):
                        applied.append(f"EVOLUÇÃO DE NÍVEL: O protagonista atingiu o Nível {prog_res['new_level']}! (+{prog_res['bonuses']['attribute_points']} Ponto(s) de Atributo, vitais expandidos).")

    if quest_fail and diario_path.exists():
        for item in quest_fail.split("|"):
            parts = item.split(":")
            qid = parts[0].strip().upper()
            reason_text = parts[1].strip() if len(parts) > 1 else ""
            upsert_quest_in_diario(diario_path, "fail", quest_id=qid, reason=reason_text, current_turn=next_turn)
            applied.append(f"Missão Fracassada: '{qid}' encerrada com status FAILED ({reason_text or 'Sem justificativa'}).")

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

    new_dt = diario_ctx["date_time"]
    if time_str:
        t_clean = time_str.strip()
        if t_clean.startswith("+"):
            rel_mins = parse_time_increment(t_clean)
            if rel_mins > 0:
                new_dt = advance_time_str(diario_ctx["date_time"], rel_mins)
            else:
                new_dt = t_clean
        else:
            new_dt = t_clean
    elif time_advance_mins > 0:
        new_dt = advance_time_str(diario_ctx["date_time"], time_advance_mins)

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
        diario_path.write_text(diario_text + turn_entry, encoding="utf-8")
        applied.append(f"Diário atualizado: Turno {next_turn} registrado.")

    # 5. Fase 5 do Conselho: Auditoria Automática Pós-Commit (Modo Revisor)
    post_audit = cmd_review(campaign_id)
    final_header = f" [{new_dt}] |  [{new_loc}] |  [{new_pres}]"
    return {
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


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Orquestrador Determinístico Agnóstico de Turno e Modos RPG (Markdown SSOT)")
    sub = parser.add_subparsers(dest="cmd")

    p_prep = sub.add_parser("prepare", help="Prepara o contexto conforme o modo (gm, narrator, writer, reviewer, architect, director)")
    p_prep.add_argument("--campaign", required=True, help="ID da pasta da campanha")
    p_prep.add_argument("--action", default="Inspecionar contexto", help="Ação do jogador ou instrução do modo")
    p_prep.add_argument("--mode", default="gm", choices=["gm", "narrator", "writer", "reviewer", "architect", "director"], help="Modo de operação da skill")
    p_prep.add_argument("--stakes", default="normal", choices=["normal", "high", "climax"], help="Peso dramático da situação avaliada pelo Mestre (normal, high, climax)")
    p_prep.add_argument("--critical", action="store_true", help="Marca o turno como crítico pela avaliação contextual da cena")
    p_prep.add_argument("--turns", default="", help="Intervalo de turnos para o Modo Escritor (ex: '40-46' ou '45')")
    p_prep.add_argument("--variant", default="normal", choices=["normal", "advantage", "disadvantage", "adv", "disadv"])
    p_prep.add_argument("--dc", type=int, default=15, help="Classe de Dificuldade (10, 15, 20, 25)")
    p_prep.add_argument("--stat", default="", help="Atributo de ficha.md testado na situação (se houver oposição/risco)")
    p_prep.add_argument("--roll", action="store_true", help="Força rolagem de dados mesmo sem especificar --stat")
    p_prep.add_argument("--no-roll", action="store_true", help="Desativa rolagem de dados para ações sem oposição mecânica")
    p_prep.add_argument("--scene-type", "--scene_type", dest="scene_type", default="standard", choices=["standard", "interlude", "parallel", "timeskip", "dossier", "flashback", "prologue", "epilogue", "post_credits", "fade_to_black"], help="Tipo de estrutura de cena")
    p_prep.add_argument("--actors", default="", help="Personagens específicos em cena (substitui presentes padrão em interlúdios)")
    p_prep.add_argument("--focus", "--npc-focus", dest="focus", default="", help="NPC(s) em foco dramático imediato nesta ação (ex: 'Vanguarda' ou 'Capitão, Batedor')")
    p_prep.add_argument("--contest-npc", "--contest_npc", dest="contest_npc", default="", help="Nome do primeiro NPC para disputa (ou 'NPC1 vs NPC2')")
    p_prep.add_argument("--vs-npc", "--vs_npc", "--vs", dest="vs_npc", default="", help="Segundo NPC para disputa oposta NPC vs NPC")
    p_prep.add_argument("--npc-stat", "--npc_stat", dest="npc_stat", default="", help="Atributo ou eixo psicológico do primeiro NPC na disputa (ex: Composure, Boldness)")
    p_prep.add_argument("--vs-stat", "--vs_stat", dest="vs_stat", default="", help="Atributo ou eixo psicológico do segundo NPC na disputa")
    p_prep.add_argument("--npc-variant", "--npc_variant", dest="npc_variant", default="normal", choices=["normal", "advantage", "disadvantage", "adv", "disadv"], help="Vantagem ou desvantagem do primeiro NPC na rolagem")
    p_prep.add_argument("--vs-variant", "--vs_variant", dest="vs_variant", default="normal", choices=["normal", "advantage", "disadvantage", "adv", "disadv"], help="Vantagem ou desvantagem do segundo NPC na rolagem")

    p_com = sub.add_parser("commit", help="Registra as consequências do turno em ficha.md, npcs.md e diario.md")
    p_com.add_argument("--campaign", required=True, help="ID da pasta da campanha")
    p_com.add_argument("--summary", "--narrative", dest="summary", required=True, help="Resumo factual e consequências do turno para o diario.md")
    p_com.add_argument("--cost", default="", help="Qualquer recurso da ficha (ex: 'HP -3, Stamina -2, time +5m' ou '+1 HP, Sanidade -4')")
    p_com.add_argument("--time", default="", help="Nova data/hora exata ou incremento relativo (ex: '+15m', '+2h', '+14d', '+2m', '+1y')")
    p_com.add_argument("--location", default="", help="Novo local caso a cena mude de espaço")
    p_com.add_argument("--present-npcs", "--present_npcs", dest="present_npcs", default="", help="Nova lista de personagens presentes")
    p_com.add_argument("--npc-updates", "--npc_updates", dest="npc_updates", default="", help="Ex: 'NPC A: Nova atitude | NPC B: Nova atitude'")
    p_com.add_argument("--state-shift", "--state_shift", dest="state_shift", default="", help="Mudança concreta de estado no mundo, alianças ou recursos gerada pelo turno")
    p_com.add_argument("--clock-advance", "--clock_advance", dest="clock_advance", default="", help="Avança um ou mais relógios (ex: 'Invasão:1' ou 'Conspiração:2')")
    p_com.add_argument("--clock-resolve", "--clock_resolve", dest="clock_resolve", default="", help="Nome do relógio a resolver com sucesso no commit (ex: 'Invasão' ou 'Conspiração|Cerco')")
    p_com.add_argument("--scene-type", "--scene_type", dest="scene_type", default="standard", choices=["standard", "interlude", "parallel", "timeskip", "dossier", "flashback", "prologue", "epilogue", "post_credits", "fade_to_black"], help="Tipo estrutural do turno para etiquetagem no diário")
    p_com.add_argument("--add-ability", default="", help="Adiciona uma nova Habilidade & Técnica em ficha.md")
    p_com.add_argument("--add-milestone", default="", help="Adiciona um novo Marco de Evolução Pessoal em ficha.md")
    p_com.add_argument("--add-item", default="", help="Adiciona um item ao Equipamento & Inventário em ficha.md")
    p_com.add_argument("--quest-progress", default="", help="Avança objetivo de missão (ex: 'Q1:2' para marcar objetivo 2 da missão Q1)")
    p_com.add_argument("--quest-complete", default="", help="Conclui missão como COMPLETED e credita XP (ex: 'Q1')")
    p_com.add_argument("--quest-fail", default="", help="Marca missão como FAILED com razão opcional (ex: 'Q1:motivo')")
    p_com.add_argument("--prose", default="", help="Texto direto da prosa para auditoria preventiva de estilo")
    p_com.add_argument("--prose-file", "--prose_file", dest="prose_file", default="", help="Arquivo de rascunho de prosa para auditoria preventiva")
    p_com.add_argument("--force", action="store_true", help="Força a gravação mesmo com violações na prosa")

    p_chk = sub.add_parser("check-prose", help="Audita rascunho de prosa literária contra regras duras de estilo (emojis, formato script, 4ª parede)")
    p_chk.add_argument("--campaign", default="", help="ID da pasta da campanha para checagem de personagens conhecidos")
    p_chk.add_argument("--file", default="", help="Caminho do arquivo de rascunho de prosa a auditar")
    p_chk.add_argument("--text", default="", help="Texto direto da prosa a auditar")

    p_rev = sub.add_parser("review", help="Executa auditoria determinística de Cânone e Integridade Referencial (Modo Revisor)")
    p_rev.add_argument("--campaign", required=True, help="ID da pasta da campanha")

    p_clk = sub.add_parser("clock", help="Gerencia relógios narrativos de facções e prazos em diario.md")
    p_clk.add_argument("--campaign", required=True, help="ID da pasta da campanha")
    p_clk.add_argument("--list", action="store_true", help="Lista todos os relógios ativos e rompidos")
    p_clk.add_argument("--add", default="", help="Nome do novo relógio a ser cadastrado")
    p_clk.add_argument("--max", type=int, default=4, help="Número total de segmentos do relógio (padrão: 4)")
    p_clk.add_argument("--trigger", default="", help="Evento concreto que eclode quando o relógio atinge o máximo")
    p_clk.add_argument("--advance", default="", help="Nome do relógio a avançar")
    p_clk.add_argument("--steps", type=int, default=1, help="Quantidade de passos a avançar (padrão: 1)")
    p_clk.add_argument("--resolve", default="", help="Nome do relógio a marcar como resolvido/desarmado")
    p_clk.add_argument("--json", action="store_true", help="Exibe a saída em formato JSON")

    p_plan = sub.add_parser("plan", help="Gerencia o planejamento de trama, fila de cenas e ritmo dramático em diario.md (Modo Diretor/Showrunner)")
    p_plan.add_argument("--campaign", required=True, help="ID da pasta da campanha")
    p_plan.add_argument("--list", action="store_true", help="Lista a fila de cenas planejadas, marcos futuros e status do ritmo")
    p_plan.add_argument("--add", "--beat", dest="add", default="", help="Adiciona uma nova batida dramática ou cena à fila de planejamento")
    p_plan.add_argument("--scene-type", "--scene_type", dest="scene_type", default="interlude", choices=["standard", "interlude", "parallel", "timeskip", "dossier", "flashback", "prologue", "epilogue", "post_credits", "fade_to_black"], help="Tipo estrutural da cena a agendar")
    p_plan.add_argument("--actors", default="", help="Personagens específicos em foco na cena agendada")
    p_plan.add_argument("--complete", type=int, default=None, help="Índice da cena pendente a marcar como concluída [x]")
    p_plan.add_argument("--milestone", default="", help="Adiciona um novo marco futuro do arco em diario.md")
    p_plan.add_argument("--json", action="store_true", help="Exibe a saída em formato JSON")

    p_arc = sub.add_parser("arc", help="Gerencia a transição de arcos, encerramento de capítulos e novo cabeçalho de cena em diario.md (Modo Showrunner)")
    p_arc.add_argument("--campaign", required=True, help="ID da pasta da campanha")
    p_arc.add_argument("--title", default="", help="Novo título do arco dramático")
    p_arc.add_argument("--question", default="", help="Nova pergunta central ou conflito do arco")
    p_arc.add_argument("--stage", default="", help="Fase do arco (ex: Preparação, Confrontação, Clímax, Resolução)")
    p_arc.add_argument("--scene-name", "--scene_name", dest="scene_name", default="", help="Título da nova cena canônica (ex: 'O Cerco da Fortaleza')")
    p_arc.add_argument("--date", default="", help="Nova data/hora canônica (ex: '24 de Dezembro de 2018, 15:30')")
    p_arc.add_argument("--location", default="", help="Novo local canônico (ex: 'Fronteira Norte, Posto Avançado')")
    p_arc.add_argument("--present", default="", help="Nova lista canônica de personagens presentes")
    p_arc.add_argument("--resolve-clocks", action="store_true", help="Marca todos os relógios do arco anterior como RESOLVED")
    p_arc.add_argument("--milestone", default="", help="Registra um marco de encerramento do arco anterior em diario.md")
    p_arc.add_argument("--json", action="store_true", help="Exibe a saída em formato JSON")

    p_npc = sub.add_parser("upsert-npc", help="Cadastra ou enriquece um NPC com Vontade Própria, Fraquezas e Atritos")
    p_npc.add_argument("--campaign", required=True, help="ID da pasta da campanha")
    p_npc.add_argument("--name", required=True, help="Nome do NPC")
    p_npc.add_argument("--classification", default="", help="Grau / Classificação do NPC")
    p_npc.add_argument("--role", default="", help="Papel na trama")
    p_npc.add_argument("--attitude", default="", help="Atitude Atual na cena")
    p_npc.add_argument("--psychology", default="", help="Psicologia & Tell (Drive, Diligence, Boldness...)")
    p_npc.add_argument("--will", default="", help="Vontade Própria & Agenda Autônoma (o que quer para si)")
    p_npc.add_argument("--weakness", default="", help="Fraquezas, traumas e pontos cegos")
    p_npc.add_argument("--dynamics", default="", help="Atritos e laços com outros NPCs")
    p_npc.add_argument("--appearance", default="", help="Aparência física e voz")
    p_npc.add_argument("--bonds", default="", help="Vínculos & Matriz Relacional")
    p_npc.add_argument("--relation", default="", help="Relação com Protagonista")

    p_init = sub.add_parser("init-campaign", help="Inicializa uma nova campanha canônica com os 5 arquivos Markdown a partir dos templates oficiais")
    p_init.add_argument("--campaign", required=True, help="ID da pasta da campanha (ex: 'fantasia_reinos')")
    p_init.add_argument("--title", default="", help="Título legível da campanha")
    p_init.add_argument("--protagonist", default="Protagonista", help="Nome do protagonista")
    p_init.add_argument("--date", default="01 de Outubro de 2026, 12:00", help="Data/Hora inicial no diário")
    p_init.add_argument("--location", default="Local Inicial", help="Local inicial da cena")

    p_qst = sub.add_parser("quest", help="Gerencia missões, objetivos e ciclo de vida teleológico em diario.md")
    p_qst.add_argument("--campaign", required=True, help="ID da pasta da campanha")
    p_qst.add_argument("--list", action="store_true", help="Lista todas as missões cadastradas")
    p_qst.add_argument("--add", default="", help="Título da nova missão a cadastrar")
    p_qst.add_argument("--type", default="main", choices=["main", "side", "personal", "faction"], help="Tipo de missão (padrão: main)")
    p_qst.add_argument("--objective", default="", help="Objetivo inicial ao cadastrar com --add OU adicionar a missão existente (ex: 'Q1: texto')")
    p_qst.add_argument("--faction", "--contractor", dest="faction", default="", help="Contratante ou facção patrona da missão")
    p_qst.add_argument("--clock", default="", help="Nome do relógio de ameaça vinculado")
    p_qst.add_argument("--reward", default="", help="Recompensa textual e XP sugerido (ex: '150 XP')")
    p_qst.add_argument("--phase", default="", help="Fase atual da missão (ex: Investigação, Confronto)")
    p_qst.add_argument("--check", default="", help="Marca objetivo como concluído [x] (ex: 'Q1:1')")
    p_qst.add_argument("--complete", default="", help="Conclui a missão como COMPLETED (ex: 'Q1')")
    p_qst.add_argument("--fail", default="", help="Marca a missão como FAILED (ex: 'Q1')")
    p_qst.add_argument("--block", default="", help="Bloqueia a missão como BLOCKED (ex: 'Q1')")
    p_qst.add_argument("--unblock", default="", help="Desbloqueia a missão como ACTIVE (ex: 'Q1')")
    p_qst.add_argument("--abandon", default="", help="Abandona a missão como ABANDONED (ex: 'Q1')")
    p_qst.add_argument("--reopen", default="", help="Reabre missão terminal como ACTIVE com justificativa auditada")
    p_qst.add_argument("--reason", default="", help="Justificativa para falha, bloqueio ou reabertura")
    p_qst.add_argument("--evidence", default="", help="Evidência diegética de cumprimento da missão")
    p_qst.add_argument("--json", action="store_true", help="Exibe a saída em formato JSON")

    p_prg = sub.add_parser("progress", help="Gerencia consulta de XP, evolução de nível e gastos de build em ficha.md")
    p_prg.add_argument("--campaign", required=True, help="ID da pasta da campanha")
    p_prg.add_argument("--list", action="store_true", help="Lista nível, XP acumulado e pontos disponíveis")
    p_prg.add_argument("--spend-attr", default="", help="Gasta 1 Ponto de Atributo para aumentar o atributo escolhido (ex: 'FOR')")
    p_prg.add_argument("--spend-ability", default="", help="Gasta 1 Ponto de Habilidade para adquirir nova técnica (ex: 'Golpe: efeito')")
    p_prg.add_argument("--training", default="", help="Justificativa diegética ou cena de treino necessária para gastar Ponto de Habilidade")
    p_prg.add_argument("--award", default="", help="Concede XP administrativo/retroativo (ex: 'quest_main:150', 'obj_main', '100')")
    p_prg.add_argument("--reason", default="", help="Justificativa diegética para concessão avulsa de XP")
    p_prg.add_argument("--json", action="store_true", help="Exibe a saída em formato JSON")

    return parser


def main():
    parser = build_cli()
    args = parser.parse_args()
    if args.cmd == "prepare":
        res = cmd_prepare(
            args.campaign,
            args.action,
            args.variant,
            args.dc,
            args.stat,
            args.roll,
            args.no_roll,
            args.mode,
            args.turns,
            args.stakes,
            args.critical,
            scene_type=args.scene_type,
            actors=args.actors,
            focus=args.focus,
            contest_npc=args.contest_npc,
            vs_npc=args.vs_npc,
            npc_stat=args.npc_stat,
            vs_stat=args.vs_stat,
            npc_variant=args.npc_variant,
            vs_variant=args.vs_variant,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "commit":
        res = cmd_commit(
            args.campaign,
            args.summary,
            args.cost,
            args.time,
            args.location,
            args.present_npcs,
            args.npc_updates,
            state_shift=args.state_shift,
            clock_advance=args.clock_advance,
            clock_resolve=args.clock_resolve,
            scene_type=args.scene_type,
            add_ability=args.add_ability,
            add_milestone=args.add_milestone,
            add_item=args.add_item,
            prose=args.prose,
            prose_file=args.prose_file,
            force=args.force,
            quest_progress=args.quest_progress,
            quest_complete=args.quest_complete,
            quest_fail=args.quest_fail,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        if res.get("prose_status") == "REJECTED":
            sys.exit(1)
    elif args.cmd == "check-prose":
        res = cmd_check_prose(
            campaign_id=args.campaign,
            file_path=args.file,
            text=args.text,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        if res.get("has_violations"):
            sys.exit(1)
    elif args.cmd == "review":
        res = cmd_review(args.campaign)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "clock":
        res = cmd_clock(
            args.campaign,
            list_clocks=args.list,
            add_name=args.add,
            max_steps=args.max,
            trigger=args.trigger,
            advance_name=args.advance,
            advance_steps=args.steps,
            resolve_name=args.resolve,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\nRelógios Narrativos — Campanha '{args.campaign}':")
            if not res.get("clocks"):
                print("  (Nenhum relógio cadastrado em diario.md)")
            for c in res.get("clocks", []):
                st_icon = "BREACHED" if c["status"] == "BREACHED" else ("RESOLVED" if c["status"] == "RESOLVED" else "ACTIVE")
                trig_txt = f" -> Gatilho: {c['trigger']}" if c["trigger"] else ""
                print(f"  * [{c['name']}]: {c['progress']} {c['bar']} [{st_icon}]{trig_txt}")
            if res.get("action_result"):
                act = res["action_result"]
                print(f"\n[Ação]: Relógio '{act.get('name')}' {act.get('action')} -> {act.get('current')}/{act.get('max')} [{act.get('status')}]")
    elif args.cmd == "plan":
        res = cmd_plan(
            args.campaign,
            list_plan=args.list,
            add_beat=args.add,
            scene_type=args.scene_type,
            actors=args.actors,
            complete_idx=args.complete,
            add_milestone=args.milestone,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\nPlanejamento de Trama & Fila de Cenas — Campanha '{args.campaign}':")
            print(f"  Arco Ativo: {res['arc'].get('title', 'Nenhum')} ({res['arc'].get('stage', 'Fase não definida')})")
            print(f"  Ritmo Linear: {res['consecutive_standard_turns']} turnos standard seguidos -> [{res['pacing_advice']}]")
            print("\n  Fila de Cenas Agendadas:")
            if not res.get("planned_scenes"):
                print("    (Nenhuma cena agendada em diario.md)")
            for idx, sc in enumerate(res.get("planned_scenes", [])):
                st = "[x]" if sc["done"] else "[ ]"
                act = f" (Atores: {sc['actors']})" if sc["actors"] else ""
                print(f"    {idx}. {st} [{sc['scene_type']}]{act}: {sc['beat']}")
            if res.get("future_milestones"):
                print("\n  Marcos Futuros do Arco:")
                for m in res["future_milestones"]:
                    print(f"    * {m}")
            if res.get("action_result") and res["action_result"] != "status_queried":
                print(f"\n[Ação]: {res['action_result']}")
    elif args.cmd == "arc":
        res = cmd_arc(
            args.campaign,
            title=args.title,
            question=args.question,
            stage=args.stage,
            scene_name=args.scene_name,
            location=args.location,
            date_time=args.date,
            present=args.present,
            resolve_clocks=args.resolve_clocks,
            milestone=args.milestone,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\nTransição de Arco / Cena — Campanha '{args.campaign}':")
            print(f"  Cabeçalho: {res['current_scene_header']}")
            print(f"  Arco: {res['arc'].get('title', 'Nenhum')} ({res['arc'].get('stage', 'Fase não definida')})")
            print(f"  Pergunta Central: {res['arc'].get('central_question', 'Nenhuma')}")
            for up in res.get("action_result", {}).get("updates", []):
                print(f"  * {up}")
    elif args.cmd == "upsert-npc":
        try:
            info = find_campaign(args.campaign)
        except (ValueError, FileNotFoundError) as e:
            print(json.dumps({"error": str(e)}))
            return
        if not info:
            print(json.dumps({"error": f"Campanha '{args.campaign}' não encontrada."}))
        else:
            res = upsert_npc_to_md(
                info["npcs"],
                name=args.name,
                classification=args.classification,
                role=args.role,
                attitude=args.attitude,
                psychology=args.psychology,
                will=args.will,
                weakness=args.weakness,
                dynamics=args.dynamics,
                appearance=args.appearance,
                bonds=args.bonds,
                relation=args.relation,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "init-campaign":
        res = init_campaign_from_templates(
            campaign_id=args.campaign,
            title=args.title,
            protagonist_name=args.protagonist,
            start_date=args.date,
            start_loc=args.location,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "quest":
        res = cmd_quest(
            args.campaign,
            list_quests=args.list,
            add_title=args.add,
            quest_type=args.type,
            objective=args.objective,
            faction=args.faction,
            clock=args.clock,
            reward=args.reward,
            phase=args.phase,
            check_target=args.check,
            complete_id=args.complete,
            fail_id=args.fail,
            block_id=args.block,
            unblock_id=args.unblock,
            abandon_id=args.abandon,
            reopen_id=args.reopen,
            reason=args.reason,
            evidence=args.evidence,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\nMissões & Objetivos — Campanha '{args.campaign}':")
            if not res.get("quests"):
                print("  (Nenhuma missão cadastrada em diario.md)")
            for q in res.get("quests", []):
                st_icon = q["status"]
                prg = f"[{q['progress_summary']}]"
                print(f"  * [{q['id']}] [{q['type']}] {q['title']} — {prg} [{st_icon}] (Recompensa: {q.get('reward') or 'N/A'})")
                for obj in q.get("objectives", []):
                    chk = "[x]" if obj["done"] else "[ ]"
                    print(f"      {obj['index']}. {chk} {obj['text']}")
            if res.get("action_result"):
                print(f"\n[Ação]: {res['action_result']}")
    elif args.cmd == "progress":
        res = cmd_progress(
            args.campaign,
            list_progress=args.list,
            spend_attr=args.spend_attr,
            spend_ability=args.spend_ability,
            training=args.training,
            award=args.award,
            reason=args.reason,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            prg = res.get("progression", {})
            print(f"\nProgressão do Protagonista — Campanha '{args.campaign}':")
            print(f"  Nível: {prg.get('level', 1)}")
            print(f"  Experiência (XP): {prg.get('xp', 0)} / {prg.get('next_threshold', 250)}")
            print(f"  Pontos de Atributo Disponíveis: {prg.get('attribute_points', 0)}")
            print(f"  Pontos de Habilidade Disponíveis: {prg.get('ability_points', 0)}")
            if res.get("action_result"):
                print(f"\n[Ação]: {res['action_result']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
