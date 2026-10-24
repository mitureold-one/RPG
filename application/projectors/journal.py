"""application/projectors/journal.py: Projector determinístico para diario.md."""

from __future__ import annotations

import re
from typing import Any

from contracts.ports import EventStreamView, ProjectionSection

_DEFAULT_DIARIO = """<!-- schema_version: 1 -->
# Diário — Campanha

### Arco Narrativo Ativo
* **Título:** Arco Principal da Campanha
* **Pergunta Central:** Como os protagonistas superarão o conflito e a resistência iminente?
* **Fase:** Confrontação

## Cena 1: Abertura
* **Data & Local:** Dia 1, 08:00 — Local Ativo.
* **Presentes:** Protagonista.

### Relógios de Ameaça & Prazos

### Planejamento de Trama & Fila de Cenas

### Quests & Objetivos

### Registro de Experiência (XP Ledger)

### Marcos da Crônica

### Histórico de Turnos
"""


class JournalProjector:
    """Projeta eventos de turno, relógio, quests, progressão e correções em diario.md."""

    file = "diario.md"
    section = "log"
    order = 10

    def __init__(self, initial_text: str | None = None) -> None:
        self.initial_text = initial_text

    def project(self, view: EventStreamView) -> ProjectionSection:
        text = self.initial_text if self.initial_text is not None else _DEFAULT_DIARIO

        for ev in view.events:
            meta = ev.meta or {}
            p = ev.payload
            t = ev.type

            if t == "projection.rebuilt":
                continue

            if t == "campaign.created":
                baseline = meta.get("baseline", {})
                if isinstance(baseline, dict) and "diario.md" in baseline:
                    text = str(baseline["diario.md"])
                    continue
                title = str(p.get("title", "Campanha"))
                start_gt = str(p.get("start_game_time", ev.game_time))
                text = re.sub(r"(?m)^#\s*Diário[^\n]*", f"# Diário — {title}", text, count=1)
                text = re.sub(
                    r"(\*\s*\*\*Data\s*&\s*Local:\*\*\s*)[^\n]+",
                    rf"\g<1>{start_gt} — Local Ativo.",
                    text,
                    count=1,
                )
                continue

            if "diario_after" in meta and meta["diario_after"]:
                text = str(meta["diario_after"])
                continue

            if t in ("clock.created", "clock.advanced", "clock.resolved"):
                name = str(p.get("name", ""))
                cur = int(p.get("current", 0 if t == "clock.created" else p.get("max", 4)))
                mx = int(p.get("max", max(1, cur)))
                status = str(p.get("status", "RESOLVED" if t == "clock.resolved" else ("BREACHED" if cur >= mx else "ACTIVE"))).upper()
                trigger = str(p.get("trigger", ""))
                text = self._upsert_clock(text, name, cur, mx, trigger, status)
                if t == "clock.resolved" and int(p.get("xp_granted", 0)) != 0:
                    text = self._append_xp(text, int(p["xp_granted"]), f"Relógio '{name}' resolvido", None)
            elif t == "protagonist.progression_changed":
                xp_delta = int(p.get("xp_delta", 0))
                if xp_delta != 0 and not p.get("skip_ledger"):
                    source = str(p.get("source") or "Progressão")
                    turn_num = p.get("turn")
                    text = self._append_xp(text, xp_delta, source, int(turn_num) if turn_num is not None else None)
            elif t == "turn.committed":
                turn_num = int(p.get("turn", 1))
                summary = str(p.get("summary", "")).rstrip(".")
                loc = str(p.get("location", "Local Ativo"))
                pres = p.get("present", [])
                pres_str = ", ".join(str(x) for x in pres) if isinstance(pres, (list, tuple)) else str(pres)
                text = re.sub(
                    r"(\*\s*\*\*Data\s*&\s*Local:\*\*\s*)[^\n]+",
                    rf"\g<1>{ev.game_time} — {loc}.",
                    text,
                    count=1,
                )
                if pres_str:
                    text = re.sub(
                        r"(\*\s*\*\*Presentes:\*\*\s*)[^\n]+",
                        rf"\g<1>{pres_str}.",
                        text,
                        count=1,
                    )
                vitals = p.get("vitals", {})
                v_str = (
                    " Vitais: " + ", ".join(f"{k.upper()} {v}" for k, v in vitals.items()) + "."
                    if isinstance(vitals, dict) and vitals
                    else ""
                )
                entry = f"* **Turno {turn_num}:** {summary}.{v_str}"
                text = self._append_history(text, entry)
            elif t == "correction.issued":
                cor_id = str(p.get("correction_id", ""))
                reason = str(p.get("reason", ""))
                state = str(p.get("state", "concluída"))
                corrects = ", ".join(str(x) for x in p.get("corrects", []))
                entry = f"* **[Correção {cor_id}]** Alvo: `{corrects}` | Estado: `{state}` — Nota: {reason}"
                text = self._append_history(text, entry)
            elif t == "correction.recomputed":
                cor_id = str(p.get("correction_id", ""))
                outcome = str(p.get("outcome", ""))
                if outcome in ("RESOLVED", "COMPENSATED"):
                    text = re.sub(
                        rf"(\*\s*\*\*\[Correção {re.escape(cor_id)}\]\*\*\s*Alvo:\s*`[^`]*`\s*\|\s*Estado:\s*)`[^`]+`",
                        r"\g<1>`concluída`",
                        text,
                    )

        return ProjectionSection(
            file=self.file,
            section=self.section,
            content=text.rstrip() + "\n",
        )

    @staticmethod
    def _upsert_clock(text: str, name: str, cur: int, mx: int, trigger: str, status: str) -> str:
        header = "### Relógios de Ameaça & Prazos"
        if header not in text:
            text = f"{header}\n\n" + text
        trig_part = f" (Gatilho: {trigger})" if trigger else ""
        line = f"* **[{name}]:** {cur}/{mx}{trig_part} [{status}]"
        pat = re.compile(rf"\*\s*\*\*\[{re.escape(name)}\]:\*\*\s*\d+\s*/\s*\d+[^\n]*", re.IGNORECASE)
        if pat.search(text):
            return pat.sub(line, text, count=1)
        idx = text.find(header) + len(header)
        return text[:idx] + f"\n{line}" + text[idx:]

    @staticmethod
    def _append_xp(text: str, amount: int, reason: str, turn: int | None) -> str:
        header = "### Registro de Experiência (XP Ledger)"
        turn_str = f" | Turno {turn}" if turn is not None else ""
        reason_str = f" ({reason.strip()})" if reason.strip() else ""
        sign = "+" if amount >= 0 else ""
        entry_line = f"* **[XP] {sign}{amount} XP**{reason_str}{turn_str}"

        m_sec = re.search(r"(###\s*Registro de Experiência[^\n]*\n)", text, re.IGNORECASE)
        if m_sec:
            start_pos = m_sec.end()
            m_next = re.search(r"\n(?=###|\n##|\Z)", text[start_pos:])
            if m_next:
                ins_pos = start_pos + m_next.start()
                return text[:ins_pos].rstrip() + "\n" + entry_line + "\n\n" + text[ins_pos:].lstrip()
            return text.rstrip() + "\n" + entry_line + "\n"
        m_hist = re.search(r"(###\s*Histórico de Turnos)", text, re.IGNORECASE)
        if m_hist:
            ins_pos = m_hist.start()
            return text[:ins_pos] + f"{header}\n{entry_line}\n\n" + text[ins_pos:]
        return text.rstrip() + f"\n\n{header}\n{entry_line}\n"

    @staticmethod
    def _append_history(text: str, entry: str) -> str:
        header = "### Histórico de Turnos"
        if header not in text:
            return text.rstrip() + f"\n\n{header}\n{entry}\n"
        return text.rstrip() + f"\n{entry}\n"


__all__ = ["JournalProjector"]
