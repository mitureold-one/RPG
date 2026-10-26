"""resources/factions/parser.py: Parsing e manipulação de facções declaradas em mundo.md."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from council.helpers import atomic_write_text

REPUTATION_TIERS: Dict[int, str] = {
    3: "Venerado",
    2: "Aliado",
    1: "Amigável",
    0: "Neutro",
    -1: "Suspeito",
    -2: "Hostil",
    -3: "Jurado de Morte",
}

SOCIAL_DC_MODIFIERS: Dict[int, int] = {
    3: -3,
    2: -2,
    1: -1,
    0: 0,
    -1: 1,
    -2: 3,
    -3: 5,
}

SUGGESTED_VARIANTS: Dict[int, str] = {
    3: "advantage",
    2: "normal",
    1: "normal",
    0: "normal",
    -1: "normal",
    -2: "disadvantage",
    -3: "disadvantage",
}

FACTION_SECTION_HEADER: str = "## 4. Facções, Forças Ativas & Alianças"
VALID_SCALES: set[str] = {"local", "urbano", "regional", "continental", "global", "planar"}


def normalize_ascii_slug(text: str) -> str:
    """Gera uma tag alfanumérica em caixa alta (ex: 'Ordem da Fé' -> 'ORDEM_DA_FE')."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_").upper()
    return slug or "FACCAO"


def clamp_reputation(score: int) -> int:
    """Trava o valor da reputação no intervalo simétrico [-3, +3]."""
    try:
        val = int(score)
    except (ValueError, TypeError):
        val = 0
    return max(-3, min(3, val))


def score_to_tier_name(score: int) -> str:
    """Retorna o rótulo nominal canônico do escalão para o score fornecido."""
    return REPUTATION_TIERS.get(clamp_reputation(score), "Neutro")


def legacy_label_to_score(label: str) -> int:
    """Converte termos legados ou qualitativos livres para o score numérico mais próximo."""
    raw = (label or "").strip()
    if not raw:
        return 0

    m_num = re.search(r"([+-]?\d+)", raw)
    if m_num:
        try:
            return clamp_reputation(int(m_num.group(1)))
        except ValueError:
            pass

    low = raw.lower()
    if any(k in low for k in ["venerado", "devoção", "devocao", "lealdade absoluta", "idolatrado"]):
        return 3
    if any(k in low for k in ["aliado", "confiável", "confiavel", "respeitado", "irmandade", "irmão", "irmao"]):
        return 2
    if any(k in low for k in ["favorável", "favoravel", "amigável", "amigavel", "cordial", "receptivo"]):
        return 1
    if any(k in low for k in ["jurado de morte", "odioso", "caçado", "cacado", "execução", "execucao", "morte"]):
        return -3
    if any(k in low for k in ["hostil", "inimigo", "guerra", "ódio", "odio", "confronto"]):
        return -2
    if any(k in low for k in ["suspeito", "vigilante", "cético", "cetico", "desconfiança", "desconfianca", "alerta", "vigia"]):
        return -1
    return 0


def parse_factions_from_mundo(mundo_path: Path) -> List[Dict[str, Any]]:
    """Extrai todas as facções declaradas em mundo.md sob '## 4. Facções, Forças Ativas & Alianças'."""
    if not mundo_path.exists():
        return []

    text = mundo_path.read_text(encoding="utf-8")
    m_sec = re.search(r"##\s*4\.\s*Facções[^\n]*\n(.*?)(?=\n###|\n##\s*\d|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        m_sec = re.search(r"##[^\n]*Facções[^\n]*\n(.*?)(?=\n###|\n##\s*\d|\Z)", text, re.IGNORECASE | re.DOTALL)
        if not m_sec:
            return []

    sec_text = m_sec.group(1)
    factions = []
    lines = sec_text.splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean.startswith(("*", "-")):
            continue
        if line_clean.startswith("###") or "Dinâmica Inter-Facções" in line_clean or "Dinamica" in line_clean:
            continue

        raw_tag = ""
        name = ""
        body = ""

        m_line = re.match(r"^[\*\-]\s*\*\*(?:\[([^\]]+)\]\s*)?([^*:]+)(?::)?\*\*(?:\s*:\s*)?\s*(.*)$", line_clean)
        if m_line:
            raw_tag = (m_line.group(1) or "").strip()
            name = m_line.group(2).strip().rstrip(":")
            body = m_line.group(3).strip()
        else:
            m_line2 = re.match(r"^[\*\-]\s*(?:\*\*)?(?:\[([^\]]+)\]\s*)?([^*—(:]+?)(?:\*\*)?\s*(?:\(([^)]+)\))?\s*[—:]\s*(.*)$", line_clean)
            if m_line2:
                raw_tag = (m_line2.group(1) or "").strip()
                name = m_line2.group(2).strip().rstrip(":")
                par_attrs = m_line2.group(3) or ""
                body = m_line2.group(4).strip()
                if par_attrs:
                    body = f"{body} | {par_attrs}"
            else:
                continue

        m_par = re.match(r"^\(([^)]+)\)\s*[—:]\s*(.*)$", body)
        if m_par:
            attrs_str = m_par.group(1)
            desc_str = m_par.group(2).strip()
            parts = [desc_str] + [p.strip() for p in re.split(r"[,|]+", attrs_str)]
        else:
            parts = [p.strip() for p in body.split("|")]

        desc = parts[0] if parts else ""
        power = 3
        scale = "regional"
        clock = ""
        rivals = []

        for p in parts[1:]:
            p_low = p.lower()
            if "poder:" in p_low:
                m_p = re.search(r"poder:\s*(\d+)", p, re.IGNORECASE)
                if m_p:
                    power = max(1, min(5, int(m_p.group(1))))
            elif "escala:" in p_low:
                m_s = re.search(r"escala:\s*([A-Za-zÀ-ÿ]+)", p, re.IGNORECASE)
                if m_s:
                    sc_cand = m_s.group(1).lower().strip()
                    scale = sc_cand if sc_cand in VALID_SCALES else "regional"
            elif "relógio:" in p_low or "relogio:" in p_low:
                m_c = re.search(r"rel[oó]gio:\s*([^|]+)", p, re.IGNORECASE)
                if m_c:
                    clock = m_c.group(1).strip()
            elif "rivais:" in p_low or "rival:" in p_low:
                m_r = re.search(r"rivais?:\s*([^|]+)", p, re.IGNORECASE)
                if m_r:
                    rivals = [r.strip() for r in re.split(r"[,;]+", m_r.group(1)) if r.strip()]

        tag = raw_tag or normalize_ascii_slug(name)

        factions.append({
            "tag": tag,
            "name": name,
            "description": desc,
            "power": power,
            "scale": scale,
            "clock": clock,
            "rivals": rivals,
            "raw_line": line_clean,
        })

    return factions


def format_faction_line(faction: Dict[str, Any]) -> str:
    """Formata a linha canônica da facção para gravação em mundo.md."""
    tag = faction.get("tag") or normalize_ascii_slug(faction.get("name", "FACCAO"))
    name = faction.get("name", "").strip()
    desc = faction.get("description", "").strip()
    power = max(1, min(5, int(faction.get("power", 3))))
    raw_scale = (faction.get("scale") or "regional").strip().lower()
    scale = raw_scale if raw_scale in VALID_SCALES else "regional"
    clock = (faction.get("clock") or "").strip()
    rivals = faction.get("rivals", [])

    meta_parts = [f"Poder: {power}", f"Escala: {scale}"]
    if clock:
        meta_parts.append(f"Relógio: {clock}")
    if rivals:
        meta_parts.append(f"Rivais: {', '.join(rivals)}")

    meta_str = " | ".join(meta_parts)
    return f"* **[{tag}] {name}:** {desc} | {meta_str}"


def upsert_faction_in_mundo(
    mundo_path: Path,
    name: str,
    tag: str = "",
    power: int = 3,
    scale: str = "regional",
    clock: str = "",
    desc: str = "",
    rivals: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Insere ou atualiza atomicamente uma facção em mundo.md com escrita única."""
    if not mundo_path.exists():
        return {"error": f"Arquivo {mundo_path} não encontrado"}

    text = mundo_path.read_text(encoding="utf-8")
    existing_factions = parse_factions_from_mundo(mundo_path)

    clean_name = name.strip()
    clean_tag = (tag.strip() or normalize_ascii_slug(clean_name)).upper()
    power_clamped = max(1, min(5, int(power)))
    raw_scale = (scale or "regional").strip().lower()
    scale_clean = raw_scale if raw_scale in VALID_SCALES else "regional"

    target = None
    for f in existing_factions:
        if f["tag"].upper() == clean_tag or f["name"].lower() == clean_name.lower():
            target = f
            break

    faction_data = {
        "tag": clean_tag,
        "name": clean_name,
        "description": desc.strip() if desc else (target.get("description", "") if target else "Força ativa do cenário."),
        "power": power_clamped,
        "scale": scale_clean,
        "clock": clock.strip() if clock else (target.get("clock", "") if target else ""),
        "rivals": rivals if rivals is not None else (target.get("rivals", []) if target else []),
    }

    new_line = format_faction_line(faction_data)

    if target and target.get("raw_line") in text:
        text = text.replace(target["raw_line"], new_line, 1)
        action = "faction_updated"
    else:
        m_sec = re.search(r"(##\s*4\.\s*Facções[^\n]*\n)", text, re.IGNORECASE)
        if not m_sec:
            m_sec = re.search(r"(##[^\n]*Facções[^\n]*\n)", text, re.IGNORECASE)

        if m_sec:
            insert_pos = m_sec.end()
            text = text[:insert_pos] + f"{new_line}\n" + text[insert_pos:]
        else:
            m_sec5 = re.search(r"(##\s*5\.[^\n]*\n)", text, re.IGNORECASE)
            if m_sec5:
                pos = m_sec5.start()
                text = text[:pos] + f"\n{FACTION_SECTION_HEADER}\n\n{new_line}\n\n" + text[pos:]
            else:
                text = text.rstrip() + f"\n\n{FACTION_SECTION_HEADER}\n\n{new_line}\n"
        action = "faction_added"

    atomic_write_text(mundo_path, text)
    return {
        "action": action,
        "faction": faction_data,
    }


__all__ = [
    "FACTION_SECTION_HEADER",
    "REPUTATION_TIERS",
    "SOCIAL_DC_MODIFIERS",
    "SUGGESTED_VARIANTS",
    "VALID_SCALES",
    "clamp_reputation",
    "format_faction_line",
    "legacy_label_to_score",
    "normalize_ascii_slug",
    "parse_factions_from_mundo",
    "score_to_tier_name",
    "upsert_faction_in_mundo",
]
