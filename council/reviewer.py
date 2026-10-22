"""council.reviewer.py: Auditoria de Cânone, SSOT, paradoxos temporais e estagnação narrativa."""

import re
from pathlib import Path
from council.helpers import find_campaign, CAMPAIGN_DIRS
from council.ssot import parse_ficha_md, parse_diario_md, extract_turns_from_diario, parse_progression_from_ficha
from council.narrator import parse_npcs_md
from council.quests import parse_quests_from_diario, parse_xp_ledger_from_diario

# --- Constantes e Padrões de Lints de Prosa Literária (P3) ---
EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001F5FF"  # Symbols & Pictographs
    r"\U0001F600-\U0001F64F"  # Emoticons
    r"\U0001F680-\U0001F6FF"  # Transport & Map
    r"\U0001F700-\U0001F77F"  # Alchemical Symbols
    r"\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    r"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    r"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    r"\U0001FA00-\U0001FA6F"  # Chess Symbols
    r"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    r"\u2600-\u26FF"          # Misc Symbols (ex: ⚔, ⚰, ⚡, ☕)
    r"\u2700-\u27BF]"          # Dingbats (ex: ✨, ❌, ❓)
)

SCRIPT_BRACKET_PATTERN = re.compile(
    r"(?m)^\s*(?:\*\s*)?(?:\*\*[^*]+\*\*\s*)?\[([A-Za-zÀ-ÖØ-öø-ÿ\s]{2,30})\]\s*:(?!\*\*)\s*(.+)"
)
SCRIPT_UNBRACKETED_PATTERN = re.compile(
    r"(?m)^\s*(?:\*\s*)?(?:\*\*[^*]+\*\*\s*)?([A-ZÀ-ÖØ-ß][A-Za-zÀ-ÖØ-öø-ÿ\s]{1,30})\s*:\s*(.+)"
)

FOURTH_WALL_PATTERN = re.compile(
    r"(?i)\b(?:o\s+que\s+(?:(?:você|voce|vc)\s+)?(?:faz|fará|fara|vai\s+fazer|decide|escolhe)|"
    r"qual\s+(?:é\s+a\s+sua|a\s+sua|é\s+sua|sua)\s+(?:ação|acao|decisão|decisao|escolha)|"
    r"como\s+(?:(?:você|voce|vc)\s+)?(?:reage|responde))\b[^\n.!?]*\??",
    re.IGNORECASE,
)

RESERVED_METADATA_KEYS = {
    "turno", "vitais", "data", "data & local", "presentes", "fatos",
    "mudança de estado", "mudanca de estado", "marco", "status",
    "gatilho", "atores", "título", "titulo", "fase", "pergunta central",
    "conflito central", "questão", "questao", "nota", "cena", "arco",
    "hp", "stamina", "ce", "pv", "mp", "rad",
    # Metadados de resumo, pós-turno e commit:
    "atitude", "relação", "relacao", "local", "resumo", "custo", "item", "tempo",
    "autor", "personagem", "classe", "grau", "nível", "nivel"
}

SPEECH_VERBS = {
    "disse", "respondeu", "falou", "gritou", "murmurou", "sussurrou",
    "exclamou", "perguntou", "declarou", "afirmou", "adverte", "indaga",
    "prossegue", "comenta", "acrescentou", "retrucou", "rebateu", "ordenou",
    "anunciou", "avisa", "avisou", "lembra", "lembrou"
}


def check_prose_lints(
    text: str,
    context_label: str = "diario.md",
    known_speakers: set | list | None = None,
) -> list:
    """Audita violações duras de estilo literário: emojis, formato script [Nome]: e perguntas de 4ª parede.
    
    Se known_speakers for fornecido, a detecção de 'Nome: Fala' (sem colchetes) restringe-se
    a personagens conhecidos da campanha, eliminando falsos positivos com metadados ou cláusulas
    de diálogo legítimas ('Ela disse:', 'Resumo:', 'Atitude:').
    """
    issues = []
    if not text:
        return issues

    known_lower = {s.lower().strip() for s in known_speakers} if known_speakers else None

    # 1. Zero Emojis
    m_emoji = EMOJI_PATTERN.search(text)
    if m_emoji:
        emoji_char = m_emoji.group(0)
        issues.append({
            "type": "EMOJI_DETECTED",
            "severity": "MEDIUM",
            "detail": (
                f"Caractere emoji detectado em {context_label} ('{emoji_char}'): "
                f"o estilo literário do RPGPRO exige prosa textual pura sem emojis."
            ),
        })

    # 2. Proibição de Roteiro Teatral ([Nome]: ou Nome: fala)
    # 2a. Formato com colchetes: [Nome]: ... (sempre violação de roteiro teatral)
    m_bracket = SCRIPT_BRACKET_PATTERN.search(text)
    if m_bracket:
        bracket_name = m_bracket.group(1).strip()
        bracket_str = f"[{bracket_name}]:"
        issues.append({
            "type": "SCRIPT_FORMAT_DETECTED",
            "severity": "HIGH",
            "detail": (
                f"Formato teatral detectado em {context_label} ('{bracket_str}'): "
                f"utilize travessão literário (—) e diálogo integrado à narrativa em vez de '[Nome]:'."
            ),
        })
    else:
        # 2b. Formato sem colchetes: Nome: fala
        for m_unbracket in SCRIPT_UNBRACKETED_PATTERN.finditer(text):
            raw_speaker = m_unbracket.group(1).strip()
            rest = m_unbracket.group(2).strip()
            speaker_low = raw_speaker.lower()

            if speaker_low in RESERVED_METADATA_KEYS:
                continue

            speaker_words = [w.lower() for w in re.split(r"\s+", raw_speaker) if w]
            if any(w in SPEECH_VERBS for w in speaker_words):
                continue

            # Se known_speakers foi passado, só dispara para personagens conhecidos da campanha
            is_script = False
            if known_lower is not None:
                if speaker_low in known_lower or any(speaker_low == k or speaker_low in k for k in known_lower):
                    is_script = True
            else:
                # Sem lista de personagens: exige que a fala comece com aspas ou tenha padrão claro de diálogo
                if rest.startswith(('"', "'", "“", "”")):
                    is_script = True

            if is_script:
                snippet = f"{raw_speaker}: {rest[:40]}"
                issues.append({
                    "type": "SCRIPT_FORMAT_DETECTED",
                    "severity": "HIGH",
                    "detail": (
                        f"Formato teatral detectado em {context_label} ('{snippet}'): "
                        f"utilize travessão literário (—) e diálogo integrado à narrativa em vez de '{raw_speaker}:'."
                    ),
                })
                break

    # 3. Proibição de Quarta Parede ("O que você faz?")
    m_4th = FOURTH_WALL_PATTERN.search(text)
    if m_4th:
        question_str = m_4th.group(0).strip()
        issues.append({
            "type": "FOURTH_WALL_QUESTION",
            "severity": "MEDIUM",
            "detail": (
                f"Pergunta de quebra de quarta parede detectada em {context_label} ('{question_str}'): "
                f"encerre com impacto sensorial e gancho dramático aberto, sem recorrer ao clichê 'O que você faz?'."
            ),
        })

    return issues

PT_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def parse_pt_date(text: str):
    """Extrai (ano, mes, dia) de uma string de data em português (ex: '25 de Novembro de 2018')."""
    if not text:
        return None
    m = re.search(
        r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+(\d{4}))?",
        text,
        re.IGNORECASE,
    )
    if m:
        day = int(m.group(1))
        month = PT_MONTHS[m.group(2).lower()]
        year = int(m.group(3)) if m.group(3) else None
        return (year, month, day)
    return None


def detect_temporal_paradoxes(current_dt_str: str, texts_to_scan: list) -> list:
    """Detecta de forma agnóstica se textos tratam uma data já passada no calendário da campanha como evento futuro."""
    cur_parsed = parse_pt_date(current_dt_str)
    if not cur_parsed or not cur_parsed[0]:
        return []
    cur_year, cur_month, cur_day = cur_parsed
    paradoxes = []
    future_markers = r"(?:antes\s+de|até\s+o\s+dia|ate\s+o\s+dia|para\s+a\s+noite\s+de|para\s+o\s+dia|aguardando\s+o\s+dia|programado\s+para(?:\s+a\s+noite\s+de)?)"
    pattern = rf"{future_markers}\s+(\d{{1,2}})\s+de\s+(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+(\d{{4}}))?"

    for label, txt in texts_to_scan:
        if not txt:
            continue
        for m in re.finditer(pattern, txt, re.IGNORECASE):
            d = int(m.group(1))
            mo = PT_MONTHS[m.group(2).lower()]
            yr = int(m.group(3)) if m.group(3) else cur_year
            if (yr, mo, d) < (cur_year, cur_month, cur_day):
                paradoxes.append(
                    f"Paradoxo temporal em {label}: a expressão '{m.group(0)}' trata {d:02d}/{mo:02d}/{yr} como futuro, mas o calendário atual da campanha já está em '{current_dt_str}' ({cur_day:02d}/{cur_month:02d}/{cur_year})."
                )
    return paradoxes


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
    ficha_snapshot = ", ".join(
        f"{v['label'].split('(')[0].strip()} {v['current']}/{v['max']}"
        for v in ficha["vitals"].values()
    )
    m_vit = re.search(r"Vitais:\s*([^\n.]+)", diario["last_turn_summary"])
    diario_snapshot = m_vit.group(1).strip() if m_vit else ""
    if diario_snapshot and diario_snapshot != ficha_snapshot:
        is_level_up_expansion = False
        prog = parse_progression_from_ficha(info["ficha"])
        level = prog.get("level", 1)
        if level > 1:
            vit_pairs = re.findall(r"([A-Za-zÀ-Ú/ ]+?)\s*(\d+)\s*/\s*(\d+)", diario_snapshot)
            f_vitals = ficha["vitals"]
            bonus_hp = (level - 1) * 2
            bonus_sta = (level - 1) * 1
            bonus_ce = (level - 1) * 1
            matches = 0
            for lbl, cur, mx in vit_pairs:
                clean_lbl = lbl.strip().lower()
                cur_i, mx_i = int(cur), int(mx)
                for k, v in f_vitals.items():
                    k_clean = v["label"].split("(")[0].strip().lower()
                    if clean_lbl in k_clean or k_clean in clean_lbl:
                        exp_max = mx_i + (bonus_hp if "hp" in clean_lbl or "vida" in clean_lbl else (bonus_sta if "sta" in clean_lbl or "fôlego" in clean_lbl else bonus_ce))
                        if v["max"] == exp_max:
                            matches += 1
            if matches >= 2 and matches == len(vit_pairs):
                is_level_up_expansion = True

        if not is_level_up_expansion:
            issues.append({
                "type": "VITALS_DESYNC",
                "severity": "HIGH",
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

    # 3. Contaminação de Atitudes em npcs.md (múltiplos NPCs concatenados na mesma linha de Atitude Atual)
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

    # 5. Consistência Cronológica (Detecção Agnóstica de Paradoxo Temporal)
    scan_targets = [(f"diario.md (Turno {diario['last_turn_num']})", diario["last_turn_summary"])]
    for npc in all_npcs:
        scan_targets.append((f"npcs.md ({npc['name']})", npc["summary"]))
    for p_msg in detect_temporal_paradoxes(diario["date_time"], scan_targets):
        issues.append({
            "type": "TEMPORAL_PARADOX",
            "severity": "HIGH",
            "detail": p_msg,
        })

    # 6. Relógios Narrativos Rompidos (CLOCK_BREACHED)
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

    # 7. Inércia Narrativa / Estagnação de Estado (NARRATIVE_STAGNATION)
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

    # 8. Ausência de Relógios Ativos no Arco (MISSING_ACTIVE_CLOCKS)
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

    # 9. Fadiga de Ritmo Linear (PACING_FATIGUE)
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

    # 10. Rastreamento de Itens e Armas no Inventário (UNTRACKED_INVENTORY_ITEM)
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

    # 11. Estagnação de Atitude de NPCs Presentes (STALE_NPC_ATTITUDE)
    cur_loc_low = diario.get("location", "").lower()
    for pres in present_raw:
        matched_npc = None
        for npc_obj in all_npcs:
            if any(tok in npc_obj["name"].lower() for tok in re.split(r"[\s(),&]+", pres.lower()) if len(tok) > 2):
                matched_npc = npc_obj
                break
        if matched_npc:
            att = matched_npc.get("attitude", "")
            att_low = att.lower()
            # Se o local mudou drasticamente (ex: montanha -> refúgio/aldeia), verifica se a atitude ainda descreve o local antigo
            geography_terms = ["cume", "cratera", "caverna", "pico", "garganta", "floresta", "aldeia", "refúgio", "refugio", "acampamento", "palácio", "cidade"]
            for geo in geography_terms:
                if geo in att_low and geo not in cur_loc_low:
                    # O local citado na atitude não bate com o local da cena atual
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

    # 12. Verificação de Marcos Futuros Concluídos (PENDING_MILESTONE_PROMOTION)
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

    # 13. Lints de Estilo e Prosa Literária (EMOJI_DETECTED, SCRIPT_FORMAT_DETECTED, FOURTH_WALL_QUESTION)
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

    prose_texts_checked = set()
    if diario.get("last_turn_summary"):
        lbl = f"diario.md (Turno {diario['last_turn_num']} - Resumo)"
        prose_texts_checked.add(diario["last_turn_summary"])
        issues.extend(check_prose_lints(diario["last_turn_summary"], context_label=lbl, known_speakers=known_speakers))

    recent_turns = extract_turns_from_diario(info["diario"], turns_spec="")
    for t_item in recent_turns:
        t_text = t_item["text"]
        if t_text not in prose_texts_checked:
            prose_texts_checked.add(t_text)
            lbl = f"diario.md (Turno {t_item['turn']})"
            issues.extend(check_prose_lints(t_text, context_label=lbl, known_speakers=known_speakers))

    # 14. Integridade de Missões & Objetivos (QUEST_WITHOUT_OBJECTIVES, QUEST_STALE, QUEST_CLOCK_LINK_BROKEN, QUEST_OVERDUE, QUEST_REWARD_PAID_TWICE)
    quests = parse_quests_from_diario(info["diario"])
    clock_map = {c["name"].lower(): c for c in diario.get("clocks", [])}
    for q in quests:
        if not q.get("objectives"):
            issues.append({
                "type": "QUEST_WITHOUT_OBJECTIVES",
                "severity": "MEDIUM",
                "detail": f"A missão '{q['title']}' ({q['id']}) foi cadastrada sem nenhum objetivo em sub-bullets [ ] no diário.",
            })

        if q.get("status") == "ACTIVE":
            if q.get("last_progress"):
                m_turn = re.search(r"Turno\s*(\d+)", q["last_progress"], re.IGNORECASE)
                if m_turn:
                    last_p_turn = int(m_turn.group(1))
                    if diario["last_turn_num"] - last_p_turn >= 10:
                        issues.append({
                            "type": "QUEST_STALE",
                            "severity": "LOW",
                            "detail": f"A missão ativa '{q['title']}' ({q['id']}) não registra progresso há mais de {diario['last_turn_num'] - last_p_turn} turnos (último: Turno {last_p_turn}).",
                        })

            if q.get("clock"):
                c_low = q["clock"].strip().lower()
                if c_low not in clock_map:
                    issues.append({
                        "type": "QUEST_CLOCK_LINK_BROKEN",
                        "severity": "HIGH",
                        "detail": f"A missão '{q['title']}' ({q['id']}) está vinculada ao relógio '{q['clock']}', mas este não consta em '### Relógios de Ameaça & Prazos'.",
                    })
                elif clock_map[c_low]["status"] == "BREACHED":
                    issues.append({
                        "type": "QUEST_OVERDUE",
                        "severity": "HIGH",
                        "detail": (
                            f"O relógio vinculado '{clock_map[c_low]['name']}' rompeu ({clock_map[c_low]['progress']}) "
                            f"enquanto a missão '{q['title']}' ({q['id']}) permanece com status ACTIVE. "
                            f"O Mestre deve arbitrar diegeticamente a falha (--quest-fail) ou nova fase de contingência."
                        ),
                    })

        raw_header = q.get("raw_header", "")
        if raw_header.lower().count("xp pago") > 1:
            issues.append({
                "type": "QUEST_REWARD_PAID_TWICE",
                "severity": "CRITICAL",
                "detail": f"Duplicidade de pagamento detectada na missão '{q['title']}' ({q['id']}): mais de um carimbo de 'XP Pago' presente na linha.",
            })

    # Auditoria de tentativas duplicadas registradas no histórico
    for t_item in diario.get("turns", []):
        t_text = t_item.get("text", "")
        if "Tentativa de pagamento duplicado de XP barrada" in t_text:
            issues.append({
                "type": "QUEST_REWARD_PAID_TWICE",
                "severity": "CRITICAL",
                "detail": f"Tentativa de pagamento duplicado de XP detectada no histórico (Turno {t_item['turn']}).",
            })

    # 15. Auditoria de Progressão & Coerência de XP (XP_MISMATCH)
    prog = parse_progression_from_ficha(info["ficha"])
    ledger = parse_xp_ledger_from_diario(info["diario"])
    total_xp_paid_quests = sum(q.get("xp_paid") or 0 for q in quests)
    total_xp_ledger = sum(e.get("amount") or 0 for e in ledger)
    total_auditable_xp = total_xp_paid_quests + total_xp_ledger

    if total_auditable_xp > 0 and prog["xp"] != total_auditable_xp:
        issues.append({
            "type": "XP_MISMATCH",
            "severity": "HIGH",
            "detail": f"Divergência de XP: O total acumulado na ficha ({prog['xp']} XP) difere da soma dos créditos auditáveis no diário ({total_auditable_xp} XP = {total_xp_paid_quests} de missões + {total_xp_ledger} do registro).",
        })

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
