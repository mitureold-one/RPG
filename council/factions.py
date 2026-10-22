"""council/factions.py: Domínio de Facções, Reputação Numérica e Agência Off-Screen (RPGPRO).

Implementa:
- Parsing e persistência de facções estruturadas em mundo.md (Poder, Escala, Relógios, Rivais).
- Parsing e atualização de reputação (-3 a +3), Favores e Débitos em ficha.md.
- Ledger auditável de reputação em diario.md.
- Turno de Facções Off-Screen (tick de mundo).
- Injeção de contexto político para o prepare.
Totalmente em Python Standard Library (sem dependências externas).
"""

import re
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
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
FACTION_LEDGER_HEADER: str = "### Registro de Reputação & Facções"
VALID_SCALES: set = {"local", "urbano", "regional", "continental", "global", "planar"}


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

    # 1. Procura número explícito (+2, -1, 3, etc)
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


# ==============================================================================
# 1. Parsing & Manipulação de Facções em mundo.md
# ==============================================================================

def parse_factions_from_mundo(mundo_path: Path) -> List[Dict[str, Any]]:
    """Extrai todas as facções declaradas em mundo.md sob '## 4. Facções, Forças Ativas & Alianças'."""
    if not mundo_path.exists():
        return []

    text = mundo_path.read_text(encoding="utf-8")
    m_sec = re.search(r"##\s*4\.\s*Facções[^\n]*\n(.*?)(?=\n###|\n##\s*\d|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        # Fallback para qualquer seção com Facções
        m_sec = re.search(r"##[^\n]*Facções[^\n]*\n(.*?)(?=\n###|\n##\s*\d|\Z)", text, re.IGNORECASE | re.DOTALL)
        if not m_sec:
            return []

    sec_text = m_sec.group(1)

    factions = []
    # Padrão flexível: * **[TAG] Nome:** Descrição | Poder: N | Escala: S | Relógio: C
    # Também suporta sem tag: * **Nome:** Descrição
    lines = sec_text.splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean.startswith(("*", "-")):
            continue
        # Ignora subtítulos de dinâmicas
        if line_clean.startswith("###") or "Dinâmica Inter-Facções" in line_clean or "Dinamica" in line_clean:
            continue

        raw_tag = ""
        name = ""
        body = ""

        # 1. Padrão canônico bold: * **[TAG] Nome:** Descrição ou * **Nome:** Descrição
        m_line = re.match(r"^[\*\-]\s*\*\*(?:\[([^\]]+)\]\s*)?([^*:]+)(?::)?\*\*(?:\s*:\s*)?\s*(.*)$", line_clean)
        if m_line:
            raw_tag = (m_line.group(1) or "").strip()
            name = m_line.group(2).strip().rstrip(":")
            body = m_line.group(3).strip()
        else:
            # 2. Padrão flexível com travessão ou texto simples: - **[TAG] Nome** (Poder...) — Descrição ou * Nome: Descrição
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

        # Se o body começar com (Poder: X, Escala: Y...) — Descrição
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
        # Se a seção ## 4. Facções não existir, cria
        m_sec = re.search(r"(##\s*4\.\s*Facções[^\n]*\n)", text, re.IGNORECASE)
        if not m_sec:
            m_sec = re.search(r"(##[^\n]*Facções[^\n]*\n)", text, re.IGNORECASE)

        if m_sec:
            insert_pos = m_sec.end()
            text = text[:insert_pos] + f"{new_line}\n" + text[insert_pos:]
        else:
            # Insere antes da seção 5 ou no fim
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


# ==============================================================================
# 2. Parsing & Manipulação de Reputação em ficha.md
# ==============================================================================

def parse_reputation_from_ficha(ficha_path: Path) -> Dict[str, Dict[str, Any]]:
    """Extrai a reputação do protagonista com facções sob '### Vínculos, Laços & Matriz Relacional' em ficha.md."""
    reputations: Dict[str, Dict[str, Any]] = {}
    if not ficha_path.exists():
        return reputations

    text = ficha_path.read_text(encoding="utf-8")
    m_vinc = re.search(r"###\s*Vínculos[^\n]*\n(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_vinc:
        return reputations

    vinc_text = m_vinc.group(1)

    # 1. Tenta extrair formato detalhado em sub-bullets (Canônico)
    # * **[TAG] Nome:** +2 (Aliado) | Favores: 1 | Débitos: 0
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
            raw_favors = m.group(5)
            raw_debts = m.group(6)

            score = clamp_reputation(int(raw_score)) if raw_score is not None else legacy_label_to_score(raw_tier)
            tier = score_to_tier_name(score)
            favors = max(0, int(raw_favors)) if raw_favors is not None else 0
            debts = max(0, int(raw_debts)) if raw_debts is not None else 0

            entry = {
                "tag": tag or normalize_ascii_slug(name),
                "name": name,
                "score": score,
                "tier": tier,
                "favors": favors,
                "debts": debts,
                "social_dc_modifier": SOCIAL_DC_MODIFIERS.get(score, 0),
                "suggested_variant": SUGGESTED_VARIANTS.get(score, "normal"),
            }
            reputations[name.lower()] = entry
            if tag:
                reputations[tag.lower()] = entry
        return reputations

    # 2. Fallback para linha única legada:
    # * **Reputação com Facções:** Facção 1 (Status 1), Facção 2 (Status 2)
    m_uni = re.search(r"\*\s*\*\*Reputa[çc][ãa]o\s*com\s*Fac[çc][õo]es:\*\*\s*([^\n]+)", vinc_text, re.IGNORECASE)
    if m_uni:
        items = re.split(r",\s*(?=[^()]*\()", m_uni.group(1).strip())
        for it in items:
            it_clean = it.strip().rstrip(".")
            m_it = re.search(r"^(.*?)\s*\(([^)]+)\)$", it_clean)
            if m_it:
                f_name = m_it.group(1).strip()
                f_label = m_it.group(2).strip()
                score = legacy_label_to_score(f_label)
                tier = score_to_tier_name(score)
                tag = normalize_ascii_slug(f_name)
                entry = {
                    "tag": tag,
                    "name": f_name,
                    "score": score,
                    "tier": tier,
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

    # Localiza a seção de vínculos
    m_vinc = re.search(r"(###\s*Vínculos[^\n]*\n)(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_vinc:
        return {"error": "Seção '### Vínculos' não encontrada em ficha.md"}

    sec_header = m_vinc.group(1)
    sec_body = m_vinc.group(2)

    # Verifica se já há sub-bullet desta facção
    pat_existing = re.compile(
        rf"^\s{{2,}}\*\s*\*\*(?:\[(?:{re.escape(final_tag)}|[^\]]+)\]\s*|\s*){re.escape(clean_name)}:?\*\*:?[^\n]*$",
        re.MULTILINE | re.IGNORECASE,
    )
    if pat_existing.search(sec_body):
        new_sec_body = pat_existing.sub(new_sub_bullet, sec_body, count=1)
    else:
        # Verifica se há o cabeçalho "* **Reputação com Facções:**"
        m_rep_head = re.search(r"(\*\s*\*\*Reputa[çc][ãa]o\s*com\s*Fac[çc][õo]es:\*\*[^\n]*)", sec_body, re.IGNORECASE)
        if m_rep_head:
            orig_rep_line = m_rep_head.group(1)
            # Se for linha legada com texto inline, converte para cabeçalho limpo + sub-bullet
            if "(" in orig_rep_line:
                # Transforma a linha em cabeçalho puro e anexa os existentes convertidos
                other_bullets = []
                for f_k, f_v in existing_reps.items():
                    if f_v["name"].lower() != clean_name.lower() and f_k == f_v["name"].lower():
                        sc_fmt = f"+{f_v['score']}" if f_v["score"] > 0 else str(f_v["score"])
                        other_bullets.append(f"  * **[{f_v['tag']}] {f_v['name']}:** {sc_fmt} ({f_v['tier']}) | Favores: {f_v['favors']} | Débitos: {f_v['debts']}")
                all_bullets = "\n".join(other_bullets + [new_sub_bullet])
                new_sec_body = sec_body.replace(orig_rep_line, f"* **Reputação com Facções:**\n{all_bullets}", 1)
            else:
                # Insere logo abaixo da linha de cabeçalho
                insert_idx = m_rep_head.end()
                new_sec_body = sec_body[:insert_idx] + f"\n{new_sub_bullet}" + sec_body[insert_idx:]
        else:
            # Anexa no final da seção de vínculos
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


# ==============================================================================
# 3. Ledger de Reputação & Histórico em diario.md
# ==============================================================================

def parse_faction_ledger_from_diario(diario_path: Path) -> List[Dict[str, Any]]:
    """Extrai todas as mutações históricas de reputação sob '### Registro de Reputação & Facções' em diario.md."""
    if not diario_path.exists():
        return []

    text = diario_path.read_text(encoding="utf-8")
    m_sec = re.search(r"###\s*Registro\s*de\s*Reputa[çc][ãa]o[^\n]*\n(.*?)(?=\n###|\n##|\Z)", text, re.IGNORECASE | re.DOTALL)
    if not m_sec:
        return []

    sec_text = m_sec.group(1)
    pattern = re.compile(
        r"^\*\s*\*\*\[(?:Turno\s*)?(\d+)\]\*\*\s*([^:]+):\s*([+-]?\d+)\s*Reputa[çc][ãa]o[^(]*\((?:[+-]?\d+\s*->\s*)?([+-]?\d+)\s*\[([^\]]+)\]\)(?:.*?Favores:\s*([+-]?\d+))?(?:.*?D[eé]bitos:\s*([+-]?\d+))?(?:.*?Motivo:\s*([^|\n]+))?(?:.*?Miss[ãa]o:\s*([^|\n]+))?",
        re.MULTILINE | re.IGNORECASE,
    )

    entries = []
    for m in pattern.finditer(sec_text):
        turn = int(m.group(1))
        fac = m.group(2).strip()
        delta_rep = int(m.group(3))
        res_score = int(m.group(4))
        tier = m.group(5).strip()
        delta_fav = int(m.group(6)) if m.group(6) else 0
        delta_deb = int(m.group(7)) if m.group(7) else 0
        reason = (m.group(8) or "").strip()
        qid = (m.group(9) or "").strip()

        entries.append({
            "turn": turn,
            "faction": fac,
            "delta_rep": delta_rep,
            "new_score": res_score,
            "tier": tier,
            "delta_favors": delta_fav,
            "delta_debts": delta_deb,
            "reason": reason,
            "quest_id": qid,
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

    # Formata campos
    rep_sign = f"+{delta_rep}" if delta_rep > 0 else str(delta_rep)
    old_score = new_score - delta_rep
    old_sign = f"+{old_score}" if old_score > 0 else str(old_score)
    new_sign = f"+{new_score}" if new_score > 0 else str(new_score)

    entry_parts = [
        f"* **[Turno {cur_turn}]** {faction_name}: {rep_sign} Reputação ({old_sign} -> {new_sign} [{tier_name}])"
    ]
    if delta_favors != 0:
        f_sign = f"+{delta_favors}" if delta_favors > 0 else str(delta_favors)
        entry_parts.append(f"Favores: {f_sign}")
    if delta_debts != 0:
        d_sign = f"+{delta_debts}" if delta_debts > 0 else str(delta_debts)
        entry_parts.append(f"Débitos: {d_sign}")
    if reason.strip():
        entry_parts.append(f"Motivo: {reason.strip()}")
    if quest_id.strip():
        entry_parts.append(f"Missão: {quest_id.strip()}")

    entry_line = " | ".join(entry_parts)

    if FACTION_LEDGER_HEADER.lower() not in text.lower():
        # Insere antes de Histórico de Turnos
        m_hist = re.search(r"(###\s*Histórico de Turnos)", text, re.IGNORECASE)
        if m_hist:
            idx = m_hist.start()
            text = text[:idx] + f"{FACTION_LEDGER_HEADER}\n\n{entry_line}\n\n" + text[idx:]
        else:
            text = text.rstrip() + f"\n\n{FACTION_LEDGER_HEADER}\n\n{entry_line}\n"
    else:
        # Insere no final da seção existente
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


# ==============================================================================
# 4. Turno de Facções Off-Screen (Tick de Mundo)
# ==============================================================================

def simulate_faction_tick(campaign_info: Dict[str, Any]) -> Dict[str, Any]:
    """Avança deterministicamente relógios narrativos de facções com base em seu atributo de Poder (1 a 5).
    
    Regra de Agência Off-Screen Determinística:
    - Poder 4 ou 5: avança 1 passo garantido no tick.
    - Poder 2 ou 3: avança 1 passo se o relógio já foi iniciado em cena (current >= 1).
    - Poder 1: só avança em cena sob intervenção direta do protagonista.
    """
    mundo_path = campaign_info["mundo"]
    diario_path = campaign_info["diario"]

    if not mundo_path.exists() or not diario_path.exists():
        return {"error": "Arquivos mundo.md ou diario.md não localizados."}

    from council.ssot import parse_clocks_from_diario, upsert_clock_in_diario, parse_diario_md

    factions = parse_factions_from_mundo(mundo_path)
    clocks = parse_clocks_from_diario(diario_path)
    clock_map = {c["name"].lower(): c for c in clocks}

    advancements = []
    breaches = []

    for f in factions:
        c_name = f.get("clock")
        if not c_name:
            continue
        c_match = clock_map.get(c_name.lower())
        if not c_match or c_match.get("status") != "ACTIVE":
            continue

        power = f.get("power", 3)
        should_advance = False
        if power >= 4:
            should_advance = True
        elif power >= 2 and c_match["current"] >= 1:
            should_advance = True

        if should_advance:
            res = upsert_clock_in_diario(diario_path, c_match["name"], advance=1, create_if_missing=False)
            adv = {
                "faction": f["name"],
                "power": power,
                "clock": c_match["name"],
                "previous_progress": c_match["progress"],
                "new_progress": f"{res['current']}/{res['max']}",
                "status": res["status"],
            }
            advancements.append(adv)
            if res.get("status") == "BREACHED":
                breaches.append(adv)

    if advancements:
        cur_turn = parse_diario_md(diario_path).get("last_turn_num", 1)
        d_text = diario_path.read_text(encoding="utf-8")
        lines_to_add = [f"* **Tick Off-Screen (Turno {cur_turn}):**"]
        for adv in advancements:
            b_note = " [Gatilho de Ruptura Disparado!]" if adv.get("status") == "BREACHED" else ""
            lines_to_add.append(
                f"  * **{adv['faction']}:** Avançou relógio '{adv['clock']}' para {adv['new_progress']} (Poder {adv['power']}){b_note}."
            )
        entry_block = "\n".join(lines_to_add)

        sec_header = "### Movimentações de Facções Off-Screen"
        if sec_header in d_text:
            m_sec = re.search(rf"({re.escape(sec_header)}[^\n]*\n)(.*?)(?=\n###|\Z)", d_text, re.DOTALL)
            if m_sec:
                header_part = m_sec.group(1)
                body_part = m_sec.group(2)
                new_sec = header_part + body_part.rstrip() + "\n" + entry_block + "\n"
                d_text = d_text[:m_sec.start()] + new_sec + d_text[m_sec.end():]
            else:
                d_text = d_text.rstrip() + f"\n\n{sec_header}\n{entry_block}\n"
        else:
            if "### Histórico de Turnos" in d_text:
                d_text = d_text.replace("### Histórico de Turnos", f"{sec_header}\n{entry_block}\n\n### Histórico de Turnos", 1)
            else:
                d_text = d_text.rstrip() + f"\n\n{sec_header}\n{entry_block}\n"
        atomic_write_text(diario_path, d_text)

    return {
        "campaign": campaign_info.get("id", ""),
        "operation": "faction_tick",
        "advancements": advancements,
        "breaches": breaches,
    }


# ==============================================================================
# 5. Injeção de Contexto Político para o prepare
# ==============================================================================

def resolve_scene_factions(
    campaign_info: Dict[str, Any],
    scene_npcs: List[str],
    location: str,
) -> List[Dict[str, Any]]:
    """Identifica facções representadas na cena por NPCs presentes ou território e calcula modificadores sociais."""
    mundo_path = campaign_info.get("mundo")
    ficha_path = campaign_info.get("ficha")
    npcs_path = campaign_info.get("npcs")

    if not mundo_path or not mundo_path.exists():
        return []

    factions = parse_factions_from_mundo(mundo_path)
    if not factions:
        return []
    reputations = parse_reputation_from_ficha(ficha_path) if ficha_path and ficha_path.exists() else {}

    # Mapeia afiliação de NPCs de npcs.md com fallback de inferência
    from council.narrator import parse_npcs_md
    all_npcs = parse_npcs_md(npcs_path) if npcs_path and npcs_path.exists() else []
    npc_faction_map = {}
    for n in all_npcs:
        n_low = n["name"].lower().strip()
        n_fac = (n.get("faction") or "").strip()

        # Se não tiver facção explícita ou for genérica
        if not n_fac or n_fac.lower() in ("independente", "neutro", "nenhuma", "-"):
            for f in factions:
                if n_low in f.get("description", "").lower():
                    n_fac = f["name"]
                    break
            if not n_fac or n_fac.lower() in ("independente", "neutro", "nenhuma", "-"):
                npc_profile = f"{n.get('role', '')} {n.get('classification', '')} {n.get('summary', '')}".lower()
                for f in factions:
                    if f["name"].lower() in npc_profile or f["tag"].lower() in npc_profile:
                        n_fac = f["name"]
                        break

        if n_fac and n_fac.lower() not in ("independente", "neutro", "nenhuma", "-"):
            npc_faction_map[n_low] = n_fac

    matched_factions = []
    seen_tags = set()

    # 1. Resolução por NPCs presentes em cena
    for pres_name in scene_npcs:
        pres_low = pres_name.lower().strip()
        if not pres_low:
            continue
        matched_npc_fac = None
        for n_k, n_fac in npc_faction_map.items():
            if n_k in pres_low or pres_low in n_k:
                matched_npc_fac = n_fac
                break

        if not matched_npc_fac:
            for f in factions:
                if f["name"].lower() in pres_low:
                    matched_npc_fac = f["name"]
                    break

        if matched_npc_fac:
            for f in factions:
                if f["name"].lower() == matched_npc_fac.lower() or f["tag"].lower() == matched_npc_fac.lower():
                    if f["tag"] not in seen_tags:
                        seen_tags.add(f["tag"])
                        rep_data = reputations.get(f["name"].lower(), reputations.get(f["tag"].lower(), {}))
                        score = rep_data.get("score", 0)
                        tier = rep_data.get("tier", "Neutro")
                        favors = rep_data.get("favors", 0)
                        debts = rep_data.get("debts", 0)
                        dc_mod = SOCIAL_DC_MODIFIERS.get(score, 0)
                        variant = SUGGESTED_VARIANTS.get(score, "normal")

                        directive = "Postura diplomática neutra e pragmática."
                        if score >= 2:
                            directive = f"POSTURA OBRIGATÓRIA DE FACÇÃO ALIADA ({tier}): Membros desta facção agem com prestatividade, oferecem refúgio e colaboração armada."
                        elif score <= -2:
                            directive = f"POSTURA OBRIGATÓRIA DE FACÇÃO HOSTIL: Membros de {f['name']} tratam o protagonista como inimigo jurado ({score}). Proibida qualquer cordialidade, cooperação espontânea ou confiança sem coerção física ou chantagem comprovada."

                        matched_factions.append({
                            "name": f["name"],
                            "tag": f["tag"],
                            "score": score,
                            "tier": tier,
                            "favors": favors,
                            "debts": debts,
                            "social_dc_mod": dc_mod,
                            "suggested_variant": variant,
                            "source": "npc",
                            "focal_members": [pres_name],
                            "members_in_scene": [pres_name],
                            "writer_directive": directive,
                        })
                    else:
                        for mf in matched_factions:
                            if mf["tag"] == f["tag"]:
                                if pres_name not in mf["members_in_scene"]:
                                    mf["members_in_scene"].append(pres_name)
                                    mf["focal_members"].append(pres_name)

    # 2. Resolução por Território / Localização (P1-B & P2-5)
    loc_clean = (location or "").strip()
    if loc_clean:
        loc_low = loc_clean.lower()
        stopwords_loc = {"posto", "zona", "ruas", "porto", "sala", "torre", "ponte", "castelo", "distrito", "vila", "cidade", "aposentos", "palacio", "quarto", "corredor"}
        loc_keywords = [w for w in re.findall(r"\w{4,}", loc_low) if w not in stopwords_loc]

        for f in factions:
            f_desc_low = f.get("description", "").lower()
            f_name_low = f["name"].lower()
            is_territory = False

            if f_name_low in loc_low:
                is_territory = True
            elif loc_low in f_desc_low:
                is_territory = True
            elif any(kw in f_desc_low for kw in loc_keywords):
                is_territory = True

            if is_territory:
                if f["tag"] not in seen_tags:
                    seen_tags.add(f["tag"])
                    rep_data = reputations.get(f["name"].lower(), reputations.get(f["tag"].lower(), {}))
                    score = rep_data.get("score", 0)
                    tier = rep_data.get("tier", "Neutro")
                    favors = rep_data.get("favors", 0)
                    debts = rep_data.get("debts", 0)
                    dc_mod = SOCIAL_DC_MODIFIERS.get(score, 0)
                    variant = SUGGESTED_VARIANTS.get(score, "normal")

                    directive = f"TERRITÓRIO DOMINADO POR {f['name']} ({tier}): O protagonista opera sob jurisdição e vigilância de {f['name']} em '{loc_clean}'."
                    if score >= 2:
                        directive += " Facilidade de trânsito, refúgio seguro e cooperação da população local."
                    elif score <= -2:
                        directive += " Território hostil: patrulhas ativas, desconfiança ostensiva e risco imediato de emboscada ou denúncia."
                    else:
                        directive += f" Modificador social {dc_mod} aplicado em interações públicas."

                    matched_factions.append({
                        "name": f["name"],
                        "tag": f["tag"],
                        "score": score,
                        "tier": tier,
                        "favors": favors,
                        "debts": debts,
                        "social_dc_mod": dc_mod,
                        "suggested_variant": variant,
                        "source": "territory",
                        "territory_in_scene": loc_clean,
                        "focal_members": [],
                        "members_in_scene": [],
                        "writer_directive": directive,
                    })
                else:
                    for mf in matched_factions:
                        if mf["tag"] == f["tag"]:
                            mf["territory_in_scene"] = loc_clean

    return matched_factions
