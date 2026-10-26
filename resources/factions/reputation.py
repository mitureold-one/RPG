"""resources/factions/reputation.py: Parsing e manipulação de reputação em ficha.md e diario.md."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from council.helpers import atomic_write_text
from resources.factions.parser import (
    SOCIAL_DC_MODIFIERS,
    SUGGESTED_VARIANTS,
    clamp_reputation,
    legacy_label_to_score,
    normalize_ascii_slug,
    score_to_tier_name,
)

FACTION_LEDGER_HEADER: str = "### Registro de Reputação & Facções"


def parse_reputation_from_ficha(ficha_path: Path) -> Dict[str, Dict[str, Any]]:
    """Extrai a reputação do protagonista com facções sob '### Vínculos' em ficha.md."""
    reputations: Dict[str, Dict[str, Any]] = {}
    if not ficha_path.exists():
        return reputations

    text = ficha_path.read_text(encoding="utf-8")
    m_vinc = re.search(r"###\s*Vínculos[^\n]*\n(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_vinc:
        return reputations

    vinc_text = m_vinc.group(1)
    sub_pattern = re.compile(
        r"^\s{2,}\*\s*\*\*(?:\[([^\]]+)\]\s*)?([^*:]+)(?::)?\*\*(?:\s*:\s*)?\s*([+-]?\d+)?\s*(?:\(([^)]+)\))?(?:.*?Favores:\s*(\d+))?(?:.*?D[eé]bitos:\s*(\d+))?",
        re.MULTILINE,
    )
    matches = list(sub_pattern.finditer(vinc_text))
    if matches:
        for m in matches:
            tag = (m.group(1) or "").strip()
            name = m.group(2).strip()
            raw_score = m.group(3)
            raw_tier = (m.group(4) or "").strip()
            score = clamp_reputation(int(raw_score)) if raw_score is not None else legacy_label_to_score(raw_tier)
            entry = {
                "tag": tag or normalize_ascii_slug(name),
                "name": name,
                "score": score,
                "tier": score_to_tier_name(score),
                "favors": max(0, int(m.group(5))) if m.group(5) is not None else 0,
                "debts": max(0, int(m.group(6))) if m.group(6) is not None else 0,
                "social_dc_modifier": SOCIAL_DC_MODIFIERS.get(score, 0),
                "suggested_variant": SUGGESTED_VARIANTS.get(score, "normal"),
            }
            reputations[name.lower()] = entry
            if tag:
                reputations[tag.lower()] = entry
        return reputations

    m_uni = re.search(r"\*\s*\*\*Reputa[çc][ãa]o\s*com\s*Fac[çc][õo]es:\*\*\s*([^\n]+)", vinc_text, re.IGNORECASE)
    if m_uni:
        items = re.split(r",\s*(?=[^()]*\()", m_uni.group(1).strip())
        for it in items:
            m_it = re.search(r"^(.*?)\s*\(([^)]+)\)$", it.strip().rstrip("."))
            if m_it:
                f_name = m_it.group(1).strip()
                score = legacy_label_to_score(m_it.group(2).strip())
                tag = normalize_ascii_slug(f_name)
                entry = {
                    "tag": tag,
                    "name": f_name,
                    "score": score,
                    "tier": score_to_tier_name(score),
                    "favors": 0,
                    "debts": 0,
                    "social_dc_modifier": SOCIAL_DC_MODIFIERS.get(score, 0),
                    "suggested_variant": SUGGESTED_VARIANTS.get(score, "normal"),
                }
                reputations[f_name.lower()] = entry
                reputations[tag.lower()] = entry

    return reputations


def update_reputation_in_ficha(
    ficha_path: Path,
    faction_name: str,
    score_delta: int = 0,
    favors_delta: int = 0,
    debts_delta: int = 0,
    set_score: Optional[int] = None,
    set_favors: Optional[int] = None,
    set_debts: Optional[int] = None,
    tag: str = "",
) -> Dict[str, Any]:
    """Atualiza atômica e numericamente a reputação, favores e débitos em ficha.md."""
    if not ficha_path.exists():
        return {"error": f"Arquivo {ficha_path} não encontrado"}

    text = ficha_path.read_text(encoding="utf-8")
    existing_reps = parse_reputation_from_ficha(ficha_path)
    clean_name = faction_name.strip()
    target = None
    for k, v in existing_reps.items():
        if k == clean_name.lower() or v["tag"].lower() == clean_name.lower():
            target = v
            break

    cur_score = target["score"] if target else 0
    cur_favors = target["favors"] if target else 0
    cur_debts = target["debts"] if target else 0
    final_tag = tag.strip().upper() if tag else (target["tag"] if target else normalize_ascii_slug(clean_name))

    new_score = clamp_reputation(set_score if set_score is not None else cur_score + score_delta)
    new_favors = max(0, set_favors if set_favors is not None else cur_favors + favors_delta)
    new_debts = max(0, set_debts if set_debts is not None else cur_debts + debts_delta)
    new_tier = score_to_tier_name(new_score)

    formatted_score = f"+{new_score}" if new_score > 0 else str(new_score)
    new_sub_bullet = f"  * **[{final_tag}] {clean_name}:** {formatted_score} ({new_tier}) | Favores: {new_favors} | Débitos: {new_debts}"

    m_vinc = re.search(r"(###\s*Vínculos[^\n]*\n)(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_vinc:
        return {"error": "Seção '### Vínculos' não encontrada em ficha.md"}

    sec_header = m_vinc.group(1)
    sec_body = m_vinc.group(2)
    pat_existing = re.compile(
        rf"^\s{{2,}}\*\s*\*\*(?:\[(?:{re.escape(final_tag)}|[^\]]+)\]\s*|\s*){re.escape(clean_name)}:?\*\*:?[^\n]*$",
        re.MULTILINE | re.IGNORECASE,
    )
    if pat_existing.search(sec_body):
        new_sec_body = pat_existing.sub(new_sub_bullet, sec_body, count=1)
    else:
        m_rep_head = re.search(r"(\*\s*\*\*Reputa[çc][ãa]o\s*com\s*Fac[çc][õo]es:\*\*[^\n]*)", sec_body, re.IGNORECASE)
        if m_rep_head:
            orig_rep_line = m_rep_head.group(1)
            if "(" in orig_rep_line:
                other_bullets = []
                for f_k, f_v in existing_reps.items():
                    if f_v["name"].lower() != clean_name.lower() and f_k == f_v["name"].lower():
                        sc_fmt = f"+{f_v['score']}" if f_v["score"] > 0 else str(f_v["score"])
                        other_bullets.append(f"  * **[{f_v['tag']}] {f_v['name']}:** {sc_fmt} ({f_v['tier']}) | Favores: {f_v['favors']} | Débitos: {f_v['debts']}")
                new_sec_body = sec_body.replace(orig_rep_line, f"* **Reputação com Facções:**\n" + "\n".join(other_bullets + [new_sub_bullet]), 1)
            else:
                insert_idx = m_rep_head.end()
                new_sec_body = sec_body[:insert_idx] + f"\n{new_sub_bullet}" + sec_body[insert_idx:]
        else:
            new_sec_body = sec_body.rstrip() + f"\n* **Reputação com Facções:**\n{new_sub_bullet}\n"

    text = text[:m_vinc.start()] + sec_header + new_sec_body + text[m_vinc.end():]
    atomic_write_text(ficha_path, text)

    return {
        "tag": final_tag,
        "name": clean_name,
        "old_score": cur_score,
        "new_score": new_score,
        "old_tier": score_to_tier_name(cur_score),
        "new_tier": new_tier,
        "favors": new_favors,
        "debts": new_debts,
        "social_dc_modifier": SOCIAL_DC_MODIFIERS.get(new_score, 0),
        "suggested_variant": SUGGESTED_VARIANTS.get(new_score, "normal"),
    }


def parse_faction_ledger_from_diario(diario_path: Path) -> List[Dict[str, Any]]:
    """Extrai mutações históricas de reputação em diario.md."""
    if not diario_path.exists():
        return []

    text = diario_path.read_text(encoding="utf-8")
    m_sec = re.search(r"###\s*Registro\s*de\s*Reputa[çc][ãa]o[^\n]*\n(.*?)(?=\n###|\n##|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        return []

    pattern = re.compile(
        r"^\*\s*\*\*\[(?:Turno\s*)?(\d+)\]\*\*\s*([^:]+):\s*([+-]?\d+)\s*Reputa[çc][ãa]o[^(]*\((?:[+-]?\d+\s*->\s*)?([+-]?\d+)\s*\[([^\]]+)\]\)(?:.*?Favores:\s*([+-]?\d+))?(?:.*?D[eé]bitos:\s*([+-]?\d+))?(?:.*?Motivo:\s*([^|\n]+))?(?:.*?Miss[ãa]o:\s*([^|\n]+))?",
        re.MULTILINE | re.IGNORECASE,
    )
    entries = []
    for m in pattern.finditer(m_sec.group(1)):
        entries.append({
            "turn": int(m.group(1)),
            "faction": m.group(2).strip(),
            "delta_rep": int(m.group(3)),
            "new_score": int(m.group(4)),
            "tier": m.group(5).strip(),
            "delta_favors": int(m.group(6)) if m.group(6) else 0,
            "delta_debts": int(m.group(7)) if m.group(7) else 0,
            "reason": (m.group(8) or "").strip(),
            "quest_id": (m.group(9) or "").strip(),
        })
    return entries


def append_faction_ledger_entry(
    diario_path: Path,
    faction_name: str = "",
    delta_rep: int = 0,
    new_score: int = 0,
    reason: str = "",
    turn: Optional[int] = None,
    delta_favors: int = 0,
    delta_debts: int = 0,
    quest_id: str = "",
    faction: str = "",
) -> Dict[str, Any]:
    """Registra uma linha de mutação de reputação/favores no ledger do diário."""
    if not faction_name and faction:
        faction_name = faction
    if not diario_path.exists():
        return {"error": f"Arquivo {diario_path} não encontrado"}

    text = diario_path.read_text(encoding="utf-8")
    tier_name = score_to_tier_name(new_score)
    cur_turn = turn if turn is not None else 1

    rep_sign = f"+{delta_rep}" if delta_rep > 0 else str(delta_rep)
    old_score = new_score - delta_rep
    old_sign = f"+{old_score}" if old_score > 0 else str(old_score)
    new_sign = f"+{new_score}" if new_score > 0 else str(new_score)

    entry_parts = [f"* **[Turno {cur_turn}]** {faction_name}: {rep_sign} Reputação ({old_sign} -> {new_sign} [{tier_name}])"]
    if delta_favors != 0:
        entry_parts.append(f"Favores: {'+' if delta_favors > 0 else ''}{delta_favors}")
    if delta_debts != 0:
        entry_parts.append(f"Débitos: {'+' if delta_debts > 0 else ''}{delta_debts}")
    if reason.strip():
        entry_parts.append(f"Motivo: {reason.strip()}")
    if quest_id.strip():
        entry_parts.append(f"Missão: {quest_id.strip()}")

    entry_line = " | ".join(entry_parts)

    if FACTION_LEDGER_HEADER.lower() not in text.lower():
        m_hist = re.search(r"(###\s*Histórico de Turnos)", text, re.IGNORECASE)
        if m_hist:
            idx = m_hist.start()
            text = text[:idx] + f"{FACTION_LEDGER_HEADER}\n\n{entry_line}\n\n" + text[idx:]
        else:
            text = text.rstrip() + f"\n\n{FACTION_LEDGER_HEADER}\n\n{entry_line}\n"
    else:
        sec_idx = text.lower().find(FACTION_LEDGER_HEADER.lower())
        m_next_sec = re.search(r"\n###|\n##|\Z", text[sec_idx + len(FACTION_LEDGER_HEADER):])
        ins_pos = (sec_idx + len(FACTION_LEDGER_HEADER) + m_next_sec.start()) if m_next_sec else len(text)
        text = text[:ins_pos].rstrip() + f"\n{entry_line}\n\n" + text[ins_pos:].lstrip("\n")

    atomic_write_text(diario_path, text)
    return {
        "turn": cur_turn,
        "faction": faction_name,
        "delta_rep": delta_rep,
        "new_score": new_score,
        "tier": tier_name,
        "delta_favors": delta_favors,
        "delta_debts": delta_debts,
        "reason": reason,
        "quest_id": quest_id,
    }


__all__ = [
    "FACTION_LEDGER_HEADER",
    "append_faction_ledger_entry",
    "parse_faction_ledger_from_diario",
    "parse_reputation_from_ficha",
    "update_reputation_in_ficha",
]
