"""resources/sheet.py: Domínio e parsers da ficha do protagonista (ficha.md)."""

from __future__ import annotations

import re
from pathlib import Path

from adapters.persistence.files import atomic_write_text
from resources.progression import parse_progression_from_ficha


def normalize_vital_key(raw: str, vitals_dict: dict = None) -> str:
    """Normaliza o nome de qualquer recurso vital dinamicamente a partir da ficha.md ou sinônimos universais."""
    low = raw.strip().lower()
    if low in ("hp", "vida", "pv", "saúde", "saude"):
        base = "hp"
    elif low in ("stamina", "folego", "fôlego", "fadiga", "sta", "vigor"):
        base = "stamina"
    elif low in ("ce", "mp", "energia", "mana", "ea", "pe", "magia"):
        base = "ce"
    else:
        base = low

    if vitals_dict:
        if base in vitals_dict:
            return base
        for k, v in vitals_dict.items():
            lbl_low = v["label"].lower()
            short_low = lbl_low.split("(")[0].strip()
            m_abbr = re.search(r"\(([^)]+)\)", lbl_low)
            abbr_low = m_abbr.group(1).strip() if m_abbr else ""
            if low in (k, lbl_low, short_low, abbr_low):
                return k
    return base


def parse_ficha_md(ficha_path: Path) -> dict:
    """Extrai dinamicamente nome, recursos vitais e atributos de ficha.md."""
    data = {
        "name": "Protagonista",
        "vitals": {},
        "stats": {},
        "raw_vitals_line": "",
        "inventory": [],
        "milestones": [],
    }
    if not ficha_path.exists():
        return data
    text = ficha_path.read_text(encoding="utf-8")

    m_name = re.search(r"\*\*Nome:\*\*\s*([^\n(—]+)", text)
    if m_name:
        data["name"] = m_name.group(1).strip()

    vitals_text = text
    m_v_sec = re.search(r"###\s*Vitais[^\n]*\n(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if m_v_sec:
        vitals_text = m_v_sec.group(1)

    vitals_parts = []
    for m in re.finditer(r"\*\s*\*\*([^:*]+):\*\*\s*(\d+)\s*/\s*(\d+)", vitals_text):
        label, cur, mx = m.group(1).strip(), int(m.group(2)), int(m.group(3))
        low = label.lower()
        m_abbr = re.search(r"\(([^)]+)\)", low)
        abbr = m_abbr.group(1).strip() if m_abbr else ""
        short_name = low.split("(")[0].strip()

        if "hp" in low or "vida" in low or "pv" in low:
            key = "hp"
        elif "stamina" in low or "fôlego" in low or "folego" in low or "fadiga" in low or "vigor" in low:
            key = "stamina"
        elif "ce" in (low, abbr) or "energia" in low or "mp" in (low, abbr) or "mana" in low:
            key = "ce"
        else:
            key = abbr or short_name

        data["vitals"][key] = {
            "label": label,
            "current": cur,
            "max": mx,
            "short": label.split("(")[0].strip(),
            "abbr": abbr,
        }
        vitals_parts.append(f"{label}: {cur}/{mx}")
    data["raw_vitals_line"] = " | ".join(vitals_parts)

    stats_text = text
    m_s_sec = re.search(r"###\s*Atributos[^\n]*\n(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if m_s_sec:
        stats_text = m_s_sec.group(1)

    for m in re.finditer(r"\*\s*\*\*([A-ZÀ-Ú]{2,5})\b[^*]*\*\*\s*(\d+)", stats_text):
        stat_code = m.group(1).upper()
        val = int(m.group(2))
        data["stats"][stat_code] = val

    inventory = []
    m_inv = re.search(r"### Equipamento & Inventário\s*\n(.*?)(?=\n###|\Z)", text, re.DOTALL)
    if m_inv:
        for line in m_inv.group(1).splitlines():
            line = line.strip()
            if line.startswith("*"):
                inventory.append(line.lstrip("* ").strip())
    data["inventory"] = inventory

    milestones = []
    m_mil = re.search(r"### Marcos de Evolução Pessoal[^\n]*\s*\n(.*?)(?=\n###|\Z)", text, re.DOTALL)
    if m_mil:
        for line in m_mil.group(1).splitlines():
            line = line.strip()
            if line.startswith("*"):
                milestones.append(line.lstrip("* ").strip())
    data["milestones"] = milestones
    data["progression"] = parse_progression_from_ficha(ficha_path)

    return data


def upsert_ficha_feature(
    ficha_path: Path,
    ability: str = "",
    milestone: str = "",
    item: str = "",
) -> list[str]:
    """Insere novas Habilidades, Marcos ou Itens em ficha.md atomicamente."""
    if not ficha_path.exists():
        return []
    text = ficha_path.read_text(encoding="utf-8")
    applied = []

    if ability:
        sec = "### Habilidades & Técnicas"
        if sec in text:
            idx = text.find(sec) + len(sec)
            line = ability.strip().lstrip("* -")
            if not line.startswith("**"):
                if ":" in line:
                    title, desc = line.split(":", 1)
                    formatted_line = f"\n* **{title.strip()}:** {desc.strip()}"
                else:
                    formatted_line = f"\n* **{line}:** Habilidade adquirida."
            else:
                formatted_line = f"\n* {line}"
            text = text[:idx] + formatted_line + text[idx:]
            applied.append(f"Habilidade adicionada à ficha: {ability.strip()}")

    if milestone:
        sec = "### Marcos de Evolução Pessoal (Milestones do Protagonista)"
        if sec in text:
            idx = text.find(sec) + len(sec)
            line = milestone.strip().lstrip("* -")
            formatted_line = f"\n* {line}" if line.startswith("**") or line.startswith("Marco") else f"\n* **{line}**"
            text = text[:idx] + formatted_line + text[idx:]
            applied.append(f"Marco adicionado à ficha: {milestone.strip()}")

    if item:
        sec = "### Equipamento & Inventário"
        if sec in text:
            idx = text.find(sec) + len(sec)
            line = item.strip().lstrip("* -")
            formatted_line = f"\n* {line}"
            text = text[:idx] + formatted_line + text[idx:]
            applied.append(f"Item adicionado ao inventário: {item.strip()}")

    if applied:
        atomic_write_text(ficha_path, text)
    return applied


__all__ = [
    "normalize_vital_key",
    "parse_ficha_md",
    "upsert_ficha_feature",
]
