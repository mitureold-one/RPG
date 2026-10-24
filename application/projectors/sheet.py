"""application/projectors/sheet.py: Projector determinístico para ficha.md."""

from __future__ import annotations

import re
from typing import Any

from contracts.ports import EventStreamView, ProjectionSection
from rulesets.progression import (
    DEFAULT_BASE_STEP,
    calculate_level_from_xp,
    calculate_level_up_bonuses,
)

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
        text = self.initial_text if self.initial_text is not None else _DEFAULT_FICHA

        for ev in view.events:
            meta = ev.meta or {}
            p = ev.payload
            t = ev.type

            if t == "projection.rebuilt":
                continue

            if t == "campaign.created":
                baseline = meta.get("baseline", {})
                if isinstance(baseline, dict) and "ficha.md" in baseline:
                    text = str(baseline["ficha.md"])
                continue

            if "ficha_after" in meta and meta["ficha_after"]:
                text = str(meta["ficha_after"])
                continue

            if t == "protagonist.progression_changed":
                xp_delta = int(p.get("xp_delta", 0))
                xp_total = int(p.get("xp_total", 0))
                text = self._apply_progression(text, xp_delta=xp_delta, xp_total=xp_total, payload=p)
            elif t == "faction.reputation_changed":
                fac = str(p.get("faction", ""))
                score = int(p.get("new_score", 0))
                favors = int(p.get("favors", 0))
                debts = int(p.get("debts", 0))
                text = self._upsert_faction(text, fac, score, favors, debts)
            elif t == "turn.committed":
                v = p.get("vitals", {})
                if isinstance(v, dict):
                    for k, val in v.items():
                        text = self._update_vital(text, str(k), int(val))
            elif t == "protagonist.sheet_changed":
                kind = str(p.get("kind", ""))
                target = str(p.get("target", ""))
                val = p.get("new_value")
                text = self._apply_sheet_change(text, kind, target, val, p.get("points_remaining"))

        return ProjectionSection(
            file=self.file,
            section=self.section,
            content=text.rstrip() + "\n",
        )

    @staticmethod
    def _parse_prog(text: str) -> dict[str, int]:
        prog = {"level": 1, "xp": 0, "next_threshold": 250, "attribute_points": 0, "ability_points": 0}
        m_sec = re.search(r"###\s*Progressão[^\n]*\n(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
        if not m_sec:
            return prog
        sec = m_sec.group(1)
        for key, pat in (
            ("level", r"\*\s*\*\*Nível:\*\*\s*(\d+)"),
            ("xp", r"\*\s*\*\*(?:Experiência\s*\(XP\)|XP):\*\*\s*(\d+)"),
            ("next_threshold", r"\*\s*\*\*Próximo Nível:\*\*\s*(\d+)"),
            ("attribute_points", r"\*\s*\*\*Pontos de Atributo:\*\*\s*(\d+)"),
            ("ability_points", r"\*\s*\*\*Pontos de Habilidade:\*\*\s*(\d+)"),
        ):
            m = re.search(pat, sec, re.IGNORECASE)
            if m:
                prog[key] = int(m.group(1))
        return prog

    @classmethod
    def _apply_progression(
        cls,
        text: str,
        xp_delta: int,
        xp_total: int,
        payload: dict[str, Any],
        base_step: int = DEFAULT_BASE_STEP,
    ) -> str:
        cur = cls._parse_prog(text)
        old_level = cur["level"]
        new_xp = max(0, xp_total if "xp_total" in payload else cur["xp"] + xp_delta)
        new_level, next_thresh = calculate_level_from_xp(new_xp, base_step=base_step)

        if new_level >= old_level:
            bonuses = calculate_level_up_bonuses(old_level, new_level)
            attr_bonus = bonuses["attribute_points"]
            abil_bonus = bonuses["ability_points"]
            hp_add = bonuses["hp_bonus"]
            sta_add = bonuses["stamina_bonus"]
            ce_add = bonuses["energy_bonus"]
        else:
            rev = calculate_level_up_bonuses(new_level, old_level)
            attr_bonus = -rev["attribute_points"]
            abil_bonus = -rev["ability_points"]
            hp_add = -rev["hp_bonus"]
            sta_add = -rev["stamina_bonus"]
            ce_add = -rev["energy_bonus"]

        new_attr = max(0, cur["attribute_points"] + attr_bonus)
        new_abil = max(0, cur["ability_points"] + abil_bonus)

        if new_level != old_level:
            m_v_sec = re.search(r"(###\s*Vitais[^\n]*\n)(.*?)(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
            if m_v_sec:
                header_v = m_v_sec.group(1)
                v_content = m_v_sec.group(2)

                def repl_vital(m_vit):
                    lbl = m_vit.group(1)
                    cur_v = int(m_vit.group(2))
                    mx_v = int(m_vit.group(3))
                    low = lbl.lower()
                    bonus = 0
                    if "hp" in low or "vida" in low or "pv" in low:
                        bonus = hp_add
                    elif "stamina" in low or "fôlego" in low or "folego" in low or "fadiga" in low or "vigor" in low:
                        bonus = sta_add
                    elif "ce" in low or "energia" in low or "mp" in low or "mana" in low:
                        bonus = ce_add
                    return f"* **{lbl}:** {max(1, cur_v + bonus)} / {max(1, mx_v + bonus)}"

                new_v_content = re.sub(r"\*\s*\*\*([^:*]+):\*\*\s*(\d+)\s*/\s*(\d+)", repl_vital, v_content)
                text = text[: m_v_sec.start()] + header_v + new_v_content + text[m_v_sec.end() :]

        prog_block = (
            f"### Progressão\n"
            f"* **Nível:** {new_level}\n"
            f"* **Experiência (XP):** {new_xp}\n"
            f"* **Próximo Nível:** {next_thresh}\n"
            f"* **Pontos de Atributo:** {new_attr}\n"
            f"* **Pontos de Habilidade:** {new_abil}\n"
        )
        m_p_sec = re.search(r"###\s*Progressão[^\n]*\n.*?(?=\n###|\Z)", text, re.IGNORECASE | re.DOTALL)
        if m_p_sec:
            return text[: m_p_sec.start()] + prog_block + text[m_p_sec.end() :]
        return text.rstrip() + f"\n\n{prog_block}\n"

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
