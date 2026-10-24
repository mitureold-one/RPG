"""application/projectors/journal.py: Projector determinístico para diario.md."""

from __future__ import annotations

from contracts.ports import EventStreamView, ProjectionSection


class JournalProjector:
    """Projeta eventos de turno, relógio e correções em diario.md."""

    file = "diario.md"
    section = "log"
    order = 10

    def project(self, view: EventStreamView) -> ProjectionSection:
        lines: list[str] = [
            "# Diário de Campanha",
            "",
            "## 1. Crônica dos Turnos",
            "",
        ]

        turns_found = 0
        for ev in view.events:
            if ev.type == "turn.committed":
                turns_found += 1
                turn_num = ev.payload.get("turn", 0)
                summary = ev.payload.get("summary", "")
                scene_type = ev.payload.get("scene_type", "Ação")
                location = ev.payload.get("location", "Desconhecido")
                lines.append(f"### Turno {turn_num:03d} — {ev.game_time}")
                lines.append(f"* **Cena:** {scene_type} em {location}")
                lines.append(f"* **Resumo:** {summary}")
                lines.append("")
            elif ev.type == "clock.advanced":
                name = ev.payload.get("name", "")
                cur = ev.payload.get("current", 0)
                mx = ev.payload.get("max", 0)
                status = ev.payload.get("status", "active")
                lines.append(f"* [Relógio] **{name}:** {cur}/{mx} ({status})")
                lines.append("")
            elif ev.type == "correction.issued":
                cor_id = ev.payload.get("correction_id", "")
                reason = ev.payload.get("reason", "")
                lines.append(f"* [Correção {cor_id}] **Nota:** {reason}")
                lines.append("")

        if turns_found == 0:
            lines.append("*Nenhum turno registrado ainda.*")
            lines.append("")

        return ProjectionSection(
            file=self.file,
            section=self.section,
            content="\n".join(lines).strip() + "\n",
        )


__all__ = ["JournalProjector"]
