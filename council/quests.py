"""council/quests.py: Parser e Gerenciador de Ciclo de Vida de Missões em diario.md.

Implementa a extração estruturada, criação atômica, transições de estado
e manipulação de objetivos em checkboxes Markdown para o RPGPRO.
Totalmente em Python Standard Library (sem dependências externas).
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from rulesets.progression import DEFAULT_QUEST_REWARDS

VALID_QUEST_TYPES = ("MAIN", "SIDE", "PERSONAL", "FACTION")
VALID_QUEST_STATUSES = ("ACTIVE", "BLOCKED", "COMPLETED", "FAILED", "ABANDONED")
SECTION_HEADER = "### Missões & Objetivos"
LEDGER_SECTION_HEADER = "### Registro de Experiência"


def parse_reward_xp(reward_text: str) -> Optional[int]:
    """Extrai o valor numérico de XP de uma string de recompensa (ex: '150 XP', 'Recompensa: 60xp')."""
    if not reward_text:
        return None
    m = re.search(r"(\d+)\s*(?:xp|pontos de experiência)", reward_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_quests_from_text(text: str) -> List[Dict[str, Any]]:
    """Extrai as Missões e Objetivos estruturados a partir do conteúdo de diario.md."""
    if not text:
        return []

    # Extrai o bloco da seção até o próximo cabeçalho de nível 2 ou 3 (ex: ### Histórico de Turnos)
    m_sec = re.search(r"#{2,3}\s*Missões[^\n]*\n(.*?)(?=\n#{2,3}|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        return []

    sec_content = m_sec.group(1)
    quests: List[Dict[str, Any]] = []

    # Linhas de missão: * **[Q1] [MAIN] Título** | Campo: Valor | ...
    # Suporta identificador opcional explícito: * **[Q1] [MAIN] Título** ou legado * **[MAIN] Título**
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
            if status not in VALID_QUEST_STATUSES:
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


def parse_xp_ledger_from_text(text: str) -> List[Dict[str, Any]]:
    """Extrai os registros de experiência (XP Ledger) a partir do texto do diário."""
    if not text:
        return []
    m_sec = re.search(r"###\s*Registro de Experiência[^\n]*\n(.*?)(?=\n###|\n##|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        return []
    ledger = []
    line_pat = re.compile(
        r"^\*\s*\*\*\[XP\]\s*\+(?P<amount>\d+)\s*XP\*\*\s*(?:\((?P<reason>[^)]*)\))?(?:\s*\|\s*Turno\s*(?P<turn>\d+))?",
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
    entry_line = f"* **[XP] +{amount} XP**{reason_str}{turn_str}"

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

    diario_path.write_text(text, encoding="utf-8")
    return {"action": "ledger_entry_added", "amount": amount, "reason": reason, "turn": turn}


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
    """Realiza operações atômicas no bloco de Missões em diario.md com escrita única.
    
    Ações suportadas:
    - 'add': Cria nova missão com ID monotônico no final da seção.
    - 'add_objective': Adiciona objetivo a uma missão existente.
    - 'check': Marca um objetivo como concluído [x].
    - 'complete': Transiciona status para COMPLETED, anexa evidência e grava XP Pago.
    - 'fail': Transiciona status para FAILED com motivo.
    - 'block': Transiciona status para BLOCKED com motivo.
    - 'unblock': Transiciona status para ACTIVE.
    - 'abandon': Transiciona status para ABANDONED com motivo.
    - 'reopen': Reabre missão para ACTIVE com motivo auditado.
    - 'set_xp_paid': Crava carimbo de XP pago para idempotência.
    """
    if not diario_path.exists():
        return {"error": f"Arquivo {diario_path} não encontrado"}

    text = diario_path.read_text(encoding="utf-8")

    # Garante que a seção de Missões existe em memória
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

    # Parseia missões atuais diretamente da memória (sem escrita intermediária)
    existing_quests = parse_quests_from_text(text)

    # 1. Adicionar nova missão (monotônica no final do bloco de missões)
    if action == "add":
        clean_type = (quest_type or "main").strip().upper()
        if clean_type not in VALID_QUEST_TYPES:
            clean_type = "MAIN"

        # Extrai números de todos os IDs Q{N} existentes
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

        # Localiza o final da seção de missões (antes do próximo ### ou ##)
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

        diario_path.write_text(text, encoding="utf-8")
        return {"action": "quest_added", "quest_id": new_id, "title": title}

    # Para demais ações, localiza a missão alvo pelo ID exato
    target_q = None
    target_idx = -1
    for i, q in enumerate(existing_quests):
        if q["id"].lower() == (quest_id or "").lower() or (not quest_id and i == 0):
            target_q = q
            target_idx = i
            break

    if not target_q:
        return {"error": f"Missão '{quest_id}' não encontrada em diario.md"}

    # 2. Adicionar objetivo
    if action == "add_objective":
        if not objective:
            return {"error": "Texto do objetivo não pode ser vazio"}
        obj_line = f"  * [ ] {objective.strip()}"
        m_head = re.search(re.escape(target_q["raw_header"]), text)
        if not m_head:
            return {"error": "Cabeçalho da missão não localizado no texto"}
        line_end = text.find("\n", m_head.end())
        if line_end == -1:
            line_end = len(text)
        else:
            line_end += 1

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
        diario_path.write_text(text, encoding="utf-8")
        return {"action": "objective_added", "quest_id": target_q["id"], "objective": objective.strip()}

    # 3. Marcar objetivo como concluído (check)
    if action == "check":
        if check_index is None or check_index < 1 or check_index > len(target_q["objectives"]):
            return {"error": f"Índice de objetivo {check_index} inválido para missão {target_q['id']}"}
        obj = target_q["objectives"][check_index - 1]
        old_obj_text = obj["text"]

        # Atualiza cabeçalho com Último Progresso primeiro se fornecido
        if current_turn:
            target_q["last_progress"] = f"Turno {current_turn}"
            new_header = format_quest_header(target_q)
            text = text.replace(target_q["raw_header"], new_header, 1)
            target_q["raw_header"] = new_header

        # Localiza o cabeçalho no texto para substituição escopada do objetivo
        m_head = re.search(re.escape(target_q["raw_header"]), text)
        if not m_head:
            return {"error": "Cabeçalho da missão não localizado no texto"}
        head_end = m_head.end()

        # Regex delimitado após o cabeçalho desta missão
        obj_pat = rf"(\s*\*\s*\[)\s*(\]\s*{re.escape(old_obj_text)})"
        m_obj = re.search(obj_pat, text[head_end:])
        if not m_obj:
            return {"error": f"Objetivo '{old_obj_text}' não encontrado no diário"}

        obj_match_start = head_end + m_obj.start()
        obj_match_end = head_end + m_obj.end()
        leading_space = m_obj.group(1).split("*")[0]
        replacement = f"{leading_space}* [x] {old_obj_text}"
        text = text[:obj_match_start] + replacement + text[obj_match_end:]

        diario_path.write_text(text, encoding="utf-8")
        return {"action": "objective_checked", "quest_id": target_q["id"], "index": check_index, "text": old_obj_text}

    # 4. Transições de status (complete, fail, block, unblock, abandon, reopen, set_xp_paid)
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

        # Se houver evidência na conclusão, anexa como sub-bullet da missão
        if action == "complete" and evidence.strip():
            evidence_line = f"  * **Evidência:** {evidence.strip()}"
            m_new_head = re.search(re.escape(new_header), text)
            if m_new_head:
                line_end = text.find("\n", m_new_head.end())
                if line_end == -1:
                    line_end = len(text)
                else:
                    line_end += 1
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

        diario_path.write_text(text, encoding="utf-8")
        return {
            "action": f"quest_{action}",
            "quest_id": target_q["id"],
            "new_status": target_q["status"],
            "xp_paid": target_q.get("xp_paid"),
            "evidence": evidence.strip() if evidence else None,
        }

    return {"error": f"Ação '{action}' desconhecida"}
