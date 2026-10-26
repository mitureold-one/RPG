"""application/projectors/journal.py: Projector determinístico para diario.md."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from contracts.ports import EventStreamView, ProjectionSection
from council.factions import append_faction_ledger_entry
from council.quests import append_xp_ledger_entry, upsert_quest_in_diario
from resources.clocks import upsert_clock_in_diario
from resources.ledger import parse_diario_md, update_arc_in_diario, upsert_planned_scene_in_diario

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

_SCENE_TAGS = {
    "interlude": "[INTERLÚDIO] ",
    "parallel": "[CENA PARALELA] ",
    "timeskip": "[SALTO TEMPORAL] ",
    "dossier": "[DOSSIÊ] ",
    "flashback": "[FLASHBACK] ",
    "prologue": "[PRÓLOGO] ",
    "epilogue": "[EPÍLOGO] ",
    "post_credits": "[PÓS-CRÉDITOS] ",
    "fade_to_black": "[FADE TO BLACK] ",
}


class JournalProjector:
    """Projeta eventos de turno, relógio, quests, progressão e correções em diario.md."""

    file = "diario.md"
    section = "log"
    order = 10

    def __init__(self, initial_text: str | None = None) -> None:
        self.initial_text = initial_text

    def project(self, view: EventStreamView) -> ProjectionSection:
        init_txt = self.initial_text if self.initial_text is not None else _DEFAULT_DIARIO
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir) / "diario.md"
            tmp.write_text(init_txt, encoding="utf-8")
            for ev in view.events:
                self._apply_event(tmp, ev)
            final_text = tmp.read_text(encoding="utf-8")
        return ProjectionSection(file=self.file, section=self.section, content=final_text.rstrip() + "\n")

    def _apply_event(self, tmp: Path, ev: Any) -> None:
        meta = ev.meta or {}
        p = ev.payload
        t = ev.type

        if t == "projection.rebuilt":
            return

        if t == "campaign.created":
            baseline = meta.get("baseline", {})
            if isinstance(baseline, dict) and "diario.md" in baseline:
                tmp.write_text(str(baseline["diario.md"]), encoding="utf-8")
                return
            text = tmp.read_text(encoding="utf-8")
            title = str(p.get("title", "Campanha"))
            start_gt = str(p.get("start_game_time", ev.game_time))
            text = re.sub(r"(?m)^#\s*Diário[^\n]*", f"# Diário — {title}", text, count=1)
            text = re.sub(r"(\*\s*\*\*Data\s*&\s*Local:\*\*\s*)[^\n]+", rf"\g<1>{start_gt} — Local Ativo.", text, count=1)
            tmp.write_text(text, encoding="utf-8")
            return

        if t == "command.executed":
            cmd = str(p.get("command", ""))
            if cmd == "sync" and isinstance(p.get("files"), dict) and "diario.md" in p["files"]:
                tmp.write_text(str(p["files"]["diario.md"]), encoding="utf-8")
            elif cmd == "faction.tick" and p.get("clock_updates"):
                self._apply_faction_tick(tmp, p["clock_updates"])
            return

        if t in ("clock.created", "clock.advanced", "clock.resolved"):
            name = str(p.get("name", ""))
            if t == "clock.created":
                upsert_clock_in_diario(
                    tmp, name, current=int(p.get("current", 0)), max_steps=int(p.get("max", 4)),
                    trigger=str(p.get("trigger", "")), status=str(p.get("status", "")), create_if_missing=True,
                )
            elif t == "clock.advanced":
                cur_arg = int(p["current"]) if "current" in p else None
                adv_arg = int(p["delta"]) if ("current" not in p and "delta" in p) else None
                mx_arg = int(p["max"]) if "max" in p else None
                upsert_clock_in_diario(
                    tmp, name, current=cur_arg, advance=adv_arg, max_steps=mx_arg,
                    trigger=str(p.get("trigger", "")), status=str(p.get("status", "")), create_if_missing=True,
                )
            else:
                st = str(p.get("status") or p.get("outcome") or "RESOLVED").upper()
                upsert_clock_in_diario(tmp, name, status=st, create_if_missing=True)
                if int(p.get("xp_granted", 0)) != 0:
                    t_num = int(p["turn"]) if p.get("turn") is not None else None
                    append_xp_ledger_entry(tmp, int(p["xp_granted"]), reason=f"Relógio '{name}' resolvido", turn=t_num)
        elif t == "quest.created":
            objs = p.get("objectives") or [""]
            upsert_quest_in_diario(
                tmp, "add", title=str(p.get("title", "")), quest_type=str(p.get("type", "MAIN")),
                objective=str(objs[0]) if objs else "", contractor=str(p.get("contractor") or ""),
                clock=str(p.get("clock") or ""), reward=str(p.get("reward") or ""),
                phase=str(p.get("phase") or ""), current_turn=p.get("turn"),
            )
        elif t == "quest.objective_completed":
            qid = str(p.get("id") or p.get("quest_id") or "")
            idx = int(p.get("objective_idx") or p.get("objective_index") or 1)
            upsert_quest_in_diario(tmp, "check", quest_id=qid, check_index=idx, current_turn=p.get("turn"))
        elif t == "quest.completed":
            qid = str(p.get("id") or p.get("quest_id") or "")
            xp_aw = p.get("xp_awarded")
            xp_paid_arg = int(xp_aw) if (xp_aw is not None and int(xp_aw) > 0) else None
            upsert_quest_in_diario(
                tmp, "complete", quest_id=qid, evidence=str(p.get("evidence") or ""),
                xp_paid=xp_paid_arg, current_turn=p.get("turn"),
            )
        elif t == "quest.failed":
            qid = str(p.get("id") or p.get("quest_id") or "")
            r = "" if str(p.get("reason") or "") == "Sem justificativa" else str(p.get("reason") or "")
            upsert_quest_in_diario(tmp, "fail", quest_id=qid, reason=r, current_turn=p.get("turn"))
        elif t == "quest.status_changed":
            qid = str(p.get("id") or p.get("quest_id") or "")
            st_map = {"BLOCKED": "block", "ABANDONED": "abandon", "FAILED": "fail", "COMPLETED": "complete", "ACTIVE": "reopen"}
            act = str(p.get("action") or "") or st_map.get(str(p.get("status", "ACTIVE")).upper(), "reopen")
            upsert_quest_in_diario(
                tmp, act, quest_id=qid, objective=str(p.get("objective") or ""),
                reason=str(p.get("reason") or ""), current_turn=p.get("turn"),
            )
        elif t == "scene.planned":
            upsert_planned_scene_in_diario(tmp, scene_type=str(p.get("scene_type", "interlude")), beat=str(p.get("beat", "")), actors=str(p.get("actors", "")))
        elif t == "scene.completed":
            upsert_planned_scene_in_diario(tmp, mark_done_idx=int(p.get("index", 0)))
        elif t == "arc.updated":
            arc_keys = ("title", "question", "stage", "scene_name", "date_time", "location", "present", "resolve_clocks", "milestone")
            if p.get("future_milestone") and not any(p.get(k) for k in arc_keys):
                upsert_planned_scene_in_diario(tmp, future_milestone=str(p["future_milestone"]))
            else:
                update_arc_in_diario(
                    tmp, title=str(p.get("title", "")), central_question=str(p.get("question", "")),
                    stage=str(p.get("stage", "")), scene_name=str(p.get("scene_name", "")),
                    date_time=str(p.get("date_time", "")), location=str(p.get("location", "")),
                    present=str(p.get("present", "")), resolve_clocks=bool(p.get("resolve_clocks", False)),
                    archive_milestone=str(p.get("milestone", "")),
                )
        elif t == "protagonist.progression_changed":
            xp_delta = int(p.get("xp_delta", 0))
            if xp_delta != 0 and not p.get("skip_ledger"):
                t_num = int(p["turn"]) if p.get("turn") is not None else None
                append_xp_ledger_entry(tmp, xp_delta, reason=str(p.get("source") or "Progressão"), turn=t_num)
        elif t == "faction.reputation_changed":
            t_num = int(p["turn"]) if p.get("turn") is not None else None
            append_faction_ledger_entry(
                tmp, faction_name=str(p.get("faction", "")), delta_rep=int(p.get("delta_rep", 0)),
                new_score=int(p.get("new_score", 0)), reason=str(p.get("reason", "")), turn=t_num,
                delta_favors=int(p.get("delta_favors", 0)), delta_debts=int(p.get("delta_debts", 0)),
                quest_id=str(p.get("quest_id", "")),
            )
        elif t == "turn.committed":
            self._apply_turn_committed(tmp, ev, p)
        elif t == "correction.issued":
            cor_id = str(p.get("correction_id", ""))
            reason = str(p.get("reason", ""))
            state = str(p.get("state", "concluída"))
            corrects = ", ".join(str(x) for x in p.get("corrects", []))
            entry = f"* **[Correção {cor_id}]** Alvo: `{corrects}` | Estado: `{state}` — Nota: {reason}"
            tmp.write_text(self._append_history(tmp.read_text(encoding="utf-8"), entry), encoding="utf-8")
        elif t == "correction.recomputed":
            cor_id = str(p.get("correction_id", ""))
            if str(p.get("outcome", "")) in ("RESOLVED", "COMPENSATED"):
                pat = rf"(\*\s*\*\*\[Correção {re.escape(cor_id)}\]\*\*\s*Alvo:\s*`[^`]*`\s*\|\s*Estado:\s*)`[^`]+`"
                tmp.write_text(re.sub(pat, r"\g<1>`concluída`", tmp.read_text(encoding="utf-8")), encoding="utf-8")

    @staticmethod
    def _apply_turn_committed(tmp: Path, ev: Any, p: dict[str, Any]) -> None:
        d_text = tmp.read_text(encoding="utf-8").rstrip()
        loc = str(p.get("location", "Local Ativo"))
        pres = p.get("present", "")
        pres_str = ", ".join(str(x) for x in pres) if isinstance(pres, (list, tuple)) else str(pres)
        if p.get("time_changed", True) or p.get("location_changed", True):
            d_text = re.sub(r"(\*\s*\*\*Data\s*&\s*Local:\*\*\s*)[^\n]+", rf"\g<1>{ev.game_time} — {loc}.", d_text, count=1)
        if p.get("present_changed", bool(pres_str)) and pres_str:
            d_text = re.sub(r"(\*\s*\*\*Presentes:\*\*\s*)[^\n]+", rf"\g<1>{pres_str}.", d_text, count=1)
        tag_prefix = _SCENE_TAGS.get(str(p.get("scene_type", "standard")), "")
        clean_summary = re.sub(r"\s*Vitais:\s*[^\n]+$", "", str(p.get("summary", "")).strip()).rstrip(".")
        vitals_line = str(p.get("vitals_line") or "")
        if not vitals_line and isinstance(p.get("vitals"), dict) and p["vitals"]:
            vitals_line = ", ".join(f"{k.upper()} {v}" for k, v in p["vitals"].items())
        v_suffix = f" Vitais: {vitals_line}." if vitals_line else ""
        turn_num = int(p.get("turn", 1))
        if "### Histórico de Turnos" not in d_text:
            d_text = d_text.rstrip() + "\n\n### Histórico de Turnos"
        turn_entry = (
            f"\n* **Turno {turn_num} {tag_prefix.strip()}:** {clean_summary}.{v_suffix}\n"
            if tag_prefix
            else f"\n* **Turno {turn_num}:** {clean_summary}.{v_suffix}\n"
        )
        st_shift = str(p.get("state_shift") or "").strip().rstrip(".")
        if st_shift:
            turn_entry += f"  * **Mudança de Estado:** {st_shift}.\n"
        for al in p.get("alerts") or []:
            turn_entry += f"  * **Alerta:** {al}\n"
        tmp.write_text(d_text + turn_entry, encoding="utf-8")

    @staticmethod
    def _apply_faction_tick(tmp: Path, advancements: list[dict[str, Any]]) -> None:
        for adv in advancements:
            upsert_clock_in_diario(tmp, str(adv["clock"]), advance=1, create_if_missing=False)
        cur_turn = parse_diario_md(tmp).get("last_turn_num", 1)
        d_text = tmp.read_text(encoding="utf-8")
        lines = [f"* **Tick Off-Screen (Turno {cur_turn}):**"]
        for adv in advancements:
            b_note = " [Gatilho de Ruptura Disparado!]" if adv.get("status") == "BREACHED" else ""
            lines.append(f"  * **{adv['faction']}:** Avançou relógio '{adv['clock']}' para {adv['new_progress']} (Poder {adv['power']}){b_note}.")
        entry_block = "\n".join(lines)
        sec_header = "### Movimentações de Facções Off-Screen"
        if sec_header in d_text:
            m_sec = re.search(rf"({re.escape(sec_header)}[^\n]*\n)(.*?)(?=\n###|\Z)", d_text, re.DOTALL)
            if m_sec:
                d_text = d_text[: m_sec.start()] + m_sec.group(1) + m_sec.group(2).rstrip() + "\n" + entry_block + "\n" + d_text[m_sec.end() :]
            else:
                d_text = d_text.rstrip() + f"\n\n{sec_header}\n{entry_block}\n"
        elif "### Histórico de Turnos" in d_text:
            d_text = d_text.replace("### Histórico de Turnos", f"{sec_header}\n{entry_block}\n\n### Histórico de Turnos", 1)
        else:
            d_text = d_text.rstrip() + f"\n\n{sec_header}\n{entry_block}\n"
        tmp.write_text(d_text, encoding="utf-8")

    @staticmethod
    def _append_history(text: str, entry: str) -> str:
        header = "### Histórico de Turnos"
        if header not in text:
            return text.rstrip() + f"\n\n{header}\n{entry}\n"
        return text.rstrip() + f"\n{entry}\n"


__all__ = ["JournalProjector"]
