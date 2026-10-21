"""council.gm.py: Resolução determinística de dados (Modelo de 3 Portões) e cálculo de custos de vitais."""

import random
import re
from council.ssot import normalize_vital_key


def roll_3_gates(label: str, variant: str = "normal", dc: int = 15, stat_name: str = "", stat_val: int = 10):
    """Executa o Modelo de 3 Portões determinístico com modificador de atributo e comparação com DC."""
    mod = (stat_val - 10) // 2 if stat_name else 0
    if variant in ("advantage", "adv"):
        r1, r2 = random.randint(1, 20), random.randint(1, 20)
        nat = max(r1, r2)
        gate_raw = f"2d20kh1 [{r1}, {r2}] -> {nat}"
    elif variant in ("disadvantage", "disadv"):
        r1, r2 = random.randint(1, 20), random.randint(1, 20)
        nat = min(r1, r2)
        gate_raw = f"2d20kl1 [{r1}, {r2}] -> {nat}"
    else:
        nat = random.randint(1, 20)
        gate_raw = f"1d20 [{nat}]"

    total = nat + mod
    mod_str = f" + {stat_name}({mod:+d})" if stat_name else ""

    if nat == 1 or total <= dc - 5:
        tier = "Catástrofe (Falha Crítica — reversão severa, dano direto ou perda tática grave)"
    elif nat == 20 or total >= dc + 5:
        tier = "Dádiva / Triunfo Crítico (Sucesso Lendário — impacto devastador e vantagem tática)"
    elif total >= dc:
        tier = "Sucesso Pleno (Alcança o objetivo sem custos extras além do esforço normal)"
    elif total >= dc - 4:
        tier = "Sucesso com Custo (Alcança parcialmente ou com atrito imediato: perda de recurso ou posição)"
    else:
        tier = "Falha (Revés direto — a ação falha e a ameaça avança)"

    return {
        "natural": nat,
        "modifier": mod,
        "stat": stat_name or "Nenhum",
        "total": total,
        "dc": dc,
        "variant": variant,
        "tier": tier,
        "summary": f"{gate_raw}{mod_str} = {total} vs DC {dc} -> {tier}",
    }


def extract_npc_contest_modifier(npc: dict, stat_requested: str = "") -> tuple:
    """Extrai agnosticamente o modificador do NPC para a disputa a partir da sua Psicologia (Hexágono) ou Grau."""
    psych = npc.get("psychology", "")
    req_clean = stat_requested.strip().upper() if stat_requested else ""

    # 1. Se foi solicitada uma estatística específica (ex: 'COMPOSURE', 'DRIVE', 'BOLDNESS', 'DILIGENCE', 'WARMTH', 'EMPATHY')
    if req_clean:
        m = re.search(rf"\b{re.escape(req_clean)}\b\s*([+-]\s*\d+)", psych, re.IGNORECASE)
        if m:
            val = int(m.group(1).replace(" ", ""))
            return stat_requested.title(), val

    # 2. Se não foi especificado ou não bateu, extrai os traços do Hexágono e escolhe o mais relevante
    hexagon_matches = re.findall(r"\b(Drive|Diligence|Boldness|Warmth|Empathy|Composure)\s*([+-]\s*\d+)", psych, re.IGNORECASE)
    if hexagon_matches:
        sorted_traits = sorted(hexagon_matches, key=lambda x: int(x[1].replace(" ", "")), reverse=True)
        best_trait, best_val_str = sorted_traits[0]
        return best_trait.title(), int(best_val_str.replace(" ", ""))

    # 3. Fallback agnóstico baseado em Grau / Classificação (se for veterano, líder, comandante, dá +2; caso contrário +0)
    role = (npc.get("classification") or npc.get("role") or "").lower()
    if any(k in role for k in ["líder", "lider", "comandante", "alfa", "inquisitor", "mestre", "elite", "grau 1", "grau especial"]):
        return "Grau Elite", 2
    return "Base", 0


def roll_contest(
    pc_name: str,
    pc_stat_name: str,
    pc_stat_val: int,
    npc_name: str,
    npc_stat_name: str,
    npc_stat_mod: int,
    pc_variant: str = "normal",
    npc_variant: str = "normal",
    p1_is_npc: bool = False,
) -> dict:
    """Executa uma Disputa Oposta de Dados (PC vs NPC ou NPC vs NPC) sob o Framework Universal de 3 Portões (100% agnóstico)."""
    # 1. Rolagem do Participante 1 (PC ou NPC 1)
    if p1_is_npc:
        p1_mod = pc_stat_val
    else:
        p1_mod = (pc_stat_val - 10) // 2 if pc_stat_name else 0

    if pc_variant in ("advantage", "adv"):
        r1, r2 = random.randint(1, 20), random.randint(1, 20)
        p1_nat = max(r1, r2)
        p1_raw = f"2d20kh1 [{r1}, {r2}] -> {p1_nat}"
    elif pc_variant in ("disadvantage", "disadv"):
        r1, r2 = random.randint(1, 20), random.randint(1, 20)
        p1_nat = min(r1, r2)
        p1_raw = f"2d20kl1 [{r1}, {r2}] -> {p1_nat}"
    else:
        p1_nat = random.randint(1, 20)
        p1_raw = f"1d20 [{p1_nat}]"

    p1_total = p1_nat + p1_mod
    p1_mod_str = f" + {pc_stat_name}({p1_mod:+d})" if pc_stat_name else ""

    # 2. Rolagem do Participante 2 (NPC ou NPC 2)
    if npc_variant in ("advantage", "adv"):
        r1, r2 = random.randint(1, 20), random.randint(1, 20)
        p2_nat = max(r1, r2)
        p2_raw = f"2d20kh1 [{r1}, {r2}] -> {p2_nat}"
    elif npc_variant in ("disadvantage", "disadv"):
        r1, r2 = random.randint(1, 20), random.randint(1, 20)
        p2_nat = min(r1, r2)
        p2_raw = f"2d20kl1 [{r1}, {r2}] -> {p2_nat}"
    else:
        p2_nat = random.randint(1, 20)
        p2_raw = f"1d20 [{p2_nat}]"

    p2_total = p2_nat + npc_stat_mod
    p2_mod_str = f" + {npc_stat_name}({npc_stat_mod:+d})" if npc_stat_name else ""

    delta = p1_total - p2_total
    dispute_type = "DISPUTA NPC vs NPC" if p1_is_npc else "DISPUTA PC vs NPC"

    # 3. Resolução dos 3 Portões de Disputa
    if p1_is_npc:
        # Disputa entre dois NPCs (Horizontal / Triangulação Autônoma)
        if p1_nat == 20 or (delta >= 8 and p2_nat != 20):
            tier = f"Dádiva / Triunfo Esmagador de {pc_name}"
            outcome_desc = f"{pc_name} subjuga e supera {npc_name} com autoridade categórica. {npc_name} perde a posição, recua desestabilizado(a) ou é forçado(a) a engolir os termos."
            cost_guide = "Disputa interna de NPCs: sem custo mecânico direto ao protagonista. Altere a balança de poder e os alinhamentos dos presentes."
            npc_mandate = f"{pc_name} VENCEU categoricamente sobre {npc_name}. Deve liderar a cena e impor seus termos; {npc_name} deve demonstrar recuo forçado ou choque."
        elif p1_nat == 1 or p2_nat == 20 or delta <= -8:
            tier = f"Catástrofe de {pc_name} / Triunfo Esmagador de {npc_name}"
            outcome_desc = f"{npc_name} desferiu réplica devastadora e esmagou a iniciativa de {pc_name}. {pc_name} é colocado(a) em posição de fraqueza perante todos."
            cost_guide = "Disputa interna de NPCs: sem custo mecânico direto ao protagonista. Altere a balança de poder e os alinhamentos dos presentes."
            npc_mandate = f"{npc_name} VENCEU categoricamente sobre {pc_name}. Deve liderar a cena e impor sua Vontade Própria; {pc_name} é forçado(a) a recuar."
        elif delta > 0:
            if delta <= 3:
                tier = f"Vitória Tensa de {pc_name} (Sucesso com Atrito)"
                outcome_desc = f"{pc_name} vence a disputa contra {npc_name}, mas {npc_name} resiste tenazmente e mantém o atrito vivo."
                cost_guide = "Disputa entre NPCs: preserve a tensão latente entre ambos."
                npc_mandate = f"{pc_name} prevalece no choque imediato, mas {npc_name} mantém resistência e postura desafiadora."
            else:
                tier = f"Vitória Sólida de {pc_name}"
                outcome_desc = f"{pc_name} prevalece sobre {npc_name}, quebrando sua guarda, influência ou argumento."
                cost_guide = "Disputa entre NPCs: {pc_name} assume a dianteira da ação na cena."
                npc_mandate = f"{pc_name} assume a liderança tática ou moral imediata sobre {npc_name}."
        elif delta < 0:
            if delta >= -3:
                tier = f"Resistência Vitoriosa de {npc_name} (Revés com Atrito)"
                outcome_desc = f"{npc_name} frustra o ímpeto de {pc_name}, mantém sua guarda e contra-ataca, forçando {pc_name} a hesitar."
                cost_guide = "Disputa entre NPCs: preserve a tensão latente entre ambos."
                npc_mandate = f"{npc_name} ganha vantagem tática/moral contra {pc_name} e passa a pressionar."
            else:
                tier = f"Vitória Sólida de {npc_name}"
                outcome_desc = f"{npc_name} supera a iniciativa de {pc_name}, revertendo a pressão e ditando o ritmo imediato."
                cost_guide = "Disputa entre NPCs: {npc_name} assume a dianteira da ação na cena."
                npc_mandate = f"{npc_name} subjuga a manobra de {pc_name} e assume o controle da cena."
        else:  # delta == 0
            tier = "Impasse Tenso entre NPCs"
            outcome_desc = f"{pc_name} e {npc_name} colidem em equilíbrio perfeito. Forças, argumentos ou posições travadas sem concessões mútuas."
            cost_guide = "Disputa entre NPCs: elevação mútua de tensão; nenhum dos dois recua."
            npc_mandate = f"{pc_name} e {npc_name} encaram-se em choque de vontades irreconciliável; a tensão entre as facções sobe ao máximo."
    else:
        # Disputa Protagonista vs NPC
        if p1_nat == 20 or (delta >= 8 and p2_nat != 20):
            tier = "Dádiva / Triunfo Esmagador do Protagonista"
            outcome_desc = f"{pc_name} supera {npc_name} com domínio absoluto. O NPC sofre desestabilização total, perde a posição ou cede incondicionalmente."
            cost_guide = "Nenhum custo para o PC; imponha recuo, perda de recurso ou choque tático direto ao NPC."
            npc_mandate = f"{npc_name} foi superado(a) categoricamente. Deve demonstrar orgulho ferido, recuo forçado ou espanto diante do desfecho."
        elif p1_nat == 1 or p2_nat == 20 or delta <= -8:
            tier = "Catástrofe do Protagonista / Triunfo do NPC"
            outcome_desc = f"{npc_name} reage com vigor devastador e subjuga a manobra de {pc_name}. O NPC impõe sua Vontade, dita os termos ou desfere contra-ataque severo."
            cost_guide = "OBRIGATÓRIO deduzir recursos vitais do PC no commit (--cost) e narrar o NPC tomando a dianteira da cena."
            npc_mandate = f"{npc_name} VENCEU a disputa contra o protagonista! DEVE tomar a iniciativa imediata na narrativa, ditando termos e desferindo seu contra-ataque com autoridade."
        elif delta > 0:
            if delta <= 3:
                tier = "Vitória Tensa do Protagonista (Sucesso com Atrito)"
                outcome_desc = f"{pc_name} vence a disputa imediata, mas {npc_name} resiste com tenacidade, cobra um preço em atrito ou manobra para não perder o controle."
                cost_guide = "Deduza recursos moderados (Stamina/Energia) de ambos ou aplique concessão tática ao NPC."
                npc_mandate = f"{npc_name} cedeu terreno, mas não se rendeu. Mantém postura desafiadora e busca um novo ângulo tático."
            else:
                tier = "Vitória Sólida do Protagonista"
                outcome_desc = f"{pc_name} prevalece sobre {npc_name} na disputa, quebrando sua guarda, resistência ou argumento."
                cost_guide = "Avance o objetivo do protagonista; o NPC é forçado a recuar ou reconsiderar sua postura."
                npc_mandate = f"{npc_name} recua sob pressão e é forçado(a) a engolir a derrota imediata sem perder sua dignidade."
        elif delta < 0:
            if delta >= -3:
                tier = "Resistência Vitoriosa do NPC (Revés com Custo para o PC)"
                outcome_desc = f"{npc_name} frustra a investida de {pc_name}, mantém sua postura e contra-ataca verbal ou fisicamente, forçando o herói a recuar."
                cost_guide = "Deduza recursos (Stamina/Vigor) do PC e narre o NPC ganhando vantagem de posicionamento."
                npc_mandate = f"{npc_name} segurou o choque e ganhou vantagem. Deve pressionar o protagonista ativamente, cobrando postura ou atacando."
            else:
                tier = "Vitória Sólida do NPC (Revés Tático)"
                outcome_desc = f"{npc_name} supera a iniciativa de {pc_name}, revertendo a pressão e ditando as regras do confronto imediato."
                cost_guide = "Deduza recursos vitais do PC no commit e coloque {pc_name} em posição de desvantagem."
                npc_mandate = f"{npc_name} VENCEU o confronto imediato. DEVE exercer sua Vontade Própria de forma proativa contra {pc_name}."
        else:  # delta == 0
            tier = "Impasse Tenso (Empate Absoluto)"
            outcome_desc = f"{pc_name} e {npc_name} colidem em equilíbrio perfeito de forças. Espadas travadas ou vontades colidindo sem recuo."
            cost_guide = "Ambos os lados sofrem desgaste imediato (Stamina -2) e a tensão se eleva para o próximo turno."
            npc_mandate = f"{npc_name} trava forças com {pc_name} sem ceder um milímetro. Ambos se encaram no limite da tensão."

    result = {
        "is_contest": True,
        "is_npc_vs_npc": p1_is_npc,
        "p1": {
            "name": pc_name,
            "is_npc": p1_is_npc,
            "natural": p1_nat,
            "stat": pc_stat_name,
            "mod": p1_mod,
            "total": p1_total,
            "roll_raw": f"{p1_raw}{p1_mod_str} = {p1_total}",
        },
        "p2": {
            "name": npc_name,
            "is_npc": True,
            "natural": p2_nat,
            "stat": npc_stat_name,
            "mod": npc_stat_mod,
            "total": p2_total,
            "roll_raw": f"{p2_raw}{p2_mod_str} = {p2_total}",
        },
        "delta": delta,
        "tier": tier,
        "outcome": outcome_desc,
        "cost_directive": cost_guide,
        "npc_reaction_mandate": npc_mandate,
        "winner": pc_name if delta > 0 else (npc_name if delta < 0 else "Impasse"),
        "summary": f"[{dispute_type}] {pc_name}: {p1_total} ({p1_raw}{p1_mod_str}) vs {npc_name}: {p2_total} ({p2_raw}{p2_mod_str}) -> Delta {delta:+d} -> {tier}",
    }

    if not p1_is_npc:
        result["pc"] = result["p1"]
        result["npc"] = result["p2"]

    return result


def parse_cost_string(cost_str: str, vitals_dict: dict = None):
    """Parser agnóstico de custos: aceita qualquer recurso de ficha.md ('Recurso -3' ou '+1 Recurso') e tempo ('time +5m')."""
    deltas = {}
    time_mins = 0
    if not cost_str:
        return deltas, time_mins

    # 1. Minutos/horas/dias explícitos
    for m_t in re.finditer(r"time\s*\+\s*(\d+)\s*([mhd]?)", cost_str, re.IGNORECASE):
        val, unit = int(m_t.group(1)), (m_t.group(2) or "m").lower()
        time_mins += val * (60 if unit == "h" else (1440 if unit == "d" else 1))
    if time_mins == 0:
        m_nat = re.search(r"(\d+)\s*(minutos?|mins?|horas?|dias?)\s+decorridos?", cost_str, re.IGNORECASE)
        if m_nat:
            val, unit = int(m_nat.group(1)), m_nat.group(2).lower()
            time_mins += val * (60 if unit.startswith("hora") else (1440 if unit.startswith("dia") else 1))

    # Remove parênteses como (27/30) e blocos de tempo para não confundir o parser de recursos
    cleaned = re.sub(r"\([^)]*\)", "", cost_str)
    cleaned = re.sub(r"time\s*\+\s*\d+\s*[mhd]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\d+\s*(?:minutos?|mins?|horas?|dias?)\s+decorridos?", "", cleaned, flags=re.IGNORECASE)

    # Constrói padrões dinâmicos a partir dos recursos da ficha + sinônimos universais
    known_tokens = {"hp", "vida", "pv", "saúde", "saude", "stamina", "fôlego", "folego", "fadiga", "sta", "vigor", "ce", "mp", "energia", "mana", "ea", "pe", "san", "sanidade", "humanidade"}
    if vitals_dict:
        for k, v in vitals_dict.items():
            known_tokens.add(k.lower())
            if v.get("short"):
                known_tokens.add(v["short"].lower())
            if v.get("abbr"):
                known_tokens.add(v["abbr"].lower())

    token_pattern = "|".join(sorted((re.escape(t) for t in known_tokens if t), key=len, reverse=True))

    # Formato A: 'Recurso -3', 'Stamina +2'
    for m in re.finditer(rf"\b({token_pattern})\s*([+-]\s*\d+)", cleaned, re.IGNORECASE):
        k = normalize_vital_key(m.group(1), vitals_dict)
        v = int(m.group(2).replace(" ", ""))
        deltas[k] = v

    # Formato B: '+1 Recurso', '-3 Stamina'
    for m in re.finditer(rf"([+-]\s*\d+)\s*({token_pattern})\b", cleaned, re.IGNORECASE):
        k = normalize_vital_key(m.group(2), vitals_dict)
        v = int(m.group(1).replace(" ", ""))
        if k not in deltas:
            deltas[k] = v

    return deltas, time_mins
