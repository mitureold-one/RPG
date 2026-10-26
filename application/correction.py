"""application/correction.py: Serviço de correções causais e compensações (C4)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Sequence

from application.projectors.sheet import CharacterSheetProjector
from application.rebuild import rebuild_projections
from contracts.event import ActorRef, AppendResult, EventDraft
from contracts.ports import EventStore, EventStreamView
from contracts.serialization import canonical_json
from council.factions import clamp_reputation, normalize_ascii_slug, parse_reputation_from_ficha
from council.reviewer_checks import check_causal_inconsistencies
from kernel.dag import DependencyGraph
from kernel.errors import DuplicateBatchError, ValidationError
from kernel.ids import new_correction_id
from resources.sheet import normalize_vital_key, parse_ficha_md
from rulesets.progression import calculate_level_from_xp


def _draft(etype: str, actor: ActorRef, payload: dict[str, Any], gt: str, gts: int, meta: dict[str, Any]) -> EventDraft:
    return EventDraft(type=etype, schema_version=1, actor=actor, payload=payload, game_time=gt, game_time_sort=gts, meta=dict(meta))


def _project_current_sheet(all_events: tuple) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    cid = all_events[0].campaign_id if all_events else "default"
    sec = CharacterSheetProjector().project(EventStreamView(cid, all_events))
    with tempfile.TemporaryDirectory() as tmp_dir:
        p = Path(tmp_dir) / "ficha.md"
        p.write_text(sec.content, encoding="utf-8")
        return parse_ficha_md(p), parse_reputation_from_ficha(p)


class CorrectionService:
    """Gerencia emissão de correções, cálculo de compensações e alerta de inconsistências."""

    def __init__(self, store: EventStore, dep_graph: DependencyGraph | None = None, campaign_dir: Path | str | None = None) -> None:
        self.store = store
        self.dep_graph = dep_graph or DependencyGraph()
        self.campaign_dir = Path(campaign_dir) if campaign_dir is not None else None

    def _maybe_rebuild(self, campaign_id: str) -> None:
        target_dir = self.campaign_dir
        if target_dir is None and hasattr(self.store, "_campaign_dir"):
            cand = self.store._campaign_dir(campaign_id)
            if isinstance(cand, Path) and ((cand / "diario.md").exists() or (cand / "projections").exists()):
                target_dir = cand
        if target_dir is not None and target_dir.exists():
            rebuild_projections(self.store, campaign_id, target_dir, emit_audit_event=False)

    def issue_correction(
        self,
        campaign_id: str,
        actor: ActorRef,
        corrects: Sequence[str],
        reason: str,
        changes: Sequence[dict[str, Any]],
        game_time: str,
        game_time_sort: int,
        *,
        resolve: bool = False,
    ) -> AppendResult:
        if not corrects:
            raise ValidationError("A correção deve referenciar pelo menos um evento em 'corrects'")
        if not reason.strip():
            raise ValidationError("A correção exige justificativa explícita em 'reason'")

        all_events = tuple(self.store.read(campaign_id))
        event_by_id = {e.event_id: e for e in all_events}
        cor_events_by_id = {
            e.payload.get("correction_id"): e
            for e in all_events
            if e.type == "correction.issued" and e.payload.get("correction_id")
        }

        is_resolve = resolve or any(bool(c.get("resolve")) for c in changes)
        resolved_deps: list[str] = []
        for cid in corrects:
            if cid in event_by_id:
                resolved_deps.append(cid)
            elif cid in cor_events_by_id:
                resolved_deps.append(cor_events_by_id[cid].event_id)
            else:
                raise ValidationError(f"Evento corrigido não encontrado: '{cid}'")

        if not is_resolve:
            deps_key = sorted(resolved_deps)
            changes_key = canonical_json(list(changes))
            for existing in all_events:
                if existing.type != "correction.issued":
                    continue
                if (
                    sorted(existing.payload.get("corrects", [])) == deps_key
                    and canonical_json(existing.payload.get("changes", [])) == changes_key
                    and str(existing.payload.get("reason", "")).strip() == reason.strip()
                ):
                    existing_cor_id = existing.payload.get("correction_id")
                    already_resolved = any(
                        e.type == "correction.recomputed"
                        and e.payload.get("correction_id") == existing_cor_id
                        and e.payload.get("outcome") == "RESOLVED"
                        for e in all_events
                    )
                    if not already_resolved:
                        raise DuplicateBatchError(
                            "Correção idêntica já registrada e ainda pendente; resolva-a ou altere motivo/alterações.",
                            details={"correction_id": existing_cor_id, "corrects": deps_key},
                        )

        forward_adj: dict[str, list[str]] = {}
        for e in all_events:
            for dep in e.meta.get("dependencies", []):
                forward_adj.setdefault(dep, []).append(e.event_id)

        affected_ids = self.dep_graph.get_dependents_transitive(resolved_deps, forward_adj)
        cor_id = new_correction_id()
        expected_seq = all_events[-1].seq if all_events else 0

        if is_resolve:
            target_cor_id = str(corrects[0])
            if target_cor_id in event_by_id and event_by_id[target_cor_id].type == "correction.issued":
                target_cor_id = str(event_by_id[target_cor_id].payload.get("correction_id", target_cor_id))
            drafts = [
                _draft(
                    "correction.recomputed",
                    actor,
                    {"correction_id": target_cor_id, "affected": affected_ids, "outcome": "RESOLVED"},
                    game_time,
                    game_time_sort,
                    {"dependencies": resolved_deps},
                )
            ]
            res = self.store.append(campaign_id, drafts, expected_last_seq=expected_seq)
            self._maybe_rebuild(campaign_id)
            return res

        inconsistency_detected = any(bool(c.get("inconsistent") or c.get("contradiction")) for c in changes)
        drafts = [
            _draft(
                "correction.issued",
                actor,
                {
                    "correction_id": cor_id,
                    "corrects": list(resolved_deps),
                    "reason": reason.strip(),
                    "changes": list(changes),
                    "state": "pendente" if inconsistency_detected else "concluída",
                    "inconsistency_detected": inconsistency_detected,
                },
                game_time,
                game_time_sort,
                {"dependencies": list(resolved_deps)},
            )
        ]

        if not inconsistency_detected:
            meta_comp = {"dependencies": list(resolved_deps), "correction_id": cor_id}
            for ch in changes:
                self._append_compensation_drafts(drafts, ch, all_events, actor, cor_id, reason.strip(), game_time, game_time_sort, meta_comp)

        if affected_ids or inconsistency_detected:
            outcome = "INCONSISTENCY_PENDING_REVIEW" if inconsistency_detected else "COMPENSATED"
            drafts.append(
                _draft(
                    "correction.recomputed",
                    actor,
                    {"correction_id": cor_id, "affected": affected_ids, "outcome": outcome},
                    game_time,
                    game_time_sort,
                    {"dependencies": list(resolved_deps)},
                )
            )

        res = self.store.append(campaign_id, drafts, expected_last_seq=expected_seq)
        self._maybe_rebuild(campaign_id)
        return res

    @staticmethod
    def _append_compensation_drafts(
        drafts: list[EventDraft],
        ch: dict[str, Any],
        all_events: tuple,
        actor: ActorRef,
        cor_id: str,
        reason: str,
        gt: str,
        gts: int,
        meta_comp: dict[str, Any],
    ) -> None:
        field = ch.get("field")
        if field in ("xp_delta", "xp"):
            delta = int(ch.get("delta", 0))
            cur_xp = 0
            for e in all_events:
                if e.type == "protagonist.progression_changed":
                    cur_xp = int(e.payload.get("xp_total", cur_xp))
            new_xp = max(0, cur_xp + delta)
            new_level, _ = calculate_level_from_xp(new_xp)
            payload = {
                "xp_delta": delta,
                "xp_total": new_xp,
                "level": new_level,
                "attribute_points": 0,
                "ability_points": 0,
                "source": f"compensação_{cor_id}",
            }
            drafts.append(_draft("protagonist.progression_changed", actor, payload, gt, gts, meta_comp))
        elif field in ("sheet", "vital", "hp", "stamina", "ce", "mana", "attribute", "item", "condition"):
            kind = str(ch.get("kind") or ("vital" if field in ("hp", "stamina", "ce", "mana", "vital") else field))
            target = str(ch.get("target", field))
            if kind == "vital":
                ficha_data, _ = _project_current_sheet(all_events)
                vitals = ficha_data.get("vitals", {})
                v_key = normalize_vital_key(target, vitals)
                v_info = dict(vitals.get(v_key, {"current": 0, "max": 9999}))
                for d in drafts:
                    if d.type == "protagonist.sheet_changed" and d.payload.get("kind") == "vital" and d.payload.get("target") == v_key:
                        v_info["current"] = int(d.payload["new_value"])
                raw_new = ch.get("new_value")
                is_signed_str = isinstance(raw_new, str) and raw_new.strip().startswith(("-", "+")) and raw_new.strip()[1:].isdigit()
                if "delta" in ch and raw_new is None:
                    delta_v = int(ch["delta"])
                    new_val = max(0, min(v_info["max"], v_info["current"] + delta_v))
                elif is_signed_str:
                    delta_v = int(str(raw_new).strip())
                    new_val = max(0, min(v_info["max"], v_info["current"] + delta_v))
                else:
                    new_val = max(0, min(v_info["max"], int(raw_new if raw_new is not None else ch.get("delta", 0))))
                    delta_v = new_val - v_info["current"]
                payload = {"kind": "vital", "target": v_key, "delta": delta_v, "new_value": new_val, "source": f"compensação_{cor_id}"}
            else:
                new_val = ch.get("new_value", ch.get("delta", 0))
                payload = {"kind": kind, "target": target, "new_value": new_val, "source": f"compensação_{cor_id}"}
            drafts.append(_draft("protagonist.sheet_changed", actor, payload, gt, gts, meta_comp))
        elif field == "reputation" and ch.get("faction"):
            fac = str(ch["faction"]).strip()
            fac_slug = normalize_ascii_slug(fac).lower()
            _, reps = _project_current_sheet(all_events)
            cur_score = reps.get(fac.lower(), reps.get(fac_slug, {})).get("score", 0)
            for e in (*all_events, *drafts):
                if e.type == "faction.reputation_changed":
                    efac = str(e.payload.get("faction", "")).strip()
                    if efac.lower() == fac.lower() or normalize_ascii_slug(efac).lower() == fac_slug:
                        if "new_score" in e.payload:
                            cur_score = clamp_reputation(int(e.payload["new_score"]))
                        else:
                            cur_score = clamp_reputation(cur_score + int(e.payload.get("delta_rep", 0)))
            if "new_score" in ch:
                new_score = clamp_reputation(int(ch["new_score"]))
                delta = int(ch.get("delta", new_score - cur_score))
            else:
                delta = int(ch.get("delta", 0))
                new_score = clamp_reputation(cur_score + delta)
            payload = {"faction": fac, "delta_rep": delta, "new_score": new_score, "reason": f"compensação_{cor_id}: {reason}"}
            drafts.append(_draft("faction.reputation_changed", actor, payload, gt, gts, meta_comp))
        elif field == "clock":
            c_name = str(ch.get("name") or ch.get("clock") or "Relógio")
            cur_val, mx_val = 0, 4
            for e in all_events:
                if e.type in ("clock.created", "clock.advanced") and str(e.payload.get("name", "")).lower() == c_name.lower():
                    if "max" in e.payload:
                        mx_val = int(e.payload["max"])
                    if "current" in e.payload:
                        cur_val = int(e.payload["current"])
                    elif "delta" in e.payload:
                        cur_val = max(0, cur_val + int(e.payload["delta"]))
            mx_val = int(ch.get("max", mx_val))
            if "current" in ch:
                new_cur = max(0, int(ch["current"]))
                delta = new_cur - cur_val
            elif "delta" in ch:
                delta = int(ch["delta"])
                new_cur = max(0, cur_val + delta)
            else:
                delta, new_cur = 0, cur_val
            new_status = str(ch.get("status") or ("BREACHED" if new_cur >= mx_val else "ACTIVE")).upper()
            payload = {"name": c_name, "delta": delta, "current": new_cur, "max": mx_val, "status": new_status}
            drafts.append(_draft("clock.advanced", actor, payload, gt, gts, meta_comp))
            if new_status == "RESOLVED":
                drafts.append(_draft("clock.resolved", actor, {"name": c_name, "outcome": "RESOLVED"}, gt, gts, meta_comp))
        elif field == "quest":
            qid = str(ch.get("quest_id") or ch.get("id") or "Q1").upper()
            new_status = str(ch.get("status", "ACTIVE")).upper()
            payload = {"id": qid, "status": new_status, "reason": f"compensação_{cor_id}: {reason}"}
            drafts.append(_draft("quest.status_changed", actor, payload, gt, gts, meta_comp))
        elif field == "arc":
            arc_payload = {k: str(ch[k]) for k in ("title", "stage", "question") if ch.get(k)}
            if arc_payload:
                drafts.append(_draft("arc.updated", actor, arc_payload, gt, gts, meta_comp))


__all__ = ["CorrectionService", "check_causal_inconsistencies"]
