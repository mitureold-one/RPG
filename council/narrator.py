"""council.narrator.py: Módulo do Narrador, gerador de NPCs, inteligência social e barreira epistêmica."""

import re
from pathlib import Path


def extract_md_field(block_text: str, patterns: tuple) -> str:
    """Extrai o valor de um campo '* **Campo:** Valor' dentro de um bloco de NPC."""
    for pat in patterns:
        m = re.search(rf"\*\s*\*\*{pat}[^*]*:\*\*\s*([^\n]+)", block_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def extract_npc_bonds(body: str) -> dict:
    """Extrai mapa de vínculos relacionais {alvo: descricao} de um bloco de NPC."""
    bonds = {}
    m_sec = re.search(r"\*\s*\*\*(?:Vínculos|Matriz Relacional|Relações|Laços)[^*]*:\*\*\s*(.*?)(?=\n\*|\Z)", body, re.DOTALL | re.IGNORECASE)
    if m_sec:
        sec_text = m_sec.group(1).strip()
        for line in sec_text.splitlines():
            line_s = line.strip().lstrip("* -").strip()
            if not line_s:
                continue
            if ":" in line_s:
                target, desc = line_s.split(":", 1)
                bonds[target.strip()] = desc.strip()
            elif "—" in line_s:
                target, desc = line_s.split("—", 1)
                bonds[target.strip()] = desc.strip()

    m_protag = re.search(r"\*\s*\*\*Relação com Protagonista:\*\*\s*([^\n]+)", body, re.IGNORECASE)
    if m_protag:
        bonds["Protagonista"] = m_protag.group(1).strip()

    if not bonds:
        m_dyn = re.search(r"\*\s*\*\*Atritos[^*]*:\*\*\s*([^\n]+)", body, re.IGNORECASE)
        if m_dyn:
            raw = m_dyn.group(1).strip()
            for item in raw.split(";"):
                item = item.strip()
                if ":" in item:
                    target, desc = item.split(":", 1)
                    bonds[target.strip()] = desc.strip()
                elif "—" in item:
                    target, desc = item.split("—", 1)
                    bonds[target.strip()] = desc.strip()
    return bonds


def find_scene_relational_tensions(present_names: list, all_npcs: list, protag_name: str = "") -> list:
    """Cruza os personagens presentes em cena com seus vínculos e extrai as tensões relacionais ativas."""
    tensions = []
    clean_presents = [p.strip() for p in present_names if p.strip()]
    clean_p_low = [p.lower() for p in clean_presents]
    protag_low = protag_name.lower().strip() if protag_name else "protagonista"

    for npc in all_npcs:
        n_name = npc["name"]
        n_low = n_name.lower()
        if not any(p in n_low or n_low in p for p in clean_p_low):
            continue

        bonds = npc.get("bonds", {})
        for target, desc in bonds.items():
            t_low = target.lower()
            is_protag = (t_low in ("protagonista", protag_low) or (protag_low and protag_low in t_low))
            target_present = False
            target_label = target

            if is_protag:
                if any(protag_low in p or "protagonista" in p for p in clean_p_low):
                    target_present = True
                    target_label = protag_name or "Protagonista"
            else:
                for p_raw in clean_presents:
                    p_l = p_raw.lower()
                    if t_low in p_l or p_l in t_low:
                        target_present = True
                        target_label = p_raw
                        break

            if target_present:
                tensions.append(f"{n_name} -> {target_label}: {desc}")

    return tensions


def extract_epistemic_forbidden_terms(ficha_text: str, mundo_text: str, diario_text: str = "") -> list:
    """Extrai dinamicamente da ficha os termos da identidade privada, segredos e origem do protagonista ausentes do mundo público (100% agnóstico de gênero/cenário)."""
    if not ficha_text:
        return []

    # 1. Seções de conhecimento estritamente privado do protagonista na ficha
    private_corpus = []

    m_orig = re.search(r"\*\s*\*\*Origem[^*]*:\*\*\s*([^\n]+)", ficha_text, re.IGNORECASE)
    if m_orig:
        private_corpus.append(m_orig.group(1))

    m_arq = re.search(r"\*\s*\*\*Classificação\s*/\s*Arquétipo:\*\*\s*([^\n]+)", ficha_text, re.IGNORECASE)
    if m_arq:
        private_corpus.append(m_arq.group(1))

    m_hab = re.search(r"###\s*Habilidades & Técnicas\s*\n(.*?)(?=\n###|\Z)", ficha_text, re.DOTALL | re.IGNORECASE)
    if m_hab:
        for line in m_hab.group(1).splitlines():
            line_s = line.strip().lstrip("* -")
            if ":" in line_s:
                title, desc = line_s.split(":", 1)
                private_corpus.append(title.strip().replace("**", ""))

    m_sec = re.search(r"\*\s*\*\*Segredos[^*]*:\*\*\s*([^\n]+)", ficha_text, re.IGNORECASE)
    if m_sec:
        private_corpus.append(m_sec.group(1))

    full_private_text = " ".join(private_corpus)
    if not full_private_text:
        return []

    # 2. Extrai tokens substantivos e compostos da esfera privada (termos com hífen ou capitalizados)
    hyphenated = re.findall(r"\b[A-Za-zÀ-ú]{3,}(?:-[A-Za-zÀ-ú]{2,})+\b", full_private_text)
    capitalized = re.findall(r"\b[A-ZÀ-Ú][a-zA-ZÀ-ú]{3,}\b", full_private_text)
    candidates = set(hyphenated + capitalized)

    # 3. Stopwords gramaticais universais da língua portuguesa (preposições, artigos, advérbios e verbos comuns)
    stopwords = {
        "durante", "quando", "depois", "ainda", "muito", "foram", "tendo", "mesmo", "mesma",
        "outro", "outra", "outros", "outras", "sobre", "entre", "através", "atraves", "onde",
        "como", "para", "pela", "pelo", "pelas", "pelos", "este", "esta", "estes", "estas",
        "esse", "essa", "esses", "essas", "aquele", "aquela", "aqueles", "aquelas", "cada",
        "tudo", "nada", "mais", "menos", "seus", "suas", "dele", "dela", "deles", "delas",
        "primeiro", "primeira", "segundo", "segunda", "terceiro", "terceira", "inata", "inatas",
        "sistema", "programa", "modo", "estilo", "combate", "forma", "nível", "nivel", "grau",
        "classe", "total", "parcial", "direta", "direto", "todas", "todos", "gestado", "amadurecido",
        "lançada", "romperam", "aterrissou"
    }

    # Ignora o título H1 do documento mundo.md (que pode conter o nome meta da campanha, ex: '# Crônicas: O Filho de X')
    m_clean = re.sub(r"^#[^\n]+", "", mundo_text) if mundo_text else ""
    m_low = m_clean.lower()
    forbidden = []

    for cand in candidates:
        c_low = cand.lower().strip()
        if c_low in stopwords or len(c_low) < 4:
            continue
        # Se o termo NÃO existe no texto do mundo, os habitantes daquele cenário desconhecem o conceito
        if c_low not in m_low:
            forbidden.append(cand.strip())

    return sorted(list(set(forbidden)))


def derive_situational_scene_structures(
    action: str,
    last_turn_summary: str,
    recent_shifts: list,
    clocks: list,
    consecutive_standard: int,
    focal_npcs: list = None,
) -> dict:
    """Analisa os sinais dramáticos concretos da situação imediata E das Vontades/Traumas dos NPCs para sugerir estruturas narrativas (100% agnóstico)."""
    text_pool = (
        action + " " +
        last_turn_summary + " " +
        " ".join(s.get("shift", "") for s in recent_shifts)
    ).lower()

    proposals = []
    focal_npcs = focal_npcs or []

    # 1. Estruturas derivadas da Vontade Própria, Traumas e Atritos dos NPCs presentes
    for n in focal_npcs:
        n_name = n.get("name", "NPC")
        n_will = n.get("will", "")
        n_weak = n.get("weakness", "")
        n_bonds = n.get("bonds", {})

        # Flashback centrado no NPC (se o NPC carrega trauma, cicatriz ou segredo antigo)
        weak_low = n_weak.lower()
        if any(w in weak_low for w in ["trauma", "cicatriz", "passado", "paranoia", "paranóica", "perda", "culpa", "medo", "honra"]):
            proposals.append({
                "scene_type": "flashback",
                "focus_actor": n_name,
                "trigger_signal": f"Trauma/ponto cego de {n_name}: '{n_weak}'.",
                "narrative_hook": f"Flashback revelando a origem da fraqueza/cicatriz de {n_name} e o momento do passado que dita sua conduta no presente."
            })

        # Cena Paralela da Facção do NPC (a Vontade do NPC envolve proteger seu clã/povo distante)
        will_low = n_will.lower()
        if any(w in will_low for w in ["clã", "cla", "matilha", "povo", "família", "familia", "reino", "irmandade", "facção", "faccao", "tribo", "aliança"]):
            proposals.append({
                "scene_type": "parallel",
                "focus_actor": f"Clã / Aliados de {n_name}",
                "trigger_signal": f"Vontade autônoma de {n_name} em relação à sua facção: '{n_will}'.",
                "narrative_hook": f"Cena paralela mostrando a base/clã de {n_name} reagindo aos ecos da batalha e tomando decisões estratégicas sem a liderança dela."
            })

    # Interlúdio Inter-NPCs (Deliberação secreta entre 2+ NPCs presentes longe do herói)
    if len(focal_npcs) >= 2:
        n1, n2 = focal_npcs[0]["name"], focal_npcs[1]["name"]
        proposals.append({
            "scene_type": "interlude",
            "focus_actor": f"{n1} e {n2}",
            "trigger_signal": f"Vínculos e hierarquia interna entre {n1} e {n2}.",
            "narrative_hook": f"Conferência secreta entre {n1} e {n2}: as duas se afastam por alguns metros e deliberam em sussurros/dialeto nativo sobre se devem confiar, usar ou trair o protagonista."
        })

    # 2. Sinal para Dossiê Documental (dossier)
    dossier_signals = [
        "corvo", "relatório", "relatorio", "carta", "ordem", "inquisição", "inquisicao",
        "senado", "patrulha", "patrulhas", "busca", "buscas", "sensor", "sensores",
        "investigação", "investigacao", "tribunal", "boletim", "mandado", "procurado",
        "registro", "escuta", "espião", "espiao", "espiões", "espioes"
    ]
    if any(sig in text_pool for sig in dossier_signals):
        proposals.append({
            "scene_type": "dossier",
            "focus_actor": "Rede de Inteligência / Autoridades",
            "trigger_signal": "Comunicações oficiais, investigações ou relatórios de busca ativos no cenário.",
            "narrative_hook": "Apresentar a cena como relatório confidencial de inteligência, carta interceptada ou mandado oficial avaliando a anomalia ou os NPCs presentes."
        })

    # 3. Sinal para Interlúdio de Antagonistas Externos (interlude)
    critical_clocks = [c for c in clocks if c.get("status") == "ACTIVE" and (c.get("current", 0) / max(1, c.get("max", 1))) >= 0.70]
    antagonist_generic_words = [
        "reagrupamento", "conselho", "vanguarda", "generais", "mobilização", "mobilizacao",
        "patrulhas de busca", "inimigo", "senado", "tropa", "esquadrão", "esquadrao",
        "guarnição", "guarnicao", "comandante", "oficial", "alerta geral", "emboscada"
    ]
    if critical_clocks or any(sig in text_pool for sig in antagonist_generic_words):
        reasons = [f"Relógio crítico '[{c['name']}]' em {c['progress']}" for c in critical_clocks]
        proposals.append({
            "scene_type": "interlude",
            "focus_actor": "Forças Antagônicas / Comandantes",
            "trigger_signal": "; ".join(reasons) if reasons else "Movimentação de forças antagônicas fora da presença do protagonista.",
            "narrative_hook": "Cortar a perspectiva para os antagonistas organizando o cerco ou a resposta tática nos bastidores."
        })

    # 4. Sinal para Salto Temporal / Montagem (timeskip)
    timeskip_signals = [
        "curada", "curadas", "curado", "curados", "descanso", "acampar", "dormir", "noite",
        "amanhecer", "anoitecer", "esperar", "vigília", "vigilia", "viagem", "estrada",
        "recuperação", "recuperacao", "horas", "dias", "estabilizados", "estabilizado"
    ]
    if any(sig in text_pool for sig in timeskip_signals):
        proposals.append({
            "scene_type": "timeskip",
            "focus_actor": "Grupo em Transição",
            "trigger_signal": "Crise imediata estabilizada (cura concluída ou necessidade de deslocamento/vigília).",
            "narrative_hook": "Condensar horas ou dias de viagem, treino ou vigília sob montagem sensorial acelerada até o próximo ponto de atrito."
        })

    # 5. Sinal para Fade to Black / Clímax Sensorial (fade_to_black)
    fade_signals = [
        "beijo", "pele", "calor", "toque", "abraço", "abraco", "abrigo", "caverna",
        "despir", "despida", "despido", "ofegante", "olhar nos olhos", "sussurro",
        "intimidade", "respiração próxima", "respiracao proxima", "leito"
    ]
    if any(sig in text_pool for sig in fade_signals):
        proposals.append({
            "scene_type": "fade_to_black",
            "focus_actor": "Personagens em Intimidade",
            "trigger_signal": "Intimidade tátil e vulnerabilidade mútua no limiar físico.",
            "narrative_hook": "Construir a tensão sensorial até o ápice e aplicar corte cinematográfico para preto, aterrissando no despertar com novas dinâmicas emocionais."
        })

    pacing_status = {
        "consecutive_standard_turns": consecutive_standard,
        "is_linear_fatigue": consecutive_standard >= 4,
        "available_situational_proposals": proposals,
        "recommendation": (
            f"FADIGA LINEAR DETECTADA ({consecutive_standard} turnos padrão): O Mestre deve considerar transferir a perspectiva ou quebrar a rotina escolhendo uma das {len(proposals)} estruturas situacionais sugeridas via '--scene-type <tipo>' (com foco nos NPCs ou nas forças do mundo)."
            if consecutive_standard >= 4 and proposals
            else (
                f"Sinais situacionais ativos para quebra orgânica centrada nos NPCs ou no mundo: {', '.join(p['scene_type'] for p in proposals)}. Use '--scene-type <tipo>' se desejar explorar."
                if proposals
                else "Cena padrão em tempo real recomendada para a situação imediata."
            )
        )
    }
    return pacing_status


def parse_npcs_md(npcs_path: Path) -> list:
    """Extrai perfil estruturado dos NPCs cadastrados em npcs.md (incluindo Vontade Própria, Fraquezas, Atritos e Vínculos)."""
    if not npcs_path.exists():
        return []
    text = npcs_path.read_text(encoding="utf-8")
    npcs = []
    blocks = re.split(r"^###\s+", text, flags=re.MULTILINE)
    for b in blocks[1:]:
        lines = [line.strip() for line in b.strip().splitlines() if line.strip()]
        if not lines:
            continue
        name = lines[0]
        body = "\n".join(lines[1:])
        details = " ".join(lines[1:])
        will = extract_md_field(body, ("Vontade Própria", "Agenda Autônoma", "Motivação"))
        weakness = extract_md_field(body, ("Fraquezas", "Fraqueza", "Pontos Cegos", "Ponto Cego"))
        psychology = extract_md_field(body, ("Psicologia",))
        dynamics = extract_md_field(body, ("Atritos", "Relações", "Dinâmica Social", "Laços"))
        attitude = extract_md_field(body, ("Atitude Atual",))
        faction = extract_md_field(body, ("Facção / Afiliação", "Facção", "Faccao / Afiliacao", "Faccao", "Afiliação", "Afiliacao"))
        bonds = extract_npc_bonds(body)
        is_stub = "Introduzido durante a crônica" in details or "Personagem em Cena" in details
        npcs.append({
            "name": name,
            "attitude": attitude,
            "faction": faction,
            "psychology": psychology,
            "will": will,
            "weakness": weakness,
            "dynamics": dynamics,
            "bonds": bonds,
            "is_stub": is_stub,
            "summary": details,
        })
    return npcs


def derive_npc_initiative(npc: dict) -> str:
    """Calcula a diretriz de iniciativa autônoma do NPC com base na Vontade, Psicologia e Atitude."""
    name = npc.get("name", "NPC")
    will = (npc.get("will") or "").strip()
    psych = (npc.get("psychology") or "").strip()
    att = (npc.get("attitude") or "").strip()

    impulses = []
    p_low = psych.lower()

    if "drive +3" in p_low or "drive +2" in p_low:
        impulses.append("Ação proativa agressiva (não pede permissão; dita o ritmo ou avança sobre o objetivo)")
    elif "drive -3" in p_low or "drive -2" in p_low:
        impulses.append("Postura conservadora ou hesitante (evita riscos desnecessários)")

    if "boldness +3" in p_low or "boldness +2" in p_low:
        impulses.append("Disposto a arriscar posicionamento ou escalonar a tensão imediatamente")
    elif "boldness -3" in p_low or "boldness -2" in p_low:
        impulses.append("Busca cobertura, recuo tático ou mediação defensiva")

    if "warmth +3" in p_low or "warmth +2" in p_low or "empathy +3" in p_low:
        impulses.append("Intervenção de amparo ou proteção física/moral aos companheiros")
    elif "warmth -3" in p_low or "warmth -2" in p_low or "empathy -3" in p_low:
        impulses.append("Cobrança dura, exploração de fraqueza alheia ou réplica sem filtro")

    if "composure -3" in p_low or "composure -2" in p_low:
        impulses.append("Vazamento emocional visível (impaciência, cólera ou sobressalto reativo)")

    if not impulses:
        if will:
            impulses.append("Avançar ativamente sua agenda autônoma no cenário")
        else:
            impulses.append("Manobrar por posição tática favorável ou questionar o status quo")

    drive_summary = "; ".join(impulses[:2])
    guidance = f"{name} [Iniciativa Autônoma]: {drive_summary}. Agência Proativa: Deve realizar uma ação concreta de comando, política, investigação ou deliberação com outros NPCs sem depender da permissão do protagonista."
    if will:
        guidance += f" Direção de Vontade: '{will}'."
    if att:
        guidance += f" Postura em Cena: '{att}'."
    return guidance


def upsert_npc_to_md(
    npcs_path: Path,
    name: str,
    classification: str = "",
    role: str = "",
    faction: str = "",
    attitude: str = "",
    psychology: str = "",
    will: str = "",
    weakness: str = "",
    dynamics: str = "",
    appearance: str = "",
    bonds: str = "",
    relation: str = "",
) -> dict:
    """Cadastra ou enriquece um NPC completo em npcs.md atomicamente (sem precisar editar Markdown na mão)."""
    if not npcs_path.exists():
        npcs_path.write_text("# Catálogo de NPCs & Relações de Poder\n\n", encoding="utf-8")
    text = npcs_path.read_text(encoding="utf-8")
    parts = re.split(r"(^###\s+[^\n]+)", text, flags=re.MULTILINE)
    header = parts[0]
    blocks = []
    for i in range(1, len(parts), 2):
        blocks.append([parts[i], parts[i + 1] if i + 1 < len(parts) else ""])

    field_specs = [
        ("Grau / Classificação", classification),
        ("Papel", role),
        ("Facção / Afiliação", faction),
        ("Atitude Atual", attitude),
        ("Psicologia & Tell", psychology),
        ("Vontade Própria & Agenda", will),
        ("Fraquezas & Pontos Cegos", weakness),
        ("Relação com Protagonista", relation),
        ("Vínculos & Matriz Relacional", bonds),
        ("Atritos & Laços com Outros NPCs", dynamics),
        ("Aparência & Voz", appearance),
    ]

    t_low = name.strip().lower()
    matched_heading = None
    for b in blocks:
        h_name = b[0].replace("###", "").strip()
        h_low = h_name.lower()
        if t_low == h_low or t_low in h_low or h_low in t_low:
            matched_heading = h_name
            for label, val in field_specs:
                if not val:
                    continue
                val_clean = val.strip().rstrip(".") + "."
                key_prefix = label.split("&")[0].split("/")[0].strip()
                if re.search(rf"\*\s*\*\*{re.escape(key_prefix)}[^*]*:\*\*\s*[^\n]+", b[1], re.IGNORECASE):
                    b[1] = re.sub(
                        rf"(\*\s*\*\*{re.escape(key_prefix)}[^*]*:\*\*\s*)[^\n]+",
                        rf"\g<1>{val_clean}",
                        b[1],
                        count=1,
                        flags=re.IGNORECASE,
                    )
                else:
                    b[1] = b[1].rstrip() + f"\n* **{label}:** {val_clean}\n\n"
            break

    if not matched_heading:
        matched_heading = name.strip()
        new_lines = [f"### {matched_heading}\n"]
        for label, val in field_specs:
            if val:
                val_clean = val.strip().rstrip(".") + "."
                new_lines.append(f"* **{label}:** {val_clean}\n")
        new_lines.append("\n")
        blocks.append([new_lines[0].rstrip("\n"), "\n" + "".join(new_lines[1:])])

    new_text = header + "".join(b[0] + b[1] for b in blocks)
    npcs_path.write_text(new_text, encoding="utf-8")
    return {"status": "ok", "npc_upserted": matched_heading}


def split_npc_updates(npc_updates_str: str) -> list:
    """Divide 'NPC1: texto; NPC2: texto | NPC3: texto' com segurança sem contaminar outros NPCs."""
    if not npc_updates_str:
        return []
    parts = re.split(r"\s*\|\s*|\s*;\s*(?=[A-ZÀ-Ú][A-Za-zÀ-ú0-9'&\s,\-]{1,45}:)", npc_updates_str.strip())
    pairs = []
    for p in parts:
        p = p.strip()
        if ":" not in p:
            continue
        name, attitude = p.split(":", 1)
        name, attitude = name.strip(), attitude.strip().rstrip(".")
        if name and attitude:
            pairs.append((name, attitude))
    return pairs


def apply_npc_updates_to_md(npcs_path: Path, npc_updates_str: str) -> list:
    """Atualiza cada NPC individualmente em npcs.md (ou cria a seção se o NPC for novo), garantindo integridade referencial."""
    pairs = split_npc_updates(npc_updates_str)
    if not pairs or not npcs_path.exists():
        return []

    text = npcs_path.read_text(encoding="utf-8")
    parts = re.split(r"(^###\s+[^\n]+)", text, flags=re.MULTILINE)
    header = parts[0]
    blocks = []
    for i in range(1, len(parts), 2):
        blocks.append([parts[i], parts[i + 1] if i + 1 < len(parts) else ""])

    applied = []
    for target_name, raw_update in pairs:
        matched = False
        t_low = target_name.lower()

        # Extração de subcampos (ex: "Atitude: ...; Relação: ...; Vínculos: ...")
        att_val = ""
        rel_val = ""
        bonds_val = ""
        m_rel = re.search(r"(?:relação|relacao|relação com protagonista|relacao com protagonista)\s*:\s*([^;]+)", raw_update, re.IGNORECASE)
        m_att = re.search(r"atitude\s*:\s*([^;]+)", raw_update, re.IGNORECASE)
        m_bonds = re.search(r"(?:vínculos|vinculos|laços|lacos)\s*:\s*([^;]+)", raw_update, re.IGNORECASE)

        if m_rel or m_att or m_bonds:
            if m_att:
                att_val = m_att.group(1).strip()
            if m_rel:
                rel_val = m_rel.group(1).strip()
            if m_bonds:
                bonds_val = m_bonds.group(1).strip()
        else:
            att_val = raw_update.strip()

        for b in blocks:
            heading_name = b[0].replace("###", "").strip()
            h_low = heading_name.lower()
            if t_low == h_low or t_low in h_low or h_low in t_low:
                if att_val:
                    if re.search(r"\*\s*\*\*Atitude Atual:\*\*\s*[^\n]+", b[1]):
                        b[1] = re.sub(
                            r"(\*\s*\*\*Atitude Atual:\*\*\s*)[^\n]+",
                            rf"\g<1>{att_val}.",
                            b[1],
                            count=1,
                        )
                    else:
                        b[1] = f"\n* **Atitude Atual:** {att_val}." + b[1]
                    applied.append(f"NPC {heading_name} (Atitude) -> {att_val}")

                if rel_val:
                    if re.search(r"\*\s*\*\*Relação com Protagonista:\*\*\s*[^\n]+", b[1], re.IGNORECASE):
                        b[1] = re.sub(
                            r"(\*\s*\*\*Relação com Protagonista:\*\*\s*)[^\n]+",
                            rf"\g<1>{rel_val}.",
                            b[1],
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:
                        b[1] = b[1].rstrip() + f"\n* **Relação com Protagonista:** {rel_val}.\n\n"
                    applied.append(f"NPC {heading_name} (Relação com Protagonista) -> {rel_val}")

                if bonds_val:
                    if re.search(r"\*\s*\*\*Vínculos & Matriz Relacional:\*\*\s*[^\n]+", b[1], re.IGNORECASE):
                        b[1] = re.sub(
                            r"(\*\s*\*\*Vínculos & Matriz Relacional:\*\*\s*)[^\n]+",
                            rf"\g<1>{bonds_val}.",
                            b[1],
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:
                        b[1] = b[1].rstrip() + f"\n* **Vínculos & Matriz Relacional:** {bonds_val}.\n\n"
                    applied.append(f"NPC {heading_name} (Vínculos) -> {bonds_val}")

                matched = True
                break

        if not matched:
            new_heading = f"### {target_name}"
            new_body = (
                f"\n* **Grau / Classificação:** Personagem em Cena\n"
                f"* **Papel:** Introduzido durante a crônica.\n"
                f"* **Atitude Atual:** {att_val or raw_update}.\n"
            )
            if rel_val:
                new_body += f"* **Relação com Protagonista:** {rel_val}.\n"
            if bonds_val:
                new_body += f"* **Vínculos & Matriz Relacional:** {bonds_val}.\n"
            new_body += "\n"
            blocks.append([new_heading, new_body])
            applied.append(f"NPC Novo Cadastrado ({target_name}) -> {att_val or raw_update}")

    new_text = header + "".join(b[0] + b[1] for b in blocks)
    npcs_path.write_text(new_text, encoding="utf-8")
    return applied
