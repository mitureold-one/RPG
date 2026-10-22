"""council/quests.py: Parser e Gerenciador de Ciclo de Vida de Missões em diario.md.

Implementa a extração estruturada, criação atômica, transições de estado
e manipulação de objetivos em checkboxes Markdown para o RPGPRO.
Totalmente em Python Standard Library (sem dependências externas).
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

VALID_QUEST_TYPES = ("MAIN", "SIDE", "PERSONAL", "FACTION")
VALID_QUEST_STATUSES = ("ACTIVE", "BLOCKED", "COMPLETED", "FAILED", "ABANDONED")
SECTION_HEADER = "### Missões & Objetivos"


def parse_reward_xp(reward_text: str) -> Optional[int]:
    """Extrai o valor numérico de XP de uma string de recompensa (ex: '150 XP', 'Recompensa: 60xp')."""
    if not reward_text:
        return None
    m = re.search(r"(\d+)\s*(?:xp|pontos de experiência)", reward_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_quests_from_diario(diario_path: Path) -> List[Dict[str, Any]]:
    """Extrai as Missões e Objetivos estruturados de diario.md.
    
    Retorna uma lista de dicionários representando cada missão.
    Caso o arquivo ou a seção não existam, retorna lista vazia de forma resiliente.
    """
    if not diario_path.exists():
        return []

    text = diario_path.read_text(encoding="utf-8")
    if SECTION_HEADER.lower() not in text.lower():
        # Variações tolerantes de cabeçalho
        if not re.search(r"###\s*Missões", text, re.IGNORECASE):
            return []

    # Extrai o bloco da seção até o próximo cabeçalho de nível 2 ou 3 (ex: ### Histórico de Turnos)
    m_sec = re.search(r"###\s*Missões[^\n]*\n(.*?)(?=\n###|\n##|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        return []

    sec_content = m_sec.group(1)
    quests: List[Dict[str, Any]] = []

    # Linhas de missão: * **[MAIN] Título** | Campo: Valor | ...
    # Suporta identificador opcional explícito: * **[Q1] [MAIN] Título**
    quest_header_pat = re.compile(
        r"^\*\s*\*\*(?:\[(?P<exp_id>Q\d+)\]\s*)?\[(?P<type>MAIN|SIDE|PERSONAL|FACTION)\]\s+(?P<title>[^*|\n]+)\*\*(?P<rest>[^\n]*)",
        re.IGNORECASE,
    )
    obj_pat = re.compile(r"^\s{2,}\*\s*\[(?P<check>[ xX])\]\s*(?P<text>[^\n]+)")

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
            qid = exp_id if exp_id else f"Q{quest_counter}"
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

            current_quest = {
                "id": qid,
                "title": title,
                "type": raw_type,
                "status": status,
                "phase": fields.get("fase", ""),
                "contractor": fields.get("contratante", ""),
                "clock": fields.get("relógio", fields.get("relogio", "")),
                "reward": reward,
                "reward_xp": parse_reward_xp(reward) or (150 if raw_type == "MAIN" else (60 if raw_type == "SIDE" else 50)),
                "last_progress": fields.get("último progresso", fields.get("ultimo progresso", "")),
                "xp_paid": xp_paid_val,
                "objectives": [],
                "raw_header": line,
            }
            continue

        if current_quest:
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
    """Gera a linha canônica formatada de cabeçalho da missão."""
    qtype = quest.get("type", "MAIN").upper()
    title = quest.get("title", "Sem Título").strip()
    status = quest.get("status", "ACTIVE").upper()

    parts = [f"* **[{qtype}] {title}**"]
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
    """Realiza operações atômicas no bloco de Missões em diario.md.
    
    Ações suportadas:
    - 'add': Cria nova missão.
    - 'add_objective': Adiciona objetivo a uma missão existente.
    - 'check': Marca um objetivo como concluído [x].
    - 'complete': Transiciona status para COMPLETED e opcionalmente grava XP Pago.
    - 'fail': Transiciona status para FAILED com motivo.
    - 'block': Transiciona status para BLOCKED com motivo.
    - 'reopen': Reabre missão para ACTIVE com motivo auditado.
    - 'set_xp_paid': Crava carimbo de XP pago para idempotência.
    """
    if not diario_path.exists():
        return {"error": f"Arquivo {diario_path} não encontrado"}

    text = diario_path.read_text(encoding="utf-8")

    # Garante que a seção de Missões existe em diario.md
    if SECTION_HEADER.lower() not in text.lower() and not re.search(r"###\s*Missões", text, re.IGNORECASE):
        # Insere antes de ### Histórico de Turnos se presente
        m_hist = re.search(r"(###\s*Histórico de Turnos)", text, re.IGNORECASE)
        if m_hist:
            ins_pos = m_hist.start()
            text = text[:ins_pos] + f"{SECTION_HEADER}\n\n" + text[ins_pos:]
        else:
            # Insere após ### Relógios de Ameaça & Prazos ou no fim do cabeçalho de cena
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

    # Parseia missões atuais
    diario_path.write_text(text, encoding="utf-8")
    existing_quests = parse_quests_from_diario(diario_path)

    # 1. Adicionar nova missão
    if action == "add":
        clean_type = (quest_type or "main").strip().upper()
        if clean_type not in VALID_QUEST_TYPES:
            clean_type = "MAIN"
        new_id = f"Q{len(existing_quests) + 1}"
        new_q = {
            "id": new_id,
            "title": title.strip(),
            "type": clean_type,
            "status": "ACTIVE",
            "phase": phase.strip() or "Início",
            "contractor": contractor.strip(),
            "clock": clock.strip(),
            "reward": reward.strip() or ("150 XP" if clean_type == "MAIN" else "60 XP"),
            "last_progress": f"Turno {current_turn}" if current_turn else "",
            "xp_paid": None,
        }
        header_line = format_quest_header(new_q)
        content_lines = [header_line]
        if objective.strip():
            content_lines.append(f"  * [ ] {objective.strip()}")

        quest_block = "\n" + "\n".join(content_lines) + "\n"

        # Localiza o cabeçalho da seção
        m_sec = re.search(r"(###\s*Missões[^\n]*\n)", text, re.IGNORECASE)
        if m_sec:
            ins_pos = m_sec.end()
            text = text[:ins_pos] + quest_block + text[ins_pos:]
        else:
            text += f"\n\n{SECTION_HEADER}\n" + quest_block

        diario_path.write_text(text, encoding="utf-8")
        return {"action": "quest_added", "quest_id": new_id, "title": title}

    # Para demais ações, localiza a missão alvo
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
        # Acha a posição do cabeçalho da missão no texto
        m_head = re.search(re.escape(target_q["raw_header"]), text)
        if not m_head:
            return {"error": "Cabeçalho da missão não localizado no texto"}
        # Procura onde terminam os objetivos daquela missão
        end_pos = m_head.end()
        # Avança pelas linhas de objetivos existentes
        rem = text[end_pos:]
        lines = rem.splitlines(keepends=True)
        insert_offset = 0
        for l in lines:
            if re.match(r"^\s{2,}\*\s*\[", l):
                insert_offset += len(l)
            else:
                break
        final_pos = end_pos + insert_offset
        text = text[:final_pos] + f"\n{obj_line}" + text[final_pos:]
        diario_path.write_text(text, encoding="utf-8")
        return {"action": "objective_added", "quest_id": target_q["id"], "objective": objective.strip()}

    # 3. Marcar objetivo como concluído (check)
    if action == "check":
        if check_index is None or check_index < 1 or check_index > len(target_q["objectives"]):
            return {"error": f"Índice de objetivo {check_index} inválido para missão {target_q['id']}"}
        obj = target_q["objectives"][check_index - 1]
        old_obj_text = obj["text"]
        
        # Regex para substituir [ ] pelo [x] daquele objetivo específico
        pat = rf"(\s*\*\s*\[)\s*(\]\s*{re.escape(old_obj_text)})"
        m = re.search(pat, text)
        if not m:
            return {"error": f"Objetivo '{old_obj_text}' não encontrado no diário"}
        text = text[:m.start(1)] + m.group(1).replace("[", "[") + "x" + text[m.end(1) + 1:]
        
        # Atualiza Último Progresso no cabeçalho se current_turn foi fornecido
        if current_turn:
            target_q["last_progress"] = f"Turno {current_turn}"
            new_header = format_quest_header(target_q)
            text = text.replace(target_q["raw_header"], new_header)

        diario_path.write_text(text, encoding="utf-8")
        return {"action": "objective_checked", "quest_id": target_q["id"], "index": check_index, "text": old_obj_text}

    # 4. Transições de status (complete, fail, block, reopen, set_xp_paid)
    if action in ("complete", "fail", "block", "reopen", "set_xp_paid"):
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
        elif action == "reopen":
            target_q["status"] = "ACTIVE"
            if current_turn:
                target_q["last_progress"] = f"Turno {current_turn} (Reaberta: {reason or 'Novos indícios'})"
        elif action == "set_xp_paid":
            target_q["xp_paid"] = xp_paid

        new_header = format_quest_header(target_q)
        text = text.replace(target_q["raw_header"], new_header)
        diario_path.write_text(text, encoding="utf-8")
        return {
            "action": f"quest_{action}",
            "quest_id": target_q["id"],
            "new_status": target_q["status"],
            "xp_paid": target_q.get("xp_paid"),
        }

    return {"error": f"Ação '{action}' desconhecida"}
