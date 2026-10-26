"""resources/npcs/parser.py: Extração e parsing de perfis e atualizações de NPCs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

_NPC_SUBFIELDS = (
    "atitude",
    "atitudes",
    "relação",
    "relacao",
    "relação com protagonista",
    "relacao com protagonista",
    "vínculos",
    "vinculos",
    "vínculo",
    "vinculo",
    "laços",
    "lacos",
    "laço",
    "laco",
)

_NPC_SEPARATOR_RE = re.compile(
    r"\s*;\s*(?!(?:" + "|".join(re.escape(s) for s in _NPC_SUBFIELDS) + r")\s*:)"
    r"(?=[A-ZÀ-Ú][^:]{1,45}:)",
    re.IGNORECASE,
)

_NPC_PIPE_RE = re.compile(
    r"\s*\|\s*(?!(?:\s*)(?:" + "|".join(re.escape(s) for s in _NPC_SUBFIELDS) + r")\s*:)",
    re.IGNORECASE,
)


def extract_md_field(block_text: str, patterns: tuple[str, ...]) -> str:
    """Extrai o valor de um campo '* **Campo:** Valor' dentro de um bloco de NPC."""
    for pat in patterns:
        m = re.search(rf"\*\s*\*\*{pat}[^*]*:\*\*\s*([^\n]+)", block_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def extract_npc_bonds(body: str) -> dict[str, str]:
    """Extrai mapa de vínculos relacionais {alvo: descricao} de um bloco de NPC."""
    bonds = {}
    m_sec = re.search(r"\*\s*\*\*(?:Vínculos|Matriz Relacional|Relações|Laços)[^*]*:\*\*\s*(.*?)(?=\n\*|\Z)", body, re.DOTALL | re.IGNORECASE)
    if m_sec:
        sec_text = m_sec.group(1).strip()
        for line in sec_text.splitlines():
            line_s = line.strip().lstrip("* -").strip()
            if not line_s:
                continue
            if ":" in line_s:
                target, desc = line_s.split(":", 1)
                bonds[target.strip()] = desc.strip()
            elif "—" in line_s:
                target, desc = line_s.split("—", 1)
                bonds[target.strip()] = desc.strip()

    m_protag = re.search(r"\*\s*\*\*Relação com Protagonista:\*\*\s*([^\n]+)", body, re.IGNORECASE)
    if m_protag:
        bonds["Protagonista"] = m_protag.group(1).strip()

    if not bonds:
        m_dyn = re.search(r"\*\s*\*\*Atritos[^*]*:\*\*\s*([^\n]+)", body, re.IGNORECASE)
        if m_dyn:
            raw = m_dyn.group(1).strip()
            for item in raw.split(";"):
                item = item.strip()
                if ":" in item:
                    target, desc = item.split(":", 1)
                    bonds[target.strip()] = desc.strip()
                elif "—" in item:
                    target, desc = item.split("—", 1)
                    bonds[target.strip()] = desc.strip()
    return bonds


def parse_npcs_md(npcs_path: Path) -> List[Dict[str, Any]]:
    """Extrai perfil estruturado dos NPCs cadastrados em npcs.md."""
    if not npcs_path.exists():
        return []
    text = npcs_path.read_text(encoding="utf-8")
    npcs = []
    blocks = re.split(r"^###\s+", text, flags=re.MULTILINE)
    for b in blocks[1:]:
        lines = [line.strip() for line in b.strip().splitlines() if line.strip()]
        if not lines:
            continue
        name = lines[0]
        body = "\n".join(lines[1:])
        details = " ".join(lines[1:])
        will = extract_md_field(body, ("Vontade Própria", "Agenda Autônoma", "Motivação"))
        weakness = extract_md_field(body, ("Fraquezas", "Fraqueza", "Pontos Cegos", "Ponto Cego"))
        psychology = extract_md_field(body, ("Psicologia",))
        dynamics = extract_md_field(body, ("Atritos", "Relações", "Dinâmica Social", "Laços"))
        attitude = extract_md_field(body, ("Atitude Atual",))
        faction = extract_md_field(body, ("Facção / Afiliação", "Facção", "Faccao / Afiliacao", "Faccao", "Afiliação", "Afiliacao"))
        bonds = extract_npc_bonds(body)
        is_stub = "Introduzido durante a crônica" in details or "Personagem em Cena" in details
        npcs.append({
            "name": name,
            "attitude": attitude,
            "faction": faction,
            "psychology": psychology,
            "will": will,
            "weakness": weakness,
            "dynamics": dynamics,
            "bonds": bonds,
            "is_stub": is_stub,
            "summary": details,
        })
    return npcs


def parse_npc_update_fields(raw_update: str) -> dict[str, str]:
    """Extrai subcampos conhecidos de um corpo de atualização de NPC."""
    body = (raw_update or "").strip().rstrip(".")
    m_rel = re.search(
        r"(?:relação|relacao|relação com protagonista|relacao com protagonista)\s*:\s*([^;|]+)",
        body,
        re.IGNORECASE,
    )
    m_att = re.search(r"atitude\s*:\s*([^;|]+)", body, re.IGNORECASE)
    m_bonds = re.search(r"(?:vínculos|vinculos|laços|lacos)\s*:\s*([^;|]+)", body, re.IGNORECASE)
    fields = {}
    if m_att:
        fields["attitude"] = m_att.group(1).strip()
    if m_rel:
        fields["relation"] = m_rel.group(1).strip()
    if m_bonds:
        fields["bonds"] = m_bonds.group(1).strip()
    if fields:
        return fields
    return {"update": body}


def split_npc_updates(npc_updates_str: str) -> List[Tuple[str, str]]:
    """Divide 'NPC1: texto; NPC2: texto | NPC3: texto' sem confundir subcampos."""
    if not npc_updates_str:
        return []
    parts = []
    for block in _NPC_PIPE_RE.split(npc_updates_str.strip()):
        parts.extend(_NPC_SEPARATOR_RE.split(block))
    pairs = []
    for p in parts:
        p = p.strip()
        if ":" not in p:
            continue
        name, body = p.split(":", 1)
        name, body = name.strip(), body.strip().rstrip(".")
        if not name or not body:
            continue
        if name.lower() in _NPC_SUBFIELDS:
            continue
        pairs.append((name, body))
    return pairs


__all__ = [
    "_NPC_PIPE_RE",
    "_NPC_SEPARATOR_RE",
    "_NPC_SUBFIELDS",
    "extract_md_field",
    "extract_npc_bonds",
    "parse_npc_update_fields",
    "parse_npcs_md",
    "split_npc_updates",
]
