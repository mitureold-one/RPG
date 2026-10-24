"""application/correction.py: Serviço de correções causais e compensações (C4)."""

from __future__ import annotations

from typing import Any, Sequence

from contracts.event import ActorRef, AppendResult, EventDraft
from contracts.ports import EventStore
from contracts.serialization import canonical_json
from council.reviewer_checks import check_causal_inconsistencies
from kernel.dag import DependencyGraph
from kernel.errors import DuplicateBatchError, ValidationError
from kernel.ids import new_correction_id
from rulesets.progression import calculate_level_from_xp


class CorrectionService:
    """Gerencia emissão de correções, cálculo de compensações e alerta de inconsistências."""

    def __init__(
        self,
        store: EventStore,
        dep_graph: DependencyGraph | None = None,
    ) -> None:
        self.store = store
        self.dep_graph = dep_graph or DependencyGraph()

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

        # Idempotência: uma correção idêntica pendente não pode gerar outra
        # compensação. Depois de RESOLVED, uma nova correção é permitida.
        if not is_resolve:
            deps_key = sorted(resolved_deps)
            changes_key = canonical_json(list(changes))
            for existing in all_events:
                if existing.type != "correction.issued":
                    continue
                if sorted(existing.payload.get("corrects", [])) != deps_key:
                    continue
                if canonical_json(existing.payload.get("changes", [])) != changes_key:
                    continue
                if str(existing.payload.get("reason", "")).strip() != reason.strip():
                    continue
                existing_cor_id = existing.payload.get("correction_id")
                already_resolved = any(
                    e.type == "correction.recomputed"
                    and e.payload.get("correction_id") == existing_cor_id
                    and e.payload.get("outcome") == "RESOLVED"
                    for e in all_events
                )
                if not already_resolved:
                    raise DuplicateBatchError(
                        "Correção idêntica já registrada e ainda pendente; "
                        "resolva-a ou altere motivo/alterações.",
                        details={
                            "correction_id": existing_cor_id,
                            "corrects": deps_key,
                        },
                    )

        forward_adj: dict[str, list[str]] = {}
        for e in all_events:
            for dep in e.meta.get("dependencies", []):
                forward_adj.setdefault(dep, []).append(e.event_id)

        affected_ids = self.dep_graph.get_dependents_transitive(resolved_deps, forward_adj)
        cor_id = new_correction_id()

        if is_resolve:
            target_cor_id = str(corrects[0])
            if target_cor_id in event_by_id and event_by_id[target_cor_id].type == "correction.issued":
                target_cor_id = str(event_by_id[target_cor_id].payload.get("correction_id", target_cor_id))
            drafts = [
                EventDraft(
                    type="correction.recomputed",
                    schema_version=1,
                    actor=actor,
                    payload={
                        "correction_id": target_cor_id,
                        "affected": affected_ids,
                        "outcome": "RESOLVED",
                    },
                    game_time=game_time,
                    game_time_sort=game_time_sort,
                    meta={"dependencies": resolved_deps},
                )
            ]
            return self.store.append(campaign_id, drafts, expected_last_seq=all_events[-1].seq if all_events else 0)

        inconsistency_detected = any(
            bool(c.get("inconsistent") or c.get("contradiction")) for c in changes
        )

        drafts = [
            EventDraft(
                type="correction.issued",
                schema_version=1,
                actor=actor,
                payload={
                    "correction_id": cor_id,
                    "corrects": list(resolved_deps),
                    "reason": reason.strip(),
                    "changes": list(changes),
                    "state": "pendente" if inconsistency_detected else "concluída",
                    "inconsistency_detected": inconsistency_detected,
                },
                game_time=game_time,
                game_time_sort=game_time_sort,
                meta={"dependencies": list(resolved_deps)},
            )
        ]

        if not inconsistency_detected:
            for ch in changes:
                field = ch.get("field")
                if field in ("xp_delta", "xp"):
                    delta = int(ch.get("delta", 0))
                    cur_xp = 0
                    for e in all_events:
                        if e.type == "protagonist.progression_changed":
                            cur_xp = int(e.payload.get("xp_total", cur_xp))
                    new_xp = max(0, cur_xp + delta)
                    new_level, _ = calculate_level_from_xp(new_xp)
                    drafts.append(
                        EventDraft(
                            type="protagonist.progression_changed",
                            schema_version=1,
                            actor=actor,
                            payload={
                                "xp_delta": delta,
                                "xp_total": new_xp,
                                "level": new_level,
                                "attribute_points": 0,
                                "ability_points": 0,
                                "source": f"compensação_{cor_id}",
                            },
                            game_time=game_time,
                            game_time_sort=game_time_sort,
                            meta={"dependencies": list(resolved_deps), "correction_id": cor_id},
                        )
                    )
                elif field in ("vital", "hp", "stamina", "ce", "attribute", "item", "condition"):
                    target = str(ch.get("target", field))
                    new_val = ch.get("new_value", ch.get("delta", 0))
                    drafts.append(
                        EventDraft(
                            type="protagonist.sheet_changed",
                            schema_version=1,
                            actor=actor,
                            payload={
                                "kind": str(field),
                                "target": target,
                                "new_value": new_val,
                                "source": f"compensação_{cor_id}",
                            },
                            game_time=game_time,
                            game_time_sort=game_time_sort,
                            meta={"dependencies": list(resolved_deps), "correction_id": cor_id},
                        )
                    )
                elif field == "reputation" and ch.get("faction"):
                    fac = str(ch["faction"])
                    delta = int(ch.get("delta", 0))
                    new_score = int(ch.get("new_score", delta))
                    drafts.append(
                        EventDraft(
                            type="faction.reputation_changed",
                            schema_version=1,
                            actor=actor,
                            payload={
                                "faction": fac,
                                "delta_rep": delta,
                                "new_score": new_score,
                                "reason": f"compensação_{cor_id}: {reason.strip()}",
                            },
                            game_time=game_time,
                            game_time_sort=game_time_sort,
                            meta={"dependencies": list(resolved_deps), "correction_id": cor_id},
                        )
                    )

        if affected_ids or inconsistency_detected:
            outcome = "INCONSISTENCY_PENDING_REVIEW" if inconsistency_detected else "COMPENSATED"
            drafts.append(
                EventDraft(
                    type="correction.recomputed",
                    schema_version=1,
                    actor=actor,
                    payload={
                        "correction_id": cor_id,
                        "affected": affected_ids,
                        "outcome": outcome,
                    },
                    game_time=game_time,
                    game_time_sort=game_time_sort,
                    meta={"dependencies": list(resolved_deps)},
                )
            )

        expected_seq = all_events[-1].seq if all_events else 0
        return self.store.append(campaign_id, drafts, expected_last_seq=expected_seq)


__all__ = ["CorrectionService", "check_causal_inconsistencies"]
