"""Caso de uso `prepare`: monta o contexto e o mandato do turno."""

import re

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
from application.showrunner import cmd_plan


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
    }
    if memories:
        payload["ai_memory_recall"] = memories
    if mode == "writer":
        payload["source_turns"] = extract_turns_from_diario(info["diario"], turns_spec)
    return payload
