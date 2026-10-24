"""application/projectors/npc.py: Projector determinístico para npcs.md."""

from __future__ import annotations

import re

from contracts.ports import EventStreamView, ProjectionSection

_DEFAULT_NPCS = """# Personagens Não-Jogáveis (NPCs)

## 1. Elenco Ativo
"""


class NpcProjector:
    """Projeta estado de NPCs em npcs.md."""

    file = "npcs.md"
    section = "body"
    order = 30

    def __init__(self, initial_text: str | None = None) -> None:
        self.initial_text = initial_text

    def project(self, view: EventStreamView) -> ProjectionSection:
        text = self.initial_text if self.initial_text is not None else _DEFAULT_NPCS

        for ev in view.events:
            meta = ev.meta or {}
            p = ev.payload
            t = ev.type

            if t == "projection.rebuilt":
                continue

            if t == "campaign.created":
                baseline = meta.get("baseline", {})
                if isinstance(baseline, dict) and "npcs.md" in baseline:
                    text = str(baseline["npcs.md"])
                continue

            if "npcs_after" in meta and meta["npcs_after"]:
                text = str(meta["npcs_after"])
                continue

            if t == "npc.updated":
                npc_id = str(p.get("npc_id", ""))
                changes = dict(p.get("changes") or {})
                name = str(changes.get("name", npc_id))
                status = str(changes.get("status", "Ativo"))
                pat = re.compile(rf"###\s*{re.escape(name)}\b.*?(?=\n###|\n##|\Z)", re.IGNORECASE | re.DOTALL)
                lines = [f"### {name}", f"* **ID:** {npc_id}", f"* **Status:** {status}"]
                for k, v in sorted(changes.items()):
                    if k not in ("name", "status"):
                        lines.append(f"* **{k}:** {v}")
                block = "\n".join(lines) + "\n"
                if pat.search(text):
                    text = pat.sub(block, text, count=1)
                else:
                    text = text.rstrip() + "\n\n" + block

        return ProjectionSection(
            file=self.file,
            section=self.section,
            content=text.rstrip() + "\n",
        )


__all__ = ["NpcProjector"]
