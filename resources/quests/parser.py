"""resources/quests/parser.py: Parsing e formatação de missões em diario.md."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rulesets.progression import DEFAULT_QUEST_REWARDS


def parse_reward_xp(reward_text: str) -> Optional[int]:
    """Extrai o valor numérico de XP de uma string de recompensa (ex: '150 XP', 'Recompensa: 60xp')."""
    if not reward_text:
        return None
    m = re.search(r"(\d+)\s*(?:xp|pontos de experiência)", reward_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _parse_pipe_fields(text: str) -> Dict[str, str]:
    """Parseia pares Chave: Valor separados por pipe '|'."""
    fields = {}
    parts = text.split("|")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            k, v = part.split(":", 1)
            fields[k.strip().lower()] = v.strip()
    return fields


def _finalize_quest(quest: Dict[str, Any]) -> None:
    """Calcula campos derivados de progresso e sumário da missão."""
    objs = quest.get("objectives", [])
    total = len(objs)
    done_count = sum(1 for o in objs if o.get("done"))
    quest["done_count"] = done_count
    quest["total_count"] = total
    quest["progress_summary"] = f"{done_count}/{total}" if total > 0 else "0/0"
    quest["all_objectives_completed"] = (done_count == total and total > 0)


def format_quest_header(quest: Dict[str, Any]) -> str:
    """Gera a linha canônica formatada de cabeçalho da missão garantindo prefixo [Q{N}]."""
    qid = quest.get("id", "Q1").upper()
    qtype = quest.get("type", "MAIN").upper()
    title = quest.get("title", "Sem Título").strip()
    status = quest.get("status", "ACTIVE").upper()

    parts = [f"* **[{qid}] [{qtype}] {title}**"]
    if quest.get("phase"):
        parts.append(f"Fase: {quest['phase']}")
    parts.append(f"Status: {status}")
    if quest.get("contractor"):
        parts.append(f"Contratante: {quest['contractor']}")
    if quest.get("clock"):
        parts.append(f"Relógio: {quest['clock']}")
    if quest.get("reward"):
        parts.append(f"Recompensa: {quest['reward']}")
    if quest.get("last_progress"):
        parts.append(f"Último Progresso: {quest['last_progress']}")
    if quest.get("xp_paid") is not None:
        parts.append(f"XP Pago: {quest['xp_paid']}")

    return " | ".join(parts)


def parse_quests_from_text(text: str) -> List[Dict[str, Any]]:
    """Extrai as Missões e Objetivos estruturados a partir do conteúdo de diario.md."""
    if not text:
        return []

    m_sec = re.search(r"#{2,3}\s*Missões[^\n]*\n(.*?)(?=\n#{2,3}|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        return []

    sec_content = m_sec.group(1)
    quests: List[Dict[str, Any]] = []

    quest_header_pat = re.compile(
        r"^\*\s*\*\*(?:\[(?P<exp_id>Q\d+)\]\s*)?\[(?P<type>MAIN|SIDE|PERSONAL|FACTION)\]\s+(?P<title>[^*|\n]+)\*\*(?P<rest>[^\n]*)",
        re.IGNORECASE,
    )
    obj_pat = re.compile(r"^\s{2,}\*\s*\[(?P<check>[ xX])\]\s*(?P<text>[^\n]+)")
    evidence_pat = re.compile(r"^\s{2,}\*\s*\*\*Evidência:\*\*\s*(?P<evidence>[^\n]+)", re.IGNORECASE)

    current_quest: Optional[Dict[str, Any]] = None
    quest_counter = 1

    for line in sec_content.splitlines():
        m_head = quest_header_pat.match(line)
        if m_head:
            if current_quest:
                _finalize_quest(current_quest)
                quests.append(current_quest)

            raw_type = m_head.group("type").upper()
            title = m_head.group("title").strip()
            rest = m_head.group("rest") or ""
            exp_id = m_head.group("exp_id")
            qid = exp_id.upper() if exp_id else f"Q{quest_counter}"
            quest_counter += 1

            fields = _parse_pipe_fields(rest)
            reward = fields.get("recompensa", "")
            status = fields.get("status", "ACTIVE").upper()
            if status not in ("ACTIVE", "BLOCKED", "COMPLETED", "FAILED", "ABANDONED"):
                status = "ACTIVE"

            xp_paid_val = None
            if "xp pago" in fields:
                try:
                    xp_paid_val = int(fields["xp pago"])
                except ValueError:
                    pass

            default_reward = DEFAULT_QUEST_REWARDS.get(raw_type, 150)

            current_quest = {
                "id": qid,
                "title": title,
                "type": raw_type,
                "status": status,
                "phase": fields.get("fase", ""),
                "contractor": fields.get("contratante", ""),
                "clock": fields.get("relógio", fields.get("relogio", "")),
                "reward": reward,
                "reward_xp": parse_reward_xp(reward) or default_reward,
                "last_progress": fields.get("último progresso", fields.get("ultimo progresso", "")),
                "xp_paid": xp_paid_val,
                "evidence": "",
                "objectives": [],
                "raw_header": line,
            }
            continue

        if current_quest:
            m_evi = evidence_pat.match(line)
            if m_evi:
                current_quest["evidence"] = m_evi.group("evidence").strip()
                continue

            m_obj = obj_pat.match(line)
            if m_obj:
                is_done = m_obj.group("check").lower() == "x"
                obj_text = m_obj.group("text").strip()
                current_quest["objectives"].append({
                    "index": len(current_quest["objectives"]) + 1,
                    "text": obj_text,
                    "done": is_done,
                })

    if current_quest:
        _finalize_quest(current_quest)
        quests.append(current_quest)

    return quests


def parse_quests_from_diario(diario_path: Path) -> List[Dict[str, Any]]:
    """Extrai as Missões e Objetivos estruturados de diario.md."""
    if not diario_path.exists():
        return []
    text = diario_path.read_text(encoding="utf-8")
    return parse_quests_from_text(text)


__all__ = [
    "format_quest_header",
    "parse_quests_from_diario",
    "parse_quests_from_text",
    "parse_reward_xp",
]
