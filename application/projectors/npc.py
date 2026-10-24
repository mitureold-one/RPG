"""application/projectors/npc.py: Projector determinístico para npcs.md."""

from __future__ import annotations

from contracts.ports import EventStreamView, ProjectionSection


class NpcProjector:
    """Projeta estado de NPCs em npcs.md."""

    file = "npcs.md"
    section = "body"
    order = 30

    def project(self, view: EventStreamView) -> ProjectionSection:
        npcs: dict[str, dict[str, str]] = {}

        for ev in view.events:
            if ev.type == "npc.updated":
                npc_id = ev.payload.get("npc_id", "")
                changes = ev.payload.get("changes", {})
                if npc_id not in npcs:
                    npcs[npc_id] = {}
                for k, v in changes.items():
                    npcs[npc_id][str(k)] = str(v)

        lines: list[str] = [
            "# Personagens Não-Jogáveis (NPCs)",
            "",
            "## 1. Elenco Ativo",
            "",
        ]
        if npcs:
            for nid, data in sorted(npcs.items()):
                name = data.get("name", nid)
                status = data.get("status", "Ativo")
                lines.append(f"### {name}")
                lines.append(f"* **ID:** {nid}")
                lines.append(f"* **Status:** {status}")
                for k, v in sorted(data.items()):
                    if k not in ("name", "status"):
                        lines.append(f"* **{k}:** {v}")
                lines.append("")
        else:
            lines.append("*Nenhum NPC registrado até o momento.*")
            lines.append("")

        return ProjectionSection(
            file=self.file,
            section=self.section,
            content="\n".join(lines).strip() + "\n",
        )


__all__ = ["NpcProjector"]
