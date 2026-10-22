"""council.gm.py: Resolução determinística de dados e cálculo de custos de vitais.

Atua como fachada de coordenação e reexportador do ruleset padrão (rulesets.d20_3gates).
"""

import re
from council.ssot import normalize_vital_key
from rulesets.d20_3gates import (
    DC_LADDER,
    extract_npc_contest_modifier,
    roll_3_gates,
    roll_contest,
)

__all__ = [
    "DC_LADDER",
    "extract_npc_contest_modifier",
    "parse_cost_string",
    "roll_3_gates",
    "roll_contest",
]


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
