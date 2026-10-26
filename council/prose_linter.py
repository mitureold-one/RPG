"""council/prose_linter.py: Lints de estilo literário, paradoxos temporais e auditoria de missões/XP."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from council.quests import parse_quests_from_diario, parse_xp_ledger_from_diario
from council.ssot import parse_progression_from_ficha

EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001F5FF"
    r"\U0001F600-\U0001F64F"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F700-\U0001F77F"
    r"\U0001F780-\U0001F7FF"
    r"\U0001F800-\U0001F8FF"
    r"\U0001F900-\U0001F9FF"
    r"\U0001FA00-\U0001FA6F"
    r"\U0001FA70-\U0001FAFF"
    r"\u2600-\u26FF"
    r"\u2700-\u27BF]"
)

SCRIPT_BRACKET_PATTERN = re.compile(
    r"(?m)^\s*(?:\*\s*)?(?:\*\*[^*]+\*\*\s*)?\[([A-Za-zÀ-ÖØ-öø-ÿ\s]{2,30})\]\s*:(?!\*\*)\s*(.+)"
)
SCRIPT_UNBRACKETED_PATTERN = re.compile(
    r"(?m)^\s*(?:\*\s*)?(?:\*\*[^*]+\*\*\s*)?([A-ZÀ-ÖØ-ß][A-Za-zÀ-ÖØ-öø-ÿ\s]{1,30})\s*:\s*(.+)"
)

FOURTH_WALL_PATTERN = re.compile(
    r"(?i)\b(?:o\s+que\s+(?:(?:você|voce|vc)\s+)?(?:faz|fará|fara|vai\s+fazer|decide|escolhe)|"
    r"qual\s+(?:é\s+a\s+sua|a\s+sua|é\s+sua|sua)\s+(?:ação|acao|decisão|decisao|escolha)|"
    r"como\s+(?:(?:você|voce|vc)\s+)?(?:reage|responde))\b[^\n.!?]*\??",
    re.IGNORECASE,
)

RESERVED_METADATA_KEYS = {
    "turno", "vitais", "data", "data & local", "presentes", "fatos",
    "mudança de estado", "mudanca de estado", "marco", "status",
    "gatilho", "atores", "título", "titulo", "fase", "pergunta central",
    "conflito central", "questão", "questao", "nota", "cena", "arco",
    "hp", "stamina", "ce", "pv", "mp", "rad",
    "atitude", "relação", "relacao", "local", "resumo", "custo", "item", "tempo",
    "autor", "personagem", "classe", "grau", "nível", "nivel",
}

SPEECH_VERBS = {
    "disse", "respondeu", "falou", "gritou", "murmurou", "sussurrou",
    "exclamou", "perguntou", "declarou", "afirmou", "adverte", "indaga",
    "prossegue", "comenta", "acrescentou", "retrucou", "rebateu", "ordenou",
    "anunciou", "avisa", "avisou", "lembra", "lembrou",
}

PT_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def check_prose_lints(
    text: str,
    context_label: str = "diario.md",
    known_speakers: set | list | None = None,
) -> list:
    """Audita violações duras de estilo literário: emojis, formato script [Nome]: e perguntas de 4ª parede."""
    issues = []
    if not text:
        return issues

    known_lower = {s.lower().strip() for s in known_speakers} if known_speakers else None

    m_emoji = EMOJI_PATTERN.search(text)
    if m_emoji:
        emoji_char = m_emoji.group(0)
        issues.append({
            "type": "EMOJI_DETECTED",
            "severity": "MEDIUM",
            "detail": (
                f"Caractere emoji detectado em {context_label} ('{emoji_char}'): "
                f"o estilo literário do RPGPRO exige prosa textual pura sem emojis."
            ),
        })

    m_bracket = SCRIPT_BRACKET_PATTERN.search(text)
    if m_bracket:
        bracket_name = m_bracket.group(1).strip()
        bracket_str = f"[{bracket_name}]:"
        issues.append({
            "type": "SCRIPT_FORMAT_DETECTED",
            "severity": "HIGH",
            "detail": (
                f"Formato teatral detectado em {context_label} ('{bracket_str}'): "
                f"utilize travessão literário (—) e diálogo integrado à narrativa em vez de '[Nome]:'."
            ),
        })
    else:
        for m_unbracket in SCRIPT_UNBRACKETED_PATTERN.finditer(text):
            raw_speaker = m_unbracket.group(1).strip()
            rest = m_unbracket.group(2).strip()
            speaker_low = raw_speaker.lower()

            if speaker_low in RESERVED_METADATA_KEYS:
                continue

            speaker_words = [w.lower() for w in re.split(r"\s+", raw_speaker) if w]
            if any(w in SPEECH_VERBS for w in speaker_words):
                continue

            is_script = False
            if known_lower is not None:
                if speaker_low in known_lower or any(speaker_low == k or speaker_low in k for k in known_lower):
                    is_script = True
            elif rest.startswith(('"', "'", "“", "”")):
                is_script = True

            if is_script:
                snippet = f"{raw_speaker}: {rest[:40]}"
                issues.append({
                    "type": "SCRIPT_FORMAT_DETECTED",
                    "severity": "HIGH",
                    "detail": (
                        f"Formato teatral detectado em {context_label} ('{snippet}'): "
                        f"utilize travessão literário (—) e diálogo integrado à narrativa em vez de '{raw_speaker}:'."
                    ),
                })
                break

    m_4th = FOURTH_WALL_PATTERN.search(text)
    if m_4th:
        question_str = m_4th.group(0).strip()
        issues.append({
            "type": "FOURTH_WALL_QUESTION",
            "severity": "MEDIUM",
            "detail": (
                f"Pergunta de quebra de quarta parede detectada em {context_label} ('{question_str}'): "
                f"encerre com impacto sensorial e gancho dramático aberto, sem recorrer ao clichê 'O que você faz?'."
            ),
        })

    return issues


def parse_pt_date(text: str):
    """Extrai (ano, mes, dia) de uma string de data em português (ex: '25 de Novembro de 2018')."""
    if not text:
        return None
    m = re.search(
        r"\b(\d{1,2})\s+de\s+(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+(\d{4}))?",
        text,
        re.IGNORECASE,
    )
    if m:
        day = int(m.group(1))
        month = PT_MONTHS[m.group(2).lower()]
        year = int(m.group(3)) if m.group(3) else None
        return (year, month, day)
    return None


def detect_temporal_paradoxes(current_dt_str: str, texts_to_scan: list) -> list:
    """Detecta de forma agnóstica se textos tratam uma data já passada no calendário da campanha como evento futuro."""
    cur_parsed = parse_pt_date(current_dt_str)
    if not cur_parsed or not cur_parsed[0]:
        return []
    cur_year, cur_month, cur_day = cur_parsed
    paradoxes = []
    future_markers = r"(?:antes\s+de|até\s+o\s+dia|ate\s+o\s+dia|para\s+a\s+noite\s+de|para\s+o\s+dia|aguardando\s+o\s+dia|programado\s+para(?:\s+a\s+noite\s+de)?)"
    pattern = rf"{future_markers}\s+(\d{{1,2}})\s+de\s+(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+(\d{{4}}))?"

    for label, txt in texts_to_scan:
        if not txt:
            continue
        for m in re.finditer(pattern, txt, re.IGNORECASE):
            d = int(m.group(1))
            mo = PT_MONTHS[m.group(2).lower()]
            yr = int(m.group(3)) if m.group(3) else cur_year
            if (yr, mo, d) < (cur_year, cur_month, cur_day):
                paradoxes.append(
                    f"Paradoxo temporal em {label}: a expressão '{m.group(0)}' trata {d:02d}/{mo:02d}/{yr} como futuro, mas o calendário atual da campanha já está em '{current_dt_str}' ({cur_day:02d}/{cur_month:02d}/{cur_year})."
                )
    return paradoxes


def audit_quests_and_xp_in_campaign(info: Dict[str, Any], diario: Dict[str, Any], diario_text: str) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    quests = parse_quests_from_diario(info["diario"])
    clock_map = {c["name"].lower(): c for c in diario.get("clocks", [])}
    for q in quests:
        if not q.get("objectives"):
            issues.append({
                "type": "QUEST_WITHOUT_OBJECTIVES",
                "severity": "MEDIUM",
                "detail": f"A missão '{q['title']}' ({q['id']}) foi cadastrada sem nenhum objetivo em sub-bullets [ ] no diário.",
            })

        if q.get("status") == "ACTIVE":
            if q.get("last_progress"):
                m_turn = re.search(r"Turno\s*(\d+)", q["last_progress"], re.IGNORECASE)
                if m_turn:
                    last_p_turn = int(m_turn.group(1))
                    if diario["last_turn_num"] - last_p_turn >= 10:
                        issues.append({
                            "type": "QUEST_STALE",
                            "severity": "LOW",
                            "detail": f"A missão ativa '{q['title']}' ({q['id']}) não registra progresso há mais de {diario['last_turn_num'] - last_p_turn} turnos (último: Turno {last_p_turn}).",
                        })

            if q.get("clock"):
                c_low = q["clock"].strip().lower()
                if c_low not in clock_map:
                    issues.append({
                        "type": "QUEST_CLOCK_LINK_BROKEN",
                        "severity": "HIGH",
                        "detail": f"A missão '{q['title']}' ({q['id']}) está vinculada ao relógio '{q['clock']}', mas este não consta em '### Relógios de Ameaça & Prazos'.",
                    })
                elif clock_map[c_low]["status"] == "BREACHED":
                    issues.append({
                        "type": "QUEST_OVERDUE",
                        "severity": "HIGH",
                        "detail": (
                            f"O relógio vinculado '{clock_map[c_low]['name']}' rompeu ({clock_map[c_low]['progress']}) "
                            f"enquanto a missão '{q['title']}' ({q['id']}) permanece com status ACTIVE. "
                            f"O Mestre deve arbitrar diegeticamente a falha (--quest-fail) ou nova fase de contingência."
                        ),
                    })

        raw_header = q.get("raw_header", "")
        if raw_header.lower().count("xp pago") > 1:
            issues.append({
                "type": "QUEST_REWARD_PAID_TWICE",
                "severity": "CRITICAL",
                "detail": f"Duplicidade de pagamento detectada na missão '{q['title']}' ({q['id']}): mais de um carimbo de 'XP Pago' presente na linha.",
            })

    if "Tentativa de pagamento duplicado de XP barrada" in diario_text:
        m_dup = re.search(r"Turno\s+(\d+)[^\n]*\n(?:[ \t]+\*[^\n]*\n)*?[ \t]+\*\s*\*\*Alerta:\*\*\s*Tentativa de pagamento duplicado de XP barrada", diario_text, re.IGNORECASE)
        t_num = m_dup.group(1) if m_dup else diario.get("last_turn_num", "?")
        issues.append({
            "type": "QUEST_REWARD_PAID_TWICE",
            "severity": "CRITICAL",
            "detail": f"Tentativa de pagamento duplicado de XP detectada no histórico (Turno {t_num}).",
        })

    prog = parse_progression_from_ficha(info["ficha"])
    ledger = parse_xp_ledger_from_diario(info["diario"])
    total_xp_paid_quests = sum(q.get("xp_paid") or 0 for q in quests)
    total_xp_ledger = sum(e.get("amount") or 0 for e in ledger)
    total_auditable_xp = total_xp_paid_quests + total_xp_ledger

    if total_auditable_xp > 0 and prog["xp"] != total_auditable_xp:
        issues.append({
            "type": "XP_MISMATCH",
            "severity": "HIGH",
            "detail": f"Divergência de XP: O total acumulado na ficha ({prog['xp']} XP) difere da soma dos créditos auditáveis no diário ({total_auditable_xp} XP = {total_xp_paid_quests} de missões + {total_xp_ledger} do registro).",
        })

    return issues


__all__ = [
    "EMOJI_PATTERN",
    "FOURTH_WALL_PATTERN",
    "PT_MONTHS",
    "RESERVED_METADATA_KEYS",
    "SCRIPT_BRACKET_PATTERN",
    "SCRIPT_UNBRACKETED_PATTERN",
    "SPEECH_VERBS",
    "audit_quests_and_xp_in_campaign",
    "check_prose_lints",
    "detect_temporal_paradoxes",
    "parse_pt_date",
]
