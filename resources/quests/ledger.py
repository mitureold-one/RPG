"""resources/quests/ledger.py: Registro e extração de experiência (XP Ledger) em diario.md."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from council.helpers import atomic_write_text

LEDGER_SECTION_HEADER = "### Registro de Experiência"


def parse_xp_ledger_from_text(text: str) -> List[Dict[str, Any]]:
    """Extrai os registros de experiência (XP Ledger) a partir do texto do diário."""
    if not text:
        return []
    m_sec = re.search(r"###\s*Registro de Experiência[^\n]*\n(.*?)(?=\n###|\n##|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        return []
    ledger = []
    line_pat = re.compile(
        r"^\*\s*\*\*\[XP\]\s*(?P<amount>[+-]?\d+)\s*XP\*\*\s*(?:\((?P<reason>[^)]*)\))?(?:\s*\|\s*Turno\s*(?P<turn>\d+))?",
        re.IGNORECASE,
    )
    for line in m_sec.group(1).splitlines():
        m = line_pat.match(line.strip())
        if m:
            amt = int(m.group("amount"))
            reason = (m.group("reason") or "").strip()
            turn_str = m.group("turn")
            turn = int(turn_str) if turn_str and turn_str.isdigit() else None
            ledger.append({"amount": amt, "reason": reason, "turn": turn, "raw": line.strip()})
    return ledger


def parse_xp_ledger_from_diario(diario_path: Path) -> List[Dict[str, Any]]:
    """Extrai os registros de experiência de diario.md."""
    if not diario_path.exists():
        return []
    return parse_xp_ledger_from_text(diario_path.read_text(encoding="utf-8"))


def append_xp_ledger_entry(
    diario_path: Path,
    amount: int,
    reason: str = "",
    turn: Optional[int] = None,
) -> Dict[str, Any]:
    """Registra uma entrada permanente de concessão de XP no diário."""
    if not diario_path.exists():
        return {"error": f"Arquivo {diario_path} não encontrado"}
    text = diario_path.read_text(encoding="utf-8")
    turn_str = f" | Turno {turn}" if turn is not None else ""
    reason_str = f" ({reason.strip()})" if reason.strip() else ""
    sign = "+" if amount >= 0 else ""
    entry_line = f"* **[XP] {sign}{amount} XP**{reason_str}{turn_str}"

    if LEDGER_SECTION_HEADER.lower() in text.lower():
        m_sec = re.search(r"(###\s*Registro de Experiência[^\n]*\n)", text, re.IGNORECASE)
        if m_sec:
            start_pos = m_sec.end()
            m_next = re.search(r"\n(?=###|\n##|\Z)", text[start_pos:])
            if m_next:
                ins_pos = start_pos + m_next.start()
                text = text[:ins_pos].rstrip() + "\n" + entry_line + "\n\n" + text[ins_pos:].lstrip()
            else:
                text = text.rstrip() + "\n" + entry_line + "\n"
    else:
        m_hist = re.search(r"(###\s*Histórico de Turnos)", text, re.IGNORECASE)
        if m_hist:
            ins_pos = m_hist.start()
            text = text[:ins_pos] + f"{LEDGER_SECTION_HEADER}\n{entry_line}\n\n" + text[ins_pos:]
        else:
            text = text.rstrip() + f"\n\n{LEDGER_SECTION_HEADER}\n{entry_line}\n"

    atomic_write_text(diario_path, text)
    return {"action": "ledger_entry_added", "amount": amount, "reason": reason, "turn": turn}


__all__ = [
    "LEDGER_SECTION_HEADER",
    "append_xp_ledger_entry",
    "parse_xp_ledger_from_diario",
    "parse_xp_ledger_from_text",
]
