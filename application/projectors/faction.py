"""application/projectors/faction.py: Projector determinístico para facções em mundo.md."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from contracts.ports import EventStreamView, ProjectionSection
from resources.factions.parser import (
    FACTION_SECTION_HEADER,
    parse_factions_from_mundo,
    upsert_faction_in_mundo,
)

_DEFAULT_FACCOES = """# Registro Político de Facções & Subgrupos

## 1. Facções e Lideranças
"""


class FactionProjector:
    """Projeta a estrutura política, liderança e subgrupos de facções em faccoes.md."""

    file = "faccoes.md"
    section = "body"
    order = 40

    def __init__(self, initial_text: str | None = None) -> None:
        self.initial_text = initial_text

    def project(self, view: EventStreamView) -> ProjectionSection:
        init_txt = self.initial_text if self.initial_text is not None else _DEFAULT_FACCOES
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir) / "faccoes.md"
            tmp.write_text(init_txt, encoding="utf-8")

            for ev in view.events:
                self._apply_event(tmp, ev)

            final_text = tmp.read_text(encoding="utf-8")

        return ProjectionSection(
            file=self.file,
            section=self.section,
            content=final_text.rstrip() + "\n",
        )

    @staticmethod
    def _apply_event(tmp: Path, ev: Any) -> None:
        meta = ev.meta or {}
        p = ev.payload or {}
        t = ev.type

        if t == "projection.rebuilt":
            return

        if t == "campaign.created":
            baseline = meta.get("baseline", {})
            if isinstance(baseline, dict) and "mundo.md" in baseline:
                tmp.write_text(str(baseline["mundo.md"]), encoding="utf-8")
            return

        if t == "command.executed":
            if str(p.get("command", "")) == "sync" and isinstance(p.get("files"), dict) and "mundo.md" in p["files"]:
                tmp.write_text(str(p["files"]["mundo.md"]), encoding="utf-8")
            return

        if t in ("faction.updated", "faction.leadership_changed"):
            tag = (p.get("tag") or p.get("faction_tag") or "").upper()
            ld = p.get("leadership") or {}
            leader = str(ld.get("leader_id") or p.get("leader_id", ""))
            title = str(ld.get("title") or p.get("title", "Líder"))
            if tag and tmp.exists() and leader:
                text = tmp.read_text(encoding="utf-8")
                # Se a facção já existe na seção, anota a liderança
                m_fac = re.search(rf"(\*\s*\*\*\[{re.escape(tag)}\][^*]+\*\*:[^\n]+)", text)
                if m_fac:
                    line = m_fac.group(1)
                    if "Liderança:" not in line:
                        new_line = f"{line} | Liderança: {title} {leader}".strip()
                        text = text.replace(line, new_line, 1)
                        tmp.write_text(text, encoding="utf-8")
                else:
                    upsert_faction_in_mundo(
                        tmp,
                        name=str(p.get("name") or tag),
                        tag=tag,
                        desc=f"Força ativa sob liderança de {title} {leader}.",
                    )
            return

        if t in ("faction.subgroup_updated", "faction.subgroup_created"):
            tag = (p.get("faction_tag") or p.get("tag") or "").upper()
            sub_name = str(p.get("name") or p.get("subgroup_id", ""))
            if tag and tmp.exists():
                text = tmp.read_text(encoding="utf-8")
                m_fac = re.search(rf"(\*\s*\*\*\[{re.escape(tag)}\][^*]+\*\*:[^\n]+)", text)
                if m_fac:
                    line = m_fac.group(1)
                    if sub_name not in line:
                        new_line = f"{line} | Ala: {sub_name}".strip()
                        text = text.replace(line, new_line, 1)
                        tmp.write_text(text, encoding="utf-8")
            return

        if t == "faction.plan_updated":
            tag = (p.get("faction_tag") or p.get("tag") or "").upper()
            plan_id = str(p.get("plan_id", ""))
            if tag and tmp.exists():
                text = tmp.read_text(encoding="utf-8")
                m_fac = re.search(rf"(\*\s*\*\*\[{re.escape(tag)}\][^*]+\*\*:[^\n]+)", text)
                if m_fac:
                    line = m_fac.group(1)
                    if "Plano:" not in line:
                        new_line = f"{line} | Plano Ativo: {plan_id}".strip()
                        text = text.replace(line, new_line, 1)
                        tmp.write_text(text, encoding="utf-8")
            return


__all__ = ["FactionProjector"]
