"""resources/clocks.py: Domínio e manipulação de relógios narrativos em diario.md."""

from __future__ import annotations

import re
from pathlib import Path

from adapters.persistence.files import atomic_write_text


def render_progress_bar(current: int, max_steps: int, length: int = 4) -> str:
    """Gera uma barra de progresso em texto simples (ex: [██░░])."""
    if max_steps <= 0:
        return "[]"
    filled = min(max_steps, max(0, current))
    ratio = filled / max_steps
    bar_filled = round(ratio * length)
    return "[" + ("█" * bar_filled) + ("░" * (length - bar_filled)) + "]"


def parse_clocks_from_diario(diario_path: Path) -> list[dict]:
    """Extrai os Relógios Narrativos de Ameaça e Facções cadastrados em diario.md."""
    if not diario_path.exists():
        return []
    text = diario_path.read_text(encoding="utf-8")
    clocks: list[dict] = []
    pattern = (
        r"\*\s*\*\*\[([^\]]+)\]:\*\*\s*(\d+)\s*/\s*(\d+)"
        r"(?:\s*\((?:Gatilho:\s*)?([^)]*)\))?(?:\s*\[(ACTIVE|BREACHED|RESOLVED)\])?"
    )
    for m in re.finditer(pattern, text, re.IGNORECASE):
        name = m.group(1).strip()
        cur = int(m.group(2))
        max_s = int(m.group(3))
        trigger = (m.group(4) or "").strip()
        raw_status = (m.group(5) or "").upper()
        if cur >= max_s and raw_status != "RESOLVED":
            status = "BREACHED"
        elif raw_status in ("ACTIVE", "BREACHED", "RESOLVED"):
            status = raw_status
        else:
            status = "ACTIVE"
        clocks.append(
            {
                "name": name,
                "current": cur,
                "max": max_s,
                "progress": f"{cur}/{max_s}",
                "trigger": trigger,
                "status": status,
                "bar": render_progress_bar(cur, max_s),
            }
        )
    return clocks


def upsert_clock_in_diario(
    diario_path: Path,
    name: str,
    current: int = None,
    max_steps: int = None,
    trigger: str = "",
    status: str = "",
    advance: int = 0,
    create_if_missing: bool = True,
) -> dict:
    """Insere, atualiza ou avança um Relógio Narrativo em diario.md atomicamente."""
    if not diario_path.exists():
        return {"error": "diario.md não encontrado"}
    text = diario_path.read_text(encoding="utf-8")

    section_header = "### Relógios de Ameaça & Prazos"
    if "Relógios de Ameaça & Prazos" not in text:
        m_scene = re.search(r"(##\s*Cena\s+[^\n]+)", text)
        if m_scene:
            ins_pos = m_scene.end()
            text = text[:ins_pos] + f"\n\n{section_header}\n" + text[ins_pos:]
        else:
            text = f"{section_header}\n\n" + text

    clock_pat = (
        rf"(\*\s*\*\*\[{re.escape(name)}\]:\*\*\s*)(\d+)\s*/\s*(\d+)"
        r"(?:\s*\((?:Gatilho:\s*)?([^)]*)\))?(?:\s*\[(ACTIVE|BREACHED|RESOLVED)\])?"
    )
    m = re.search(clock_pat, text, re.IGNORECASE)

    if m:
        cur_val = int(m.group(2))
        max_val = int(m.group(3))
        existing_trigger = (m.group(4) or "").strip()
        existing_status = (m.group(5) or "").upper() or "ACTIVE"

        new_max = max_steps if max_steps is not None else max_val
        if current is not None:
            new_cur = current
        elif advance:
            new_cur = cur_val + advance
        else:
            new_cur = cur_val

        new_cur = max(0, new_cur)
        new_trigger = trigger.strip() if trigger else existing_trigger

        if status:
            new_status = status.upper()
        elif new_cur >= new_max and existing_status != "RESOLVED":
            new_status = "BREACHED"
        else:
            new_status = "ACTIVE" if existing_status != "RESOLVED" else "RESOLVED"

        trigger_part = f" (Gatilho: {new_trigger})" if new_trigger else ""
        new_line = f"* **[{name}]:** {new_cur}/{new_max}{trigger_part} [{new_status}]"
        text = text[: m.start()] + new_line + text[m.end() :]
        atomic_write_text(diario_path, text)
        return {
            "name": name,
            "current": new_cur,
            "max": new_max,
            "trigger": new_trigger,
            "status": new_status,
            "bar": render_progress_bar(new_cur, new_max),
            "action": "updated",
        }
    else:
        if not create_if_missing:
            return {
                "error": (
                    f"Relógio '{name}' não encontrado em diario.md. "
                    f"Crie-o explicitamente com 'lazy_turn.py clock --add \"{name}\"'."
                )
            }
        new_max = max_steps if max_steps is not None else 4
        new_cur = current if current is not None else 0
        if advance:
            new_cur += advance
        new_cur = max(0, new_cur)
        new_trigger = trigger.strip()
        new_status = status.upper() if status else ("BREACHED" if new_cur >= new_max else "ACTIVE")

        trigger_part = f" (Gatilho: {new_trigger})" if new_trigger else ""
        new_line = f"* **[{name}]:** {new_cur}/{new_max}{trigger_part} [{new_status}]\n"

        sec_idx = text.find(section_header)
        after_header = sec_idx + len(section_header)
        text = text[:after_header] + "\n" + new_line + text[after_header:]
        atomic_write_text(diario_path, text)
        return {
            "name": name,
            "current": new_cur,
            "max": new_max,
            "trigger": new_trigger,
            "status": new_status,
            "bar": render_progress_bar(new_cur, new_max),
            "action": "created",
        }


__all__ = [
    "parse_clocks_from_diario",
    "render_progress_bar",
    "upsert_clock_in_diario",
]
