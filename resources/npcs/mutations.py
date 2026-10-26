"""resources/npcs/mutations.py: Mutações de Markdown para catálogo de NPCs (npcs.md)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from council.helpers import atomic_write_text
from resources.npcs.parser import split_npc_updates


def upsert_npc_to_md(
    npcs_path: Path,
    name: str,
    classification: str = "",
    role: str = "",
    faction: str = "",
    attitude: str = "",
    psychology: str = "",
    will: str = "",
    weakness: str = "",
    dynamics: str = "",
    appearance: str = "",
    bonds: str = "",
    relation: str = "",
) -> Dict[str, Any]:
    """Cadastra ou enriquece um NPC completo em npcs.md atomicamente."""
    if not npcs_path.exists():
        atomic_write_text(npcs_path, "# Catálogo de NPCs & Relações de Poder\n\n")
    text = npcs_path.read_text(encoding="utf-8")
    parts = re.split(r"(^###\s+[^\n]+)", text, flags=re.MULTILINE)
    header = parts[0]
    blocks = []
    for i in range(1, len(parts), 2):
        blocks.append([parts[i], parts[i + 1] if i + 1 < len(parts) else ""])

    field_specs = [
        ("Grau / Classificação", classification),
        ("Papel", role),
        ("Facção / Afiliação", faction),
        ("Atitude Atual", attitude),
        ("Psicologia & Tell", psychology),
        ("Vontade Própria & Agenda", will),
        ("Fraquezas & Pontos Cegos", weakness),
        ("Relação com Protagonista", relation),
        ("Vínculos & Matriz Relacional", bonds),
        ("Atritos & Laços com Outros NPCs", dynamics),
        ("Aparência & Voz", appearance),
    ]

    t_low = name.strip().lower()
    matched_heading = None
    for b in blocks:
        h_name = b[0].replace("###", "").strip()
        h_low = h_name.lower()
        if t_low == h_low or t_low in h_low or h_low in t_low:
            matched_heading = h_name
            for label, val in field_specs:
                if not val:
                    continue
                val_clean = val.strip().rstrip(".") + "."
                key_prefix = label.split("&")[0].split("/")[0].strip()
                if re.search(rf"\*\s*\*\*{re.escape(key_prefix)}[^*]*:\*\*\s*[^\n]+", b[1], re.IGNORECASE):
                    b[1] = re.sub(
                        rf"(\*\s*\*\*{re.escape(key_prefix)}[^*]*:\*\*\s*)[^\n]+",
                        rf"\g<1>{val_clean}",
                        b[1],
                        count=1,
                        flags=re.IGNORECASE,
                    )
                else:
                    b[1] = b[1].rstrip() + f"\n* **{label}:** {val_clean}\n\n"
            break

    if not matched_heading:
        matched_heading = name.strip()
        new_lines = [f"### {matched_heading}\n"]
        for label, val in field_specs:
            if val:
                val_clean = val.strip().rstrip(".") + "."
                new_lines.append(f"* **{label}:** {val_clean}\n")
        new_lines.append("\n")
        blocks.append([new_lines[0].rstrip("\n"), "\n" + "".join(new_lines[1:])])

    new_text = header + "".join(b[0] + b[1] for b in blocks)
    atomic_write_text(npcs_path, new_text)
    return {"status": "ok", "npc_upserted": matched_heading}


def apply_npc_updates_to_md(npcs_path: Path, npc_updates_str: str) -> List[str]:
    """Atualiza cada NPC individualmente em npcs.md (ou cria a seção se o NPC for novo)."""
    pairs = split_npc_updates(npc_updates_str)
    if not pairs or not npcs_path.exists():
        return []

    text = npcs_path.read_text(encoding="utf-8")
    parts = re.split(r"(^###\s+[^\n]+)", text, flags=re.MULTILINE)
    header = parts[0]
    blocks = []
    for i in range(1, len(parts), 2):
        blocks.append([parts[i], parts[i + 1] if i + 1 < len(parts) else ""])

    applied = []
    for target_name, raw_update in pairs:
        matched = False
        t_low = target_name.lower()

        att_val = ""
        rel_val = ""
        bonds_val = ""
        m_rel = re.search(r"(?:relação|relacao|relação com protagonista|relacao com protagonista)\s*:\s*([^;]+)", raw_update, re.IGNORECASE)
        m_att = re.search(r"atitude\s*:\s*([^;]+)", raw_update, re.IGNORECASE)
        m_bonds = re.search(r"(?:vínculos|vinculos|laços|lacos)\s*:\s*([^;]+)", raw_update, re.IGNORECASE)

        if m_rel or m_att or m_bonds:
            if m_att:
                att_val = m_att.group(1).strip()
            if m_rel:
                rel_val = m_rel.group(1).strip()
            if m_bonds:
                bonds_val = m_bonds.group(1).strip()
        else:
            att_val = raw_update.strip()

        for b in blocks:
            heading_name = b[0].replace("###", "").strip()
            h_low = heading_name.lower()
            if t_low == h_low or t_low in h_low or h_low in t_low:
                if att_val:
                    if re.search(r"\*\s*\*\*Atitude Atual:\*\*\s*[^\n]+", b[1]):
                        b[1] = re.sub(
                            r"(\*\s*\*\*Atitude Atual:\*\*\s*)[^\n]+",
                            rf"\g<1>{att_val}.",
                            b[1],
                            count=1,
                        )
                    else:
                        b[1] = f"\n* **Atitude Atual:** {att_val}." + b[1]
                    applied.append(f"NPC {heading_name} (Atitude) -> {att_val}")

                if rel_val:
                    if re.search(r"\*\s*\*\*Relação com Protagonista:\*\*\s*[^\n]+", b[1], re.IGNORECASE):
                        b[1] = re.sub(
                            r"(\*\s*\*\*Relação com Protagonista:\*\*\s*)[^\n]+",
                            rf"\g<1>{rel_val}.",
                            b[1],
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:
                        b[1] = b[1].rstrip() + f"\n* **Relação com Protagonista:** {rel_val}.\n\n"
                    applied.append(f"NPC {heading_name} (Relação com Protagonista) -> {rel_val}")

                if bonds_val:
                    if re.search(r"\*\s*\*\*Vínculos & Matriz Relacional:\*\*\s*[^\n]+", b[1], re.IGNORECASE):
                        b[1] = re.sub(
                            r"(\*\s*\*\*Vínculos & Matriz Relacional:\*\*\s*)[^\n]+",
                            rf"\g<1>{bonds_val}.",
                            b[1],
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:
                        b[1] = b[1].rstrip() + f"\n* **Vínculos & Matriz Relacional:** {bonds_val}.\n\n"
                    applied.append(f"NPC {heading_name} (Vínculos) -> {bonds_val}")

                matched = True
                break

        if not matched:
            new_heading = f"### {target_name}"
            new_body = (
                f"\n* **Grau / Classificação:** Personagem em Cena\n"
                f"* **Papel:** Introduzido durante a crônica.\n"
                f"* **Atitude Atual:** {att_val or raw_update}.\n"
            )
            if rel_val:
                new_body += f"* **Relação com Protagonista:** {rel_val}.\n"
            if bonds_val:
                new_body += f"* **Vínculos & Matriz Relacional:** {bonds_val}.\n"
            new_body += "\n"
            blocks.append([new_heading, new_body])
            applied.append(f"NPC Novo Cadastrado ({target_name}) -> {att_val or raw_update}")

    new_text = header + "".join(b[0] + b[1] for b in blocks)
    atomic_write_text(npcs_path, new_text)
    return applied


__all__ = ["apply_npc_updates_to_md", "upsert_npc_to_md"]
