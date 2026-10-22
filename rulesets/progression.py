"""rulesets/progression.py: Motor de Progressão e Economia de Experiência (XP).

Implementa a tabela de concessão determinística, curva quadrática de nível,
cálculo de pontos de atributo/habilidade e resolução com suporte a overrides.
Totalmente em Python Standard Library (sem dependências externas).
"""

from typing import Dict, Any, List, Optional, Tuple

XP_GRANT_TABLE: Dict[str, int] = {
    "obj_main": 40,
    "obj_side": 15,
    "quest_side": 60,
    "quest_main": 150,
    "quest_personal": 50,
    "clock_resolved": 40,
    "clock_breached": 30,
    "arc_milestone": 80,
    "discovery": 25,
    "adversity": 20,
    "turn": 0,
}

DEFAULT_QUEST_REWARDS: Dict[str, int] = {
    "MAIN": 150,
    "SIDE": 60,
    "PERSONAL": 50,
    "FACTION": 50,
}

DEFAULT_BASE_STEP: int = 250
DEFAULT_STAT_CEILING: int = 20


def get_base_step_from_overrides(overrides: Optional[List[Dict[str, Any]]] = None) -> int:
    """Extrai o modificador base da curva de XP a partir dos overrides de regras.md."""
    if not overrides:
        return DEFAULT_BASE_STEP
    for ov in overrides:
        if ov.get("type") == "xp_curve" and ov.get("target") in ("level_threshold", "base_step"):
            try:
                return int(ov.get("value", DEFAULT_BASE_STEP))
            except (ValueError, TypeError):
                return DEFAULT_BASE_STEP
    return DEFAULT_BASE_STEP


def get_stat_ceiling_from_overrides(overrides: Optional[List[Dict[str, Any]]] = None) -> int:
    """Extrai o teto máximo de atributos a partir dos overrides de regras.md."""
    if not overrides:
        return DEFAULT_STAT_CEILING
    for ov in overrides:
        if ov.get("type") == "stat_ceiling" or (ov.get("type") == "threshold_shift" and ov.get("target") == "stat_ceiling"):
            try:
                return int(ov.get("value", DEFAULT_STAT_CEILING))
            except (ValueError, TypeError):
                return DEFAULT_STAT_CEILING
    return DEFAULT_STAT_CEILING


def calculate_level_threshold(level: int, base_step: int = DEFAULT_BASE_STEP) -> int:
    """Calcula o XP total cumulativo necessário para atingir o nível `level`.
    
    Fórmula canônica: T(L) = base_step * (L - 1) * L / 2
    Nível 1: 0 XP
    Nível 2: 250 XP
    Nível 3: 750 XP
    Nível 4: 1500 XP
    Nível 5: 2500 XP
    Nível 10: 11250 XP
    """
    if level <= 1:
        return 0
    return int(base_step * (level - 1) * level // 2)


def calculate_level_from_xp(total_xp: int, base_step: int = DEFAULT_BASE_STEP) -> Tuple[int, int]:
    """Determina o nível atual e o próximo limiar a partir do total acumulado de XP.
    
    Retorna: (current_level, next_threshold)
    """
    base_step = max(1, base_step)
    if total_xp < 0:
        total_xp = 0
    lvl = 1
    while total_xp >= calculate_level_threshold(lvl + 1, base_step):
        lvl += 1
    next_thresh = calculate_level_threshold(lvl + 1, base_step)
    return lvl, next_thresh


def evaluate_xp_gain(
    source_code: str,
    amount: Optional[int] = None,
    overrides: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Resolve a quantidade de XP a conceder para um código de fonte ou valor direto.
    
    Aplica modificadores de overrides se especificado.
    """
    clean_code = (source_code or "").strip().lower()
    base_val = XP_GRANT_TABLE.get(clean_code, 0)
    if amount is not None and amount > 0:
        base_val = amount

    if overrides:
        for ov in overrides:
            if ov.get("type") == "xp_multiplier":
                try:
                    mult = float(ov.get("value", 1.0))
                    base_val = int(base_val * mult)
                except (ValueError, TypeError):
                    pass
    return max(0, base_val)


def calculate_level_up_bonuses(old_level: int, new_level: int) -> Dict[str, int]:
    """Calcula os pontos e incrementos vitais ganhos na transição de nível.
    
    +1 Ponto de Atributo por nível avançado.
    +2 HP máximo por nível avançado.
    +1 Stamina máxima por nível avançado.
    +1 Energia/Mana máxima por nível avançado.
    +1 Ponto de Habilidade a cada 2 níveis (níveis pares atingidos).
    """
    if new_level <= old_level:
        return {
            "attribute_points": 0,
            "ability_points": 0,
            "hp_bonus": 0,
            "stamina_bonus": 0,
            "energy_bonus": 0,
        }
    levels_gained = new_level - old_level
    ability_pts = sum(1 for lvl in range(old_level + 1, new_level + 1) if lvl % 2 == 0)
    return {
        "attribute_points": levels_gained,
        "ability_points": ability_pts,
        "hp_bonus": levels_gained * 2,
        "stamina_bonus": levels_gained * 1,
        "energy_bonus": levels_gained * 1,
    }
