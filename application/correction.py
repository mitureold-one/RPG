"""application/correction.py: Serviço de correções causais e compensações (C4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from contracts.event import ActorRef, AppendResult, EventDraft
from contracts.ports import EventStore
from kernel.dag import DependencyGraph
from kernel.errors import ValidationError
from kernel.ids import _next_ulid


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
    ) -> AppendResult:
        if not corrects:
            raise ValidationError("A correção deve referenciar pelo menos um evento em 'corrects'")
        if not reason.strip():
            raise ValidationError("A correção exige justificativa explícita em 'reason'")

        all_events = tuple(self.store.read(campaign_id))
        event_by_id = {e.event_id: e for e in all_events}

        for cid in corrects:
            if cid not in event_by_id:
                raise ValidationError(f"Evento corrigido não encontrado: '{cid}'")

        # Constrói adjacência direta para expansão de dependentes
        forward_adj: dict[str, list[str]] = {}
        for e in all_events:
            for dep in e.meta.get("dependencies", []):
                forward_adj.setdefault(dep, []).append(e.event_id)

        affected_ids = self.dep_graph.get_dependents_transitive(corrects, forward_adj)
        cor_id = f"cor_{_next_ulid()}"

        # Verifica se alguma mudança invalida premissas de eventos posteriores (C4)
        inconsistency_detected = any(
            bool(c.get("inconsistent") or c.get("contradiction")) for c in changes
        )

        drafts: list[EventDraft] = []

        # 1. Evento principal de correção
        drafts.append(
            EventDraft(
                type="correction.issued",
                schema_version=1,
                actor=actor,
                payload={
                    "correction_id": cor_id,
                    "corrects": list(corrects),
                    "reason": reason.strip(),
                    "changes": list(changes),
                    "state": "pendente" if inconsistency_detected else "concluída",
                    "inconsistency_detected": inconsistency_detected,
                },
                game_time=game_time,
                game_time_sort=game_time_sort,
                meta={"dependencies": list(corrects)},
            )
        )

        # 2. Eventos compensatórios numéricos se não houver contradição
        if not inconsistency_detected:
            for ch in changes:
                field = ch.get("field")
                if field == "xp_delta":
                    delta = int(ch.get("delta", 0))
                    cur_xp = 0
                    cur_level = 1
                    for e in all_events:
                        if e.type == "protagonist.progression_changed":
                            cur_xp = e.payload.get("xp_total", cur_xp)
                            cur_level = e.payload.get("level", cur_level)
                    new_xp = max(0, cur_xp + delta)
                    drafts.append(
                        EventDraft(
                            type="protagonist.progression_changed",
                            schema_version=1,
                            actor=actor,
                            payload={
                                "xp_delta": delta,
                                "xp_total": new_xp,
                                "level": cur_level,
                                "attribute_points": 0,
                                "ability_points": 0,
                                "source": f"compensação_{cor_id}",
                            },
                            game_time=game_time,
                            game_time_sort=game_time_sort,
                            meta={"dependencies": list(corrects), "correction_id": cor_id},
                        )
                    )

        # 3. Notificação de recomputação de dependentes
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
                    meta={"dependencies": list(corrects)},
                )
            )

        return self.store.append(campaign_id, drafts)


def check_causal_inconsistencies(campaign_dir: Path | str, campaign_id: str) -> list[dict[str, str]]:
    """Detecta correções pendentes ou inconsistências causais no event log (Critério C4)."""
    c_dir = Path(campaign_dir)
    events_dir = c_dir / "events"
    if not events_dir.exists():
        return []
    from adapters.persistence.event_store import JsonlEventStore

    store = JsonlEventStore(base_dir=c_dir.parent)
    issues: list[dict[str, str]] = []
    for ev in store.read(campaign_id):
        if ev.type == "correction.issued" and ev.payload.get("inconsistency_detected"):
            cor_id = ev.payload.get("correction_id", "desconhecida")
            reason = ev.payload.get("reason", "")
            issues.append({
                "type": "CAUSAL_INCONSISTENCY",
                "severity": "CRITICAL",
                "detail": f"Inconsistência Causal Pendente: A correção '{cor_id}' invalidou premissas posteriores ('{reason}').",
            })
    return issues


__all__ = ["CorrectionService", "check_causal_inconsistencies"]
