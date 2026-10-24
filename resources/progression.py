"""resources/progression.py: Domínio e mutações de XP, níveis e pontos do protagonista."""

from __future__ import annotations

import re
from pathlib import Path

from adapters.persistence.files import atomic_write_text
from rulesets.progression import (
    DEFAULT_BASE_STEP,
    DEFAULT_STAT_CEILING,
    calculate_level_from_xp,
    calculate_level_up_bonuses,
)


def parse_progression_from_ficha(ficha_path: Path) -> dict:
    """Extrai os dados de progressão e nível do protagonista sob a seção '### Progressão' de ficha.md."""
    default_prog = {
        "level": 1,
        "xp": 0,
        "next_threshold": 250,
        "attribute_points": 0,
        "ability_points": 0,
    }
    if not ficha_path.exists():
        return default_prog
    text = ficha_path.read_text(encoding="utf-8")
    m_sec = re.search(r"###\s*Progressão[^\n]*\n(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        return default_prog
    sec_text = m_sec.group(1)

    m_lvl = re.search(r"\*\s*\*\*Nível:\*\*\s*(\d+)", sec_text, re.IGNORECASE)
    m_xp = re.search(r"\*\s*\*\*(?:Experiência\s*\(XP\)|XP):\*\*\s*(\d+)", sec_text, re.IGNORECASE)
    m_next = re.search(r"\*\s*\*\*Próximo Nível:\*\*\s*(\d+)", sec_text, re.IGNORECASE)
    m_attr = re.search(r"\*\s*\*\*Pontos de Atributo:\*\*\s*(\d+)", sec_text, re.IGNORECASE)
    m_abil = re.search(r"\*\s*\*\*Pontos de Habilidade:\*\*\s*(\d+)", sec_text, re.IGNORECASE)

    if m_lvl:
        default_prog["level"] = int(m_lvl.group(1))
    if m_xp:
        default_prog["xp"] = int(m_xp.group(1))
    if m_next:
        default_prog["next_threshold"] = int(m_next.group(1))
    if m_attr:
        default_prog["attribute_points"] = int(m_attr.group(1))
    if m_abil:
        default_prog["ability_points"] = int(m_abil.group(1))

    return default_prog


def update_progression_in_ficha(
    ficha_path: Path,
    xp_add: int = 0,
    attribute_points_delta: int = 0,
    ability_points_delta: int = 0,
    base_step: int = DEFAULT_BASE_STEP,
) -> dict:
    """Atualiza XP, recalcula nível/limiares e adiciona pontos/vitais por subida de nível em ficha.md."""
    if not ficha_path.exists():
        return {"error": f"Arquivo {ficha_path} não encontrado"}

    text = ficha_path.read_text(encoding="utf-8")
    cur_prog = parse_progression_from_ficha(ficha_path)

    old_level = cur_prog["level"]
    new_xp = max(0, cur_prog["xp"] + xp_add)
    new_level, next_thresh = calculate_level_from_xp(new_xp, base_step=base_step)

    bonuses = calculate_level_up_bonuses(old_level, new_level)
    new_attr_points = max(0, cur_prog["attribute_points"] + bonuses["attribute_points"] + attribute_points_delta)
    new_abil_points = max(0, cur_prog["ability_points"] + bonuses["ability_points"] + ability_points_delta)

    if new_level > old_level:
        hp_add = bonuses["hp_bonus"]
        sta_add = bonuses["stamina_bonus"]
        ce_add = bonuses["energy_bonus"]

        m_v_sec = re.search(r"(###\s*Vitais[^\n]*\n)(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
        if m_v_sec:
            header_v = m_v_sec.group(1)
            v_content = m_v_sec.group(2)

            def repl_vital(m_vit):
                lbl = m_vit.group(1)
                cur_v = int(m_vit.group(2))
                mx_v = int(m_vit.group(3))
                low = lbl.lower()
                bonus = 0
                if "hp" in low or "vida" in low or "pv" in low:
                    bonus = hp_add
                elif "stamina" in low or "fôlego" in low or "folego" in low or "fadiga" in low or "vigor" in low:
                    bonus = sta_add
                elif "ce" in low or "energia" in low or "mp" in low or "mana" in low:
                    bonus = ce_add
                return f"* **{lbl}:** {cur_v + bonus} / {mx_v + bonus}"

            new_v_content = re.sub(r"\*\s*\*\*([^:*]+):\*\*\s*(\d+)\s*/\s*(\d+)", repl_vital, v_content)
            text = text[: m_v_sec.start()] + header_v + new_v_content + text[m_v_sec.end() :]

    prog_block = (
        f"### Progressão\n"
        f"* **Nível:** {new_level}\n"
        f"* **Experiência (XP):** {new_xp}\n"
        f"* **Próximo Nível:** {next_thresh}\n"
        f"* **Pontos de Atributo:** {new_attr_points}\n"
        f"* **Pontos de Habilidade:** {new_abil_points}\n"
    )

    m_p_sec = re.search(r"###\s*Progressão[^\n]*\n.*?(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if m_p_sec:
        text = text[: m_p_sec.start()] + prog_block + text[m_p_sec.end() :]
    else:
        m_ins = re.search(r"(###\s*(?:Habilidades|Marcos|Equipamento))", text, re.IGNORECASE)
        if m_ins:
            ins_pos = m_ins.start()
            text = text[:ins_pos] + prog_block + "\n" + text[ins_pos:]
        else:
            text += f"\n\n{prog_block}"

    atomic_write_text(ficha_path, text)
    return {
        "old_level": old_level,
        "new_level": new_level,
        "xp_added": xp_add,
        "total_xp": new_xp,
        "next_threshold": next_thresh,
        "attribute_points": new_attr_points,
        "ability_points": new_abil_points,
        "level_up": (new_level > old_level),
        "bonuses": bonuses,
    }


def spend_attribute_point_in_ficha(
    ficha_path: Path,
    stat_code: str,
    stat_ceiling: int = DEFAULT_STAT_CEILING,
    parse_ficha_fn: Any = None,
) -> dict:
    """Gasta 1 Ponto de Atributo e incrementa o atributo escolhido em ficha.md."""
    if not ficha_path.exists():
        return {"error": f"Arquivo {ficha_path} não encontrado"}

    cur_prog = parse_progression_from_ficha(ficha_path)
    if cur_prog["attribute_points"] < 1:
        return {"error": "Sem Pontos de Atributo disponíveis na ficha"}

    clean_stat = stat_code.upper().strip()
    from resources.sheet import parse_ficha_md

    parse_fn = parse_ficha_fn or parse_ficha_md
    ficha_data = parse_fn(ficha_path)
    cur_val = ficha_data["stats"].get(clean_stat)
    if cur_val is None:
        return {"error": f"Atributo '{clean_stat}' não encontrado em ficha.md"}
    if cur_val >= stat_ceiling:
        return {"error": f"Atributo '{clean_stat}' já atingiu o teto permitido ({stat_ceiling})"}

    text = ficha_path.read_text(encoding="utf-8")
    m_s_sec = re.search(r"(###\s*Atributos[^\n]*\n)(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_s_sec:
        return {"error": "Seção '### Atributos' não encontrada em ficha.md"}

    sec_header = m_s_sec.group(1)
    sec_content = m_s_sec.group(2)

    stat_pat = re.compile(rf"(\*\s*\*\*{clean_stat}\b[^*]*\*\*\s*)(\d+)", re.IGNORECASE)
    m_stat = stat_pat.search(sec_content)
    if not m_stat:
        return {"error": f"Linha do atributo '{clean_stat}' não localizada na seção de atributos"}

    new_val = cur_val + 1
    new_sec_content = stat_pat.sub(rf"\g<1>{new_val}", sec_content, count=1)
    text = text[: m_s_sec.start()] + sec_header + new_sec_content + text[m_s_sec.end() :]

    atomic_write_text(ficha_path, text)
    res = update_progression_in_ficha(ficha_path, xp_add=0, attribute_points_delta=-1)
    return {
        "stat": clean_stat,
        "old_value": cur_val,
        "new_value": new_val,
        "remaining_points": res["attribute_points"],
    }


def spend_ability_point_in_ficha(
    ficha_path: Path,
    ability_name_desc: str,
    training_context: str,
    upsert_feature_fn: Any = None,
) -> dict:
    """Gasta 1 Ponto de Habilidade e registra a nova habilidade em ficha.md."""
    if not ficha_path.exists():
        return {"error": f"Arquivo {ficha_path} não encontrado"}

    if not training_context.strip():
        return {"error": "A aquisição de habilidade exige a flag --training com justificativa diegética"}

    cur_prog = parse_progression_from_ficha(ficha_path)
    if cur_prog["ability_points"] < 1:
        return {"error": "Sem Pontos de Habilidade disponíveis na ficha"}

    from resources.sheet import upsert_ficha_feature

    fn = upsert_feature_fn or upsert_ficha_feature
    fn(ficha_path, ability=ability_name_desc.strip())

    res = update_progression_in_ficha(ficha_path, xp_add=0, ability_points_delta=-1)
    return {
        "ability": ability_name_desc.strip(),
        "training": training_context.strip(),
        "remaining_points": res["ability_points"],
    }


__all__ = [
    "parse_progression_from_ficha",
    "spend_ability_point_in_ficha",
    "spend_attribute_point_in_ficha",
    "update_progression_in_ficha",
]
