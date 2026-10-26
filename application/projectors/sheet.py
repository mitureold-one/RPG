"""application/projectors/sheet.py: Projector determinístico para ficha.md."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from contracts.ports import EventStreamView, ProjectionSection
from council.factions import update_reputation_in_ficha
from resources.progression import (
    parse_progression_from_ficha,
    spend_ability_point_in_ficha,
    spend_attribute_point_in_ficha,
    update_progression_in_ficha,
)
from resources.sheet import parse_ficha_md, upsert_ficha_feature
from rulesets.progression import DEFAULT_BASE_STEP

_DEFAULT_FICHA = """# Ficha do Protagonista

### Identidade
* **Nome:** Protagonista
* **Arquétipo:** Aventureiro

### Progressão
* **Nível:** 1
* **Experiência (XP):** 0
* **Próximo Nível:** 250
* **Pontos de Atributo:** 0
* **Pontos de Habilidade:** 0

### Atributos
* **Força:** 10
* **Agilidade:** 10
* **Intelecto:** 10
* **Vontade:** 10

### Vitais
* **HP (Vida):** 20 / 20
* **Stamina (Fôlego):** 15 / 15
* **Energia (CE):** 10 / 10

### Condições Ativas
* *(Nenhuma)*

### Equipamento & Inventário
* *(Vazio)*

### Reputação de Facções
"""


class CharacterSheetProjector:
    """Projeta progressão, vitais, reputação e atributos em ficha.md."""

    file = "ficha.md"
    section = "body"
    order = 20

    def __init__(self, initial_text: str | None = None) -> None:
        self.initial_text = initial_text

    def project(self, view: EventStreamView) -> ProjectionSection:
        init_txt = self.initial_text if self.initial_text is not None else _DEFAULT_FICHA
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir) / "ficha.md"
            tmp.write_text(init_txt, encoding="utf-8")

            for ev in view.events:
                self._apply_event(tmp, ev)

            final_text = tmp.read_text(encoding="utf-8")

        return ProjectionSection(
            file=self.file,
            section=self.section,
            content=final_text.rstrip() + "\n",
        )

    def _apply_event(self, tmp: Path, ev: Any) -> None:
        meta = ev.meta or {}
        p = ev.payload
        t = ev.type

        if t == "projection.rebuilt":
            return

        if t == "campaign.created":
            baseline = meta.get("baseline", {})
            if isinstance(baseline, dict) and "ficha.md" in baseline:
                tmp.write_text(str(baseline["ficha.md"]), encoding="utf-8")
            return

        if t == "command.executed":
            if str(p.get("command", "")) == "sync" and isinstance(p.get("files"), dict) and "ficha.md" in p["files"]:
                tmp.write_text(str(p["files"]["ficha.md"]), encoding="utf-8")
            return

        if t == "protagonist.progression_changed":
            xp_delta = int(p.get("xp_delta", 0))
            if xp_delta == 0 and "xp_total" in p:
                cur_p = parse_progression_from_ficha(tmp)
                xp_delta = int(p["xp_total"]) - cur_p["xp"]
            base_step = int(p.get("base_step", DEFAULT_BASE_STEP))
            update_progression_in_ficha(tmp, xp_add=xp_delta, base_step=base_step)
        elif t == "faction.reputation_changed":
            fac = str(p.get("faction", ""))
            res = update_reputation_in_ficha(
                tmp,
                fac,
                score_delta=int(p.get("delta_rep", 0)),
                favors_delta=int(p.get("delta_favors", 0)),
                debts_delta=int(p.get("delta_debts", 0)),
                set_score=int(p["new_score"]) if "new_score" in p else None,
                set_favors=int(p["favors"]) if "favors" in p else None,
                set_debts=int(p["debts"]) if "debts" in p else None,
            )
            if res.get("error"):
                score = int(p.get("new_score", 0))
                favors = int(p.get("favors", p.get("delta_favors", 0)))
                debts = int(p.get("debts", p.get("delta_debts", 0)))
                tmp.write_text(self._upsert_faction(tmp.read_text(encoding="utf-8"), fac, score, favors, debts), encoding="utf-8")
        elif t == "turn.committed":
            if p.get("restored_vitals"):
                ficha_data = parse_ficha_md(tmp)
                ficha_text = tmp.read_text(encoding="utf-8")
                for v in ficha_data.get("vitals", {}).values():
                    if v["max"] > 0 and v["current"] < v["max"]:
                        pattern = rf"(\*\s*\*\*{re.escape(v['label'])}:\*\*\s*)\d+(\s*/\s*{v['max']})"
                        ficha_text = re.sub(pattern, rf"\g<1>{v['max']}\g<2>", ficha_text)
                tmp.write_text(ficha_text, encoding="utf-8")
            elif isinstance(p.get("vitals"), dict) and not p.get("costs"):
                ficha_text = tmp.read_text(encoding="utf-8")
                for k, val in p["vitals"].items():
                    ficha_text = self._update_vital(ficha_text, str(k), int(val))
                tmp.write_text(ficha_text, encoding="utf-8")
        elif t == "protagonist.sheet_changed":
            kind = str(p.get("kind", ""))
            target = str(p.get("target", ""))
            val = p.get("new_value")
            pts_rem = p.get("points_remaining")
            if kind == "attribute":
                res = spend_attribute_point_in_ficha(tmp, target)
                if res.get("error"):
                    tmp.write_text(self._apply_sheet_change(tmp.read_text(encoding="utf-8"), kind, target, val, pts_rem), encoding="utf-8")
            elif kind == "ability":
                if p.get("training") or pts_rem is not None:
                    res = spend_ability_point_in_ficha(tmp, target, str(p.get("training") or "Treino"))
                    if res.get("error"):
                        upsert_ficha_feature(tmp, ability=target)
                else:
                    upsert_ficha_feature(tmp, ability=target)
            elif kind == "milestone":
                upsert_ficha_feature(tmp, milestone=target)
            elif kind == "item":
                upsert_ficha_feature(tmp, item=target)
            elif kind == "vital":
                ficha_data = parse_ficha_md(tmp)
                if target in ficha_data.get("vitals", {}):
                    v = ficha_data["vitals"][target]
                    if "delta" in p and p.get("source") == "commit_cost":
                        new_val = max(0, min(v["max"], v["current"] + int(p["delta"])))
                    else:
                        new_val = max(0, min(v["max"], int(val)))
                    pattern = rf"(\*\s*\*\*{re.escape(v['label'])}:\*\*\s*)\d+(\s*/\s*{v['max']})"
                    tmp.write_text(re.sub(pattern, rf"\g<1>{new_val}\g<2>", tmp.read_text(encoding="utf-8")), encoding="utf-8")
                else:
                    tmp.write_text(self._update_vital(tmp.read_text(encoding="utf-8"), target, int(val)), encoding="utf-8")
            else:
                tmp.write_text(self._apply_sheet_change(tmp.read_text(encoding="utf-8"), kind, target, val, pts_rem), encoding="utf-8")

    @staticmethod
    def _update_vital(text: str, key: str, val: int) -> str:
        pat = re.compile(rf"(\*\s*\*\*[^:*]*{re.escape(key)}[^:*]*:\*\*\s*)\d+(\s*/\s*\d+)", re.IGNORECASE)
        if pat.search(text):
            return pat.sub(rf"\g<1>{val}\g<2>", text, count=1)
        return text

    @staticmethod
    def _upsert_faction(text: str, fac: str, score: int, favors: int, debts: int) -> str:
        header = "### Reputação de Facções"
        if header not in text:
            text = text.rstrip() + f"\n\n{header}\n"
        line = f"* **{fac}:** {score:+d} [Neutro] | Favores: {favors} | Débitos: {debts}"
        pat = re.compile(rf"\*\s*\*\*{re.escape(fac)}:\*\*\s*[+-]?\d+[^\n]*", re.IGNORECASE)
        if pat.search(text):
            return pat.sub(line, text, count=1)
        idx = text.find(header) + len(header)
        return text[:idx] + f"\n{line}" + text[idx:]

    @staticmethod
    def _apply_sheet_change(text: str, kind: str, target: str, val: Any, pts_rem: int | None) -> str:
        pat = re.compile(rf"(\*\s*\*\*{re.escape(target)}:\*\*\s*)[^\n]+", re.IGNORECASE)
        if pat.search(text):
            text = pat.sub(rf"\g<1>{val}", text, count=1)
        else:
            text = text.rstrip() + f"\n* **{target}:** {val}\n"
        if pts_rem is not None:
            if kind == "attribute":
                text = re.sub(r"(\*\s*\*\*Pontos de Atributo:\*\*\s*)\d+", rf"\g<1>{pts_rem}", text)
            elif kind == "ability":
                text = re.sub(r"(\*\s*\*\*Pontos de Habilidade:\*\*\s*)\d+", rf"\g<1>{pts_rem}", text)
        return text


__all__ = ["CharacterSheetProjector"]
