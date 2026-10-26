"""council.reviewer.py: Auditoria de Cânone, SSOT, paradoxos temporais e estagnação narrativa."""

import re
from pathlib import Path
from council.helpers import find_campaign, CAMPAIGN_DIRS
from council.ssot import parse_ficha_md, parse_diario_md, extract_turns_from_diario, parse_progression_from_ficha
from council.narrator import parse_npcs_md
from council.prose_linter import (
    EMOJI_PATTERN, FOURTH_WALL_PATTERN, PT_MONTHS, RESERVED_METADATA_KEYS,
    SCRIPT_BRACKET_PATTERN, SCRIPT_UNBRACKETED_PATTERN, SPEECH_VERBS,
    audit_quests_and_xp_in_campaign, check_prose_lints, detect_temporal_paradoxes, parse_pt_date,
)
from council.reviewer_checks import audit_factions_in_campaign, check_causal_inconsistencies


def cmd_review(campaign_id: str) -> dict:
    """Modo Revisor: Audita integridade referencial, temporal, profundidade psicológica de NPCs e cânone (100% agnóstico)."""
    try:
        info = find_campaign(campaign_id)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e), "ssot_status": "CORRUPTED", "issues": [str(e)]}
    if not info:
        return {"error": f"Campanha '{campaign_id}' não encontrada em {CAMPAIGN_DIRS}."}

    ficha = parse_ficha_md(info["ficha"])
    diario = parse_diario_md(info["diario"])
    all_npcs = parse_npcs_md(info["npcs"])
    issues = []

    # 1. Sincronia de Recursos Vitais (ficha.md vs último turno do diario.md)
    ficha_snapshot = ", ".join(f"{v['label'].split('(')[0].strip()} {v['current']}/{v['max']}" for v in ficha["vitals"].values())
    m_vit = re.search(r"Vitais:\s*([^\n.]+)", diario["last_turn_summary"])
    diario_snapshot = m_vit.group(1).strip() if m_vit else ""
    if diario_snapshot and diario_snapshot != ficha_snapshot:
        is_level_up_expansion = False
        prog = parse_progression_from_ficha(info["ficha"])
        level = prog.get("level", 1)
        if level > 1:
            vit_pairs = re.findall(r"([A-Za-zÀ-Ú/ ]+?)\s*(\d+)\s*/\s*(\d+)", diario_snapshot)
            bonus_hp, bonus_sta, bonus_ce = (level - 1) * 2, (level - 1) * 1, (level - 1) * 1
            matches = 0
            for lbl, _cur, mx in vit_pairs:
                clean_lbl, mx_i = lbl.strip().lower(), int(mx)
                for v in ficha["vitals"].values():
                    k_clean = v["label"].split("(")[0].strip().lower()
                    if clean_lbl in k_clean or k_clean in clean_lbl:
                        exp_max = mx_i + (bonus_hp if "hp" in clean_lbl or "vida" in clean_lbl else (bonus_sta if "sta" in clean_lbl or "fôlego" in clean_lbl else bonus_ce))
                        if v["max"] == exp_max:
                            matches += 1
            if matches >= 2 and matches == len(vit_pairs):
                is_level_up_expansion = True

        if not is_level_up_expansion:
            issues.append({
                "type": "VITALS_DESYNC", "severity": "HIGH",
                "detail": f"Dessincronia entre ficha.md ('{ficha_snapshot}') e o último turno do diario.md ('{diario_snapshot}').",
            })

    # 2. Integridade Referencial e Profundidade dos NPCs Presentes em Cena
    protag_full_low = ficha["name"].lower().strip()
    protag_tokens = {t.lower() for t in re.split(r"[\s(),&]+", ficha["name"]) if len(t) > 2}
    clean_present_str = re.sub(r"\([^)]*\)", "", diario["present"])
    present_raw = [p.strip().rstrip(".") for p in re.split(r",|\be\b", clean_present_str) if p.strip()]
    checked_npc_names = set()

    for pres in present_raw:
        p_low = pres.lower()
        if p_low == protag_full_low or any(tok in p_low for tok in protag_tokens) or not pres[0].isupper():
            continue
        matched_npc = None
        for npc_obj in all_npcs:
            n_low = npc_obj["name"].lower()
            if any(tok in n_low for tok in re.split(r"[\s(),&]+", p_low) if len(tok) > 2):
                matched_npc = npc_obj
                break
        if not matched_npc:
            issues.append({
                "type": "MISSING_NPC_IN_SSOT",
                "severity": "MEDIUM",
                "detail": f"Personagem nomeado presente em diario.md ('{pres}') não possui seção ### correspondente em npcs.md.",
            })
        elif matched_npc["name"] not in checked_npc_names:
            checked_npc_names.add(matched_npc["name"])
            missing_traits = []
            if not matched_npc["psychology"]:
                missing_traits.append("Psicologia & Tell")
            if not matched_npc["will"]:
                missing_traits.append("Vontade Própria / Motivação")
            if not matched_npc["weakness"]:
                missing_traits.append("Fraquezas & Pontos Cegos")
            if matched_npc["is_stub"] or missing_traits:
                issues.append({
                    "type": "INCOMPLETE_NPC_PROFILE",
                    "severity": "MEDIUM",
                    "detail": (
                        f"O NPC ativo em cena '{matched_npc['name']}' possui perfil raso/incompleto "
                        f"(faltando: {', '.join(missing_traits) or 'dados completos'}). "
                        f"Se pertencer a uma obra conhecida, consulte a Wiki via search_web e execute "
                        f"'python lazy_turn.py upsert-npc --campaign {campaign_id} --name \"{matched_npc['name']}\" ...' "
                        f"para definir sua Vontade Própria, Fraquezas e Atritos com outros NPCs."
                    ),
                })

    # 3. Contaminação de Atitudes em npcs.md
    for npc in all_npcs:
        att = npc.get("attitude", "")
        for other in all_npcs:
            if npc["name"] != other["name"]:
                other_short = other["name"].split("(")[0].strip()
                if f"{other_short}:" in att:
                    issues.append({
                        "type": "CONTAMINATED_NPC_ATTITUDE",
                        "severity": "HIGH",
                        "detail": f"A atitude de '{npc['name']}' contém texto vazado de '{other_short}:'.",
                    })

    # 4. Sequência de Turnos em diario.md
    diario_text = info["diario"].read_text(encoding="utf-8") if info["diario"].exists() else ""
    turn_nums = [int(n) for n in re.findall(r"\*\s*\*\*Turno\s+(\d+)(?:\s*\[[^\]]+\])?:\*\*", diario_text)]
    for idx in range(1, len(turn_nums)):
        if turn_nums[idx] != turn_nums[idx - 1] + 1:
            issues.append({
                "type": "TURN_SEQUENCE_GAP",
                "severity": "LOW",
                "detail": f"Salto ou duplicidade na numeração de turnos: Turno {turn_nums[idx - 1]} -> Turno {turn_nums[idx]}.",
            })

    # 5. Consistência Cronológica
    scan_targets = [(f"diario.md (Turno {diario['last_turn_num']})", diario["last_turn_summary"])]
    for npc in all_npcs:
        scan_targets.append((f"npcs.md ({npc['name']})", npc["summary"]))
    for p_msg in detect_temporal_paradoxes(diario["date_time"], scan_targets):
        issues.append({"type": "TEMPORAL_PARADOX", "severity": "HIGH", "detail": p_msg})

    # 6. Relógios Narrativos Rompidos
    for c in diario.get("clocks", []):
        if c["status"] == "BREACHED":
            issues.append({
                "type": "CLOCK_BREACHED",
                "severity": "CRITICAL",
                "detail": (
                    f"O relógio narrativo '{c['name']}' atingiu o limite máximo ({c['progress']})! "
                    f"Gatilho obrigatório de ruptura: '{c['trigger'] or 'Erupção de complicação grave'}'. "
                    f"O Mestre deve acionar o evento imediatamente na próxima cena."
                ),
            })

    # 7. Inércia Narrativa / Estagnação de Estado
    shifts = diario.get("recent_state_shifts", [])
    if len(shifts) >= 2:
        last_s = shifts[-1]["shift"].strip().lower()
        penult_s = shifts[-2]["shift"].strip().lower()
        if (last_s == penult_s) or ("nenhuma" in last_s) or ("mesmo" in last_s and "estado" in last_s):
            issues.append({
                "type": "NARRATIVE_STAGNATION",
                "severity": "HIGH",
                "detail": (
                    f"Inércia narrativa detectada nos turnos {shifts[-2]['turn']} e {shifts[-1]['turn']}: "
                    f"a Mudança de Estado permaneceu inalterada ('{shifts[-1]['shift']}'). "
                    f"O próximo turno exige obrigatoriamente uma Ruptura de Normalidade ou alteração concreta de posição/recursos."
                ),
            })

    # 8. Ausência de Relógios Ativos no Arco
    active_clocks = [c for c in diario.get("clocks", []) if c["status"] == "ACTIVE"]
    if not active_clocks and diario.get("arc", {}).get("title"):
        issues.append({
            "type": "MISSING_ACTIVE_CLOCKS",
            "severity": "MEDIUM",
            "detail": (
                f"O arco ativo '{diario['arc']['title']}' não possui nenhum relógio narrativo de ameaça ou facção com status ACTIVE. "
                f"O Mestre deve cadastrar relógios de pressão (ex: 'lazy_turn.py clock --campaign {campaign_id} --add \"Nome do Relógio\" --max 4 --trigger \"Evento\"') para manter o mundo em movimento autônomo."
            ),
        })

    # 9. Fadiga de Ritmo Linear
    consec_std = diario.get("consecutive_standard_turns", 0)
    if consec_std >= 5:
        issues.append({
            "type": "PACING_FATIGUE",
            "severity": "MEDIUM",
            "detail": (
                f"Fadiga de ritmo linear detectada: {consec_std} turnos consecutivos no formato padrão (tempo real centrado no protagonista) sem quebra de perspectiva. "
                f"O Mestre deve acionar proativamente uma quebra dramática via 'lazy_turn.py prepare --scene-type interlude|dossier|timeskip|flashback' ou planejar a fila com 'lazy_turn.py plan'."
            ),
        })

    # 10. Rastreamento de Itens e Armas no Inventário
    inv_text = " ".join(ficha.get("inventory", [])).lower()
    item_keywords = ["alabarda", "espada", "adaga", "machado", "arco", "lança", "escudo", "manopla", "amuleto", "anel", "cajado", "elmo", "couraça", "armadura", "relicário", "tomo", "pergaminho"]
    shifts_to_check = [s.get("shift", "") for s in diario.get("recent_state_shifts", [])] + [diario.get("last_turn_summary", "")]
    for shift_s in shifts_to_check:
        shift_low = shift_s.lower()
        if any(term in shift_low for term in ["posse", "adquire", "empunha", "tomou", "arranca", "pega", "leva a", "reivindica"]):
            for kw in item_keywords:
                if kw in shift_low and kw not in inv_text:
                    issues.append({
                        "type": "UNTRACKED_INVENTORY_ITEM",
                        "severity": "HIGH",
                        "detail": (
                            f"O item/arma com a palavra-chave '{kw}' foi citado como em posse ou adquirido pelo protagonista no diário ('{shift_s[:80]}...'), "
                            f"mas não consta em ficha.md sob Equipamento & Inventário. "
                            f"Atualize via 'lazy_turn.py commit --add-item \"<Nome Completo do Item>\"' para restaurar a integridade."
                        ),
                    })
                    break

    # 11. Estagnação de Atitude de NPCs Presentes
    cur_loc_low = diario.get("location", "").lower()
    geography_terms = ["cume", "cratera", "caverna", "pico", "garganta", "floresta", "aldeia", "refúgio", "refugio", "acampamento", "palácio", "cidade"]
    for pres in present_raw:
        matched_npc = next((npc_obj for npc_obj in all_npcs if any(tok in npc_obj["name"].lower() for tok in re.split(r"[\s(),&]+", pres.lower()) if len(tok) > 2)), None)
        if matched_npc:
            att = matched_npc.get("attitude", "")
            att_low = att.lower()
            for geo in geography_terms:
                if geo in att_low and geo not in cur_loc_low:
                    issues.append({
                        "type": "STALE_NPC_ATTITUDE",
                        "severity": "MEDIUM",
                        "detail": (
                            f"A Atitude Atual de '{matched_npc['name']}' em npcs.md ainda descreve o cenário anterior ('{geo}': '{att[:70]}...'), "
                            f"embora a cena esteja agora em '{diario.get('location')}'. "
                            f"Atualize a postura dela via 'lazy_turn.py upsert-npc --name \"{matched_npc['name']}\" --attitude \"<nova postura>\"' ou passe '--npc-updates' no commit."
                        ),
                    })
                    break

    # 12. Verificação de Marcos Futuros Concluídos
    future_mils = diario.get("plot_plan", {}).get("future_milestones", [])
    last_turn_text = (diario.get("last_turn_summary", "") + " " + " ".join(s.get("shift", "") for s in diario.get("recent_state_shifts", [])[-2:])).lower()
    campaign_stop_tokens = {t.lower() for t in re.split(r"[\s(),&_-]+", ficha.get("name", "") + " " + campaign_id) if len(t) >= 3}
    for f_mil in future_mils:
        f_tokens = [tok.lower() for tok in re.split(r"[\s(),&]+", f_mil) if len(tok) >= 5 and tok not in campaign_stop_tokens]
        if f_tokens and len(f_tokens) >= 3:
            matches = sum(1 for tok in f_tokens if tok in last_turn_text)
            if matches >= 3 and (matches / len(f_tokens) >= 0.60):
                issues.append({
                    "type": "PENDING_MILESTONE_PROMOTION",
                    "severity": "LOW",
                    "detail": (
                        f"O marco futuro '{f_mil}' possui forte correspondência ({matches}/{len(f_tokens)} termos-chave) com os eventos dos turnos recentes. "
                        f"Verifique se este marco foi alcançado e, se sim, promova-o para os Marcos da Crônica e atualize a ficha via '--add-milestone'."
                    ),
                })

    # 13. Lints de Estilo e Prosa Literária
    known_speakers = set()
    for raw_name in [ficha.get("name", "")] + [n.get("name", "") for n in all_npcs]:
        n_clean = raw_name.strip()
        if n_clean:
            known_speakers.add(n_clean)
            for tok in re.split(r"[\s(),&_-]+", n_clean):
                if len(tok) >= 3 and tok[0].isupper():
                    known_speakers.add(tok)

    prose_texts_checked = set()
    if diario.get("last_turn_summary"):
        lbl = f"diario.md (Turno {diario['last_turn_num']} - Resumo)"
        prose_texts_checked.add(diario["last_turn_summary"])
        issues.extend(check_prose_lints(diario["last_turn_summary"], context_label=lbl, known_speakers=known_speakers))

    for t_item in extract_turns_from_diario(info["diario"], turns_spec=""):
        t_text = t_item["text"]
        if t_text not in prose_texts_checked:
            prose_texts_checked.add(t_text)
            issues.extend(check_prose_lints(t_text, context_label=f"diario.md (Turno {t_item['turn']})", known_speakers=known_speakers))

    # 14 & 15. Integridade de Missões, Objetivos e Progressão XP
    issues.extend(audit_quests_and_xp_in_campaign(info, diario, diario_text))

    # 16 & 17. Integridade de Facções, Reputação, Causalidade e Prosa Externa
    issues.extend(audit_factions_in_campaign(info, all_npcs))
    camp_dir = Path(info.get("ficha", ".")).parent
    issues.extend(check_causal_inconsistencies(camp_dir, campaign_id))

    return {
        "campaign": campaign_id,
        "operation_mode": "reviewer",
        "ssot_status": "CLEAN" if not issues else f"FOUND_{len(issues)}_ISSUES",
        "last_turn_checked": diario["last_turn_num"],
        "ficha_vitals": ficha_snapshot,
        "diario_last_vitals": diario_snapshot,
        "present_in_scene": diario["present"],
        "registered_npcs_count": len(all_npcs),
        "issues": issues,
        "reviewer_mandate": [
            "1. Relate todas as inconsistências de SSOT, cronologia e perfis de NPCs incompletos listadas em 'issues'.",
            "2. Avalie se os NPCs estão interagindo ENTRE SI na cena (Triangulação Horizontal) e exibindo suas Vontades Próprias e Fraquezas, em vez de agirem como uma claque uniforme para o protagonista.",
            "3. Caso o usuário peça correção, utilize lazy_turn.py upsert-npc ou commit para restaurar a integridade.",
        ],
    }
