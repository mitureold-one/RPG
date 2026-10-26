"""application/projectors/npc.py: Projector determinístico para npcs.md."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from contracts.ports import EventStreamView, ProjectionSection
from council.narrator import apply_npc_updates_to_md, upsert_npc_to_md

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
        init_txt = self.initial_text if self.initial_text is not None else _DEFAULT_NPCS
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir) / "npcs.md"
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
        p = ev.payload
        t = ev.type

        if t == "projection.rebuilt":
            return

        if t == "campaign.created":
            baseline = meta.get("baseline", {})
            if isinstance(baseline, dict) and "npcs.md" in baseline:
                tmp.write_text(str(baseline["npcs.md"]), encoding="utf-8")
            return

        if t == "command.executed":
            if str(p.get("command", "")) == "sync" and isinstance(p.get("files"), dict) and "npcs.md" in p["files"]:
                tmp.write_text(str(p["files"]["npcs.md"]), encoding="utf-8")
            return

        if t == "npc.updated":
            npc_id = str(p.get("npc_id", ""))
            changes = dict(p.get("changes") or {})
            name = str(changes.get("name", npc_id))
            mode = str(changes.get("mode", ""))

            if mode == "turn_update" and "raw_update" in changes:
                apply_npc_updates_to_md(tmp, f"{name}: {changes['raw_update']}")
            elif mode == "upsert":
                upsert_npc_to_md(
                    tmp,
                    name=name,
                    classification=str(changes.get("classification", "")),
                    role=str(changes.get("role", "")),
                    faction=str(changes.get("faction", "")),
                    attitude=str(changes.get("attitude", "")),
                    psychology=str(changes.get("psychology", "")),
                    will=str(changes.get("will", "")),
                    weakness=str(changes.get("weakness", "")),
                    dynamics=str(changes.get("dynamics", "")),
                    appearance=str(changes.get("appearance", "")),
                    bonds=str(changes.get("bonds", "")),
                    relation=str(changes.get("relation", "")),
                )
            else:
                text = tmp.read_text(encoding="utf-8")
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
                tmp.write_text(text, encoding="utf-8")
            return

        if t == "npc.promoted":
            name = str(p.get("name") or p.get("npc_id", ""))
            to_tier = str(p.get("to_tier", "major")).capitalize()
            if name:
                apply_npc_updates_to_md(tmp, f"{name}: Tier: {to_tier} (Agente Autônomo)")
            return

        if t in ("npc.goal_updated", "npc.goal_set"):
            name = str(p.get("npc_id", ""))
            desc = str(p.get("description", ""))
            if name and desc:
                apply_npc_updates_to_md(tmp, f"{name}: Objetivo: {desc}")
            return

        if t == "npc.plan_updated":
            name = str(p.get("npc_id", ""))
            plan_id = str(p.get("plan_id", ""))
            steps = p.get("steps", [])
            summary = f"Plano {plan_id} ({len(steps)} passos)"
            if name:
                apply_npc_updates_to_md(tmp, f"{name}: Plano: {summary}")
            return

        if t in ("npc.relationship_updated", "npc.relationship_mutated"):
            name = str(p.get("npc_id", ""))
            target = str(p.get("target_id", ""))
            trust = p.get("trust", 0)
            rivalry = p.get("rivalry", 0)
            if name and target:
                apply_npc_updates_to_md(tmp, f"{name}: Relação [{target}]: Confiança {trust:+d}, Rivalidade {rivalry}")
            return


__all__ = ["NpcProjector"]
