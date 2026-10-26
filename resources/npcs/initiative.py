"""resources/npcs/initiative.py: Inteligência social, vínculos relacionais e iniciativa autônoma de NPCs."""

from __future__ import annotations

import re
from typing import Any, Dict, List


def find_scene_relational_tensions(present_names: list[str], all_npcs: list[dict[str, Any]], protag_name: str = "") -> list[str]:
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


def extract_epistemic_forbidden_terms(ficha_text: str, mundo_text: str, diario_text: str = "") -> list[str]:
    """Extrai dinamicamente da ficha os termos da identidade privada, segredos e origem do protagonista ausentes do mundo público."""
    if not ficha_text:
        return []

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
                title, _ = line_s.split(":", 1)
                private_corpus.append(title.strip().replace("**", ""))

    m_sec = re.search(r"\*\s*\*\*Segredos[^*]*:\*\*\s*([^\n]+)", ficha_text, re.IGNORECASE)
    if m_sec:
        private_corpus.append(m_sec.group(1))

    full_private_text = " ".join(private_corpus)
    if not full_private_text:
        return []

    hyphenated = re.findall(r"\b[A-Za-zÀ-ú]{3,}(?:-[A-Za-zÀ-ú]{2,})+\b", full_private_text)
    capitalized = re.findall(r"\b[A-ZÀ-Ú][a-zA-ZÀ-ú]{3,}\b", full_private_text)
    candidates = set(hyphenated + capitalized)

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

    m_clean = re.sub(r"^#[^\n]+", "", mundo_text) if mundo_text else ""
    m_low = m_clean.lower()
    forbidden = []

    for cand in candidates:
        c_low = cand.lower().strip()
        if c_low in stopwords or len(c_low) < 4:
            continue
        if c_low not in m_low:
            forbidden.append(cand.strip())

    return sorted(list(set(forbidden)))


def derive_npc_initiative(npc: dict[str, Any]) -> str:
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


__all__ = [
    "derive_npc_initiative",
    "extract_epistemic_forbidden_terms",
    "find_scene_relational_tensions",
]
