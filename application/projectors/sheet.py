"""application/projectors/sheet.py: Projector determinístico para ficha.md."""

from __future__ import annotations

from contracts.ports import EventStreamView, ProjectionSection


class CharacterSheetProjector:
    """Projeta progressão, vitais e atributos em ficha.md."""

    file = "ficha.md"
    section = "body"
    order = 20

    def project(self, view: EventStreamView) -> ProjectionSection:
        xp_total = 0
        level = 1
        hp = 20
        stamina = 20
        reputations: dict[str, int] = {}
        sheet_custom: dict[str, str] = {}

        for ev in view.events:
            if ev.type == "protagonist.progression_changed":
                xp_total = ev.payload.get("xp_total", xp_total)
                level = ev.payload.get("level", level)
            elif ev.type == "faction.reputation_changed":
                faction = ev.payload.get("faction", "")
                score = ev.payload.get("new_score", 0)
                reputations[faction] = score
            elif ev.type == "turn.committed":
                v = ev.payload.get("vitals", {})
                if "hp" in v:
                    hp = v["hp"]
                if "stamina" in v:
                    stamina = v["stamina"]
            elif ev.type == "protagonist.sheet_changed":
                target = ev.payload.get("target", "")
                val = str(ev.payload.get("new_value", ""))
                sheet_custom[target] = val

        lines: list[str] = [
            "# Ficha do Protagonista",
            "",
            "## 1. Atributos Vitais & Nível",
            f"* **Nível:** {level}",
            f"* **XP Total:** {xp_total}",
            f"* **Pontos de Vida (HP):** {hp}",
            f"* **Estamina:** {stamina}",
            "",
            "## 2. Vínculos e Reputação com Facções",
        ]
        if reputations:
            for fac, score in sorted(reputations.items()):
                lines.append(f"* **{fac}:** {score:+d}")
        else:
            lines.append("*Nenhum alinhamento político registrado.*")
        lines.append("")

        if sheet_custom:
            lines.append("## 3. Características Adicionais")
            for k, val in sorted(sheet_custom.items()):
                lines.append(f"* **{k}:** {val}")
            lines.append("")

        return ProjectionSection(
            file=self.file,
            section=self.section,
            content="\n".join(lines).strip() + "\n",
        )


__all__ = ["CharacterSheetProjector"]
