"""resources/quests/mutations.py: Mutações atômicas e ciclo de vida de missões em diario.md."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from council.helpers import atomic_write_text
from resources.quests.parser import (
    format_quest_header,
    parse_quests_from_text,
)
from rulesets.progression import DEFAULT_QUEST_REWARDS

VALID_QUEST_TYPES = ("MAIN", "SIDE", "PERSONAL", "FACTION")
VALID_QUEST_STATUSES = ("ACTIVE", "BLOCKED", "COMPLETED", "FAILED", "ABANDONED")
SECTION_HEADER = "### Missões & Objetivos"


def upsert_quest_in_diario(
    diario_path: Path,
    action: str,
    quest_id: Optional[str] = None,
    title: str = "",
    quest_type: str = "main",
    objective: str = "",
    contractor: str = "",
    clock: str = "",
    reward: str = "",
    phase: str = "",
    check_index: Optional[int] = None,
    reason: str = "",
    evidence: str = "",
    xp_paid: Optional[int] = None,
    current_turn: Optional[int] = None,
) -> Dict[str, Any]:
    """Realiza operações atômicas no bloco de Missões em diario.md com escrita única."""
    if not diario_path.exists():
        return {"error": f"Arquivo {diario_path} não encontrado"}

    text = diario_path.read_text(encoding="utf-8")

    if SECTION_HEADER.lower() not in text.lower() and not re.search(r"###\s*Missões", text, re.IGNORECASE):
        m_hist = re.search(r"(###\s*Histórico de Turnos)", text, re.IGNORECASE)
        if m_hist:
            ins_pos = m_hist.start()
            text = text[:ins_pos] + f"{SECTION_HEADER}\n\n" + text[ins_pos:]
        else:
            m_clocks = re.search(r"(###\s*Relógios de Ameaça[^\n]*\n.*?(?=\n###|\n##|\Z))", text, re.IGNORECASE | re.DOTALL)
            if m_clocks:
                ins_pos = m_clocks.end()
                text = text[:ins_pos] + f"\n\n{SECTION_HEADER}\n" + text[ins_pos:]
            else:
                m_scene = re.search(r"(##\s*Cena[^\n]+)", text)
                if m_scene:
                    ins_pos = m_scene.end()
                    text = text[:ins_pos] + f"\n\n{SECTION_HEADER}\n" + text[ins_pos:]
                else:
                    text = f"{SECTION_HEADER}\n\n" + text

    existing_quests = parse_quests_from_text(text)

    if action == "add":
        clean_type = (quest_type or "main").strip().upper()
        if clean_type not in VALID_QUEST_TYPES:
            clean_type = "MAIN"

        existing_nums = []
        for q in existing_quests:
            m_id = re.match(r"^Q(\d+)$", q.get("id", ""), re.IGNORECASE)
            if m_id:
                existing_nums.append(int(m_id.group(1)))
        new_num = max(existing_nums) + 1 if existing_nums else 1
        new_id = f"Q{new_num}"

        default_reward_xp = DEFAULT_QUEST_REWARDS.get(clean_type, 150)
        new_q = {
            "id": new_id,
            "title": title.strip(),
            "type": clean_type,
            "status": "ACTIVE",
            "phase": phase.strip() or "Início",
            "contractor": contractor.strip(),
            "clock": clock.strip(),
            "reward": reward.strip() or f"{default_reward_xp} XP",
            "last_progress": f"Turno {current_turn}" if current_turn else "",
            "xp_paid": None,
        }
        header_line = format_quest_header(new_q)
        content_lines = [header_line]
        if objective.strip():
            content_lines.append(f"  * [ ] {objective.strip()}")

        quest_block = "\n".join(content_lines)

        m_sec = re.search(r"###\s*Missões[^\n]*\n", text, re.IGNORECASE)
        if m_sec:
            sec_start = m_sec.end()
            m_next = re.search(r"\n(?=###|\n##|\Z)", text[sec_start:])
            if m_next:
                ins_pos = sec_start + m_next.start()
                text = text[:ins_pos].rstrip() + "\n\n" + quest_block + "\n\n" + text[ins_pos:].lstrip()
            else:
                text = text.rstrip() + "\n\n" + quest_block + "\n"
        else:
            text += f"\n\n{SECTION_HEADER}\n\n" + quest_block + "\n"

        atomic_write_text(diario_path, text)
        return {"action": "quest_added", "quest_id": new_id, "title": title}

    target_q = None
    for i, q in enumerate(existing_quests):
        if q["id"].lower() == (quest_id or "").lower() or (not quest_id and i == 0):
            target_q = q
            break

    if not target_q:
        return {"error": f"Missão '{quest_id}' não encontrada em diario.md"}

    if action == "add_objective":
        if not objective:
            return {"error": "Texto do objetivo não pode ser vazio"}
        obj_line = f"  * [ ] {objective.strip()}"
        m_head = re.search(re.escape(target_q["raw_header"]), text)
        if not m_head:
            return {"error": "Cabeçalho da missão não localizado no texto"}
        line_end = text.find("\n", m_head.end())
        line_end = len(text) if line_end == -1 else line_end + 1

        rem = text[line_end:]
        lines = rem.splitlines(keepends=True)
        insert_offset = 0
        for l in lines:
            if re.match(r"^\s{2,}\*\s*", l):
                insert_offset += len(l)
            else:
                break
        final_pos = line_end + insert_offset
        text = text[:final_pos].rstrip() + f"\n{obj_line}\n\n" + text[final_pos:].lstrip("\n")
        atomic_write_text(diario_path, text)
        return {"action": "objective_added", "quest_id": target_q["id"], "objective": objective.strip()}

    if action == "check":
        if check_index is None or check_index < 1 or check_index > len(target_q["objectives"]):
            return {"error": f"Índice de objetivo {check_index} inválido para missão {target_q['id']}"}
        obj = target_q["objectives"][check_index - 1]
        old_obj_text = obj["text"]

        if current_turn:
            target_q["last_progress"] = f"Turno {current_turn}"
            new_header = format_quest_header(target_q)
            text = text.replace(target_q["raw_header"], new_header, 1)
            target_q["raw_header"] = new_header

        m_head = re.search(re.escape(target_q["raw_header"]), text)
        if not m_head:
            return {"error": "Cabeçalho da missão não localizado no texto"}
        head_end = m_head.end()

        obj_pat = rf"(\s*\*\s*\[)\s*(\]\s*{re.escape(old_obj_text)})"
        m_obj = re.search(obj_pat, text[head_end:])
        if not m_obj:
            return {"error": f"Objetivo '{old_obj_text}' não encontrado no diário"}

        obj_match_start = head_end + m_obj.start()
        obj_match_end = head_end + m_obj.end()
        leading_space = m_obj.group(1).split("*")[0]
        replacement = f"{leading_space}* [x] {old_obj_text}"
        text = text[:obj_match_start] + replacement + text[obj_match_end:]

        atomic_write_text(diario_path, text)
        return {"action": "objective_checked", "quest_id": target_q["id"], "index": check_index, "text": old_obj_text}

    if action in ("complete", "fail", "block", "unblock", "abandon", "reopen", "set_xp_paid"):
        m_head = re.search(re.escape(target_q["raw_header"]), text)
        if not m_head:
            return {"error": "Cabeçalho da missão não localizado no texto"}

        if action == "complete":
            target_q["status"] = "COMPLETED"
            if current_turn:
                target_q["last_progress"] = f"Turno {current_turn}"
            if xp_paid is not None:
                target_q["xp_paid"] = xp_paid
        elif action == "fail":
            target_q["status"] = "FAILED"
            if current_turn:
                target_q["last_progress"] = f"Turno {current_turn} (Falha: {reason or 'Insucesso'})"
        elif action == "block":
            target_q["status"] = "BLOCKED"
            if reason:
                target_q["last_progress"] = f"Bloqueada: {reason}"
        elif action == "unblock":
            target_q["status"] = "ACTIVE"
            if current_turn:
                target_q["last_progress"] = f"Turno {current_turn} (Desbloqueada)"
        elif action == "abandon":
            target_q["status"] = "ABANDONED"
            if reason:
                target_q["last_progress"] = f"Abandonada: {reason}"
        elif action == "reopen":
            target_q["status"] = "ACTIVE"
            if current_turn:
                target_q["last_progress"] = f"Turno {current_turn} (Reaberta: {reason or 'Novos indícios'})"
        elif action == "set_xp_paid":
            target_q["xp_paid"] = xp_paid

        new_header = format_quest_header(target_q)
        text = text.replace(target_q["raw_header"], new_header, 1)

        if action == "complete" and evidence.strip():
            evidence_line = f"  * **Evidência:** {evidence.strip()}"
            m_new_head = re.search(re.escape(new_header), text)
            if m_new_head:
                line_end = text.find("\n", m_new_head.end())
                line_end = len(text) if line_end == -1 else line_end + 1
                rem = text[line_end:]
                lines = rem.splitlines(keepends=True)
                offset = 0
                has_evidence = False
                for l in lines:
                    if re.match(r"^\s{2,}\*\s*\[", l):
                        offset += len(l)
                    elif re.match(r"^\s{2,}\*\s*\*\*Evidência:", l):
                        has_evidence = True
                        break
                    else:
                        break
                if not has_evidence:
                    insert_at = line_end + offset
                    text = text[:insert_at].rstrip() + f"\n{evidence_line}\n\n" + text[insert_at:].lstrip("\n")

        atomic_write_text(diario_path, text)
        return {
            "action": f"quest_{action}",
            "quest_id": target_q["id"],
            "new_status": target_q["status"],
            "xp_paid": target_q.get("xp_paid"),
            "evidence": evidence.strip() if evidence else None,
        }

    return {"error": f"Ação '{action}' desconhecida"}


__all__ = [
    "SECTION_HEADER",
    "VALID_QUEST_STATUSES",
    "VALID_QUEST_TYPES",
    "upsert_quest_in_diario",
]
