"""application/projectors/world_journal.py: projeção textual da simulação em diario.md.

Funções puras de texto: recebem o conteúdo atual do diário e devolvem o conteúdo
com a seção ``### Simulação de Mundo`` e a data canônica atualizadas.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

WORLD_SECTION = "### Simulação de Mundo"


def ensure_world_section(text: str) -> str:
    if WORLD_SECTION in text:
        return text
    if "### Histórico de Turnos" in text:
        return text.replace(
            "### Histórico de Turnos",
            f"{WORLD_SECTION}\n\n### Histórico de Turnos",
            1,
        )
    return text.rstrip() + f"\n\n{WORLD_SECTION}\n"


def append_world_entry(text: str, entry: str) -> str:
    text = ensure_world_section(text)
    start = text.find(WORLD_SECTION) + len(WORLD_SECTION)
    following = re.search(r"\n###\s", text[start:])
    if following:
        position = start + following.start()
        body = text[start:position].rstrip()
        return text[:start] + body + "\n" + entry + text[position:]
    return text.rstrip() + "\n" + entry + "\n"


def apply_world_tick(text: str, event: Any, payload: Mapping[str, Any]) -> str:
    """Atualiza a data canônica e registra o ciclo no diário, preservando o local."""
    current_location = re.search(r"\*\s*\*\*Data\s*&\s*Local:\*\*\s*([^\n]+)", text)
    location_name = "Local Ativo"
    if current_location:
        raw = current_location.group(1).strip().rstrip(".")
        for separator in ("—", " - "):
            if separator in raw:
                location_name = raw.split(separator, 1)[1].strip().rstrip(".")
                break

    text = re.sub(
        r"(\*\s*\*\*Data\s*&\s*Local:\*\*\s*)[^\n]+",
        rf"\g<1>{event.game_time} — {location_name}.",
        text,
        count=1,
    )
    entry = (
        f"* **Tick {payload.get('tick_id', '')}:** +{int(payload.get('elapsed_minutes', 0))} min "
        f"({payload.get('from_game_time', '')} → {payload.get('to_game_time', '')}) | "
        f"{int(payload.get('selected', 0))} executados, {int(payload.get('deferred', 0))} adiados."
    )
    return append_world_entry(text, entry)


def apply_world_work(text: str, payload: Mapping[str, Any], failed: bool) -> str:
    """Registra um trabalho resolvido ou uma falha na seção de simulação."""
    kind = str(payload.get("kind", ""))
    entity_id = str(payload.get("entity_id", ""))
    if failed:
        entry = (
            f"* **Falha ({kind})** {entity_id}: {payload.get('error', '')} "
            f"(tentativa {int(payload.get('attempts', 1))})."
        )
    else:
        outcome = payload.get("outcome") or {}
        summary = str(outcome.get("summary") or kind)
        entry = f"* **{kind}** {entity_id}: {summary}"
    return append_world_entry(text, entry)


__all__ = [
    "WORLD_SECTION",
    "append_world_entry",
    "apply_world_tick",
    "apply_world_work",
    "ensure_world_section",
]
