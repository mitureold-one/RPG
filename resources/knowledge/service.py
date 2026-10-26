"""resources/knowledge/service.py: Projeção de Estado Epistêmico e Isolamento Causal (Gate G3).

Reconstrói deterministicamente o mapa de KnowledgeRecords a partir dos eventos canônicos,
gerencia transições de status (current, contested, outdated, refuted) e isola crenças
subjetivas de agentes contra mutações causais mágicas (AT15).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from resources.knowledge.drafts import (
    make_claim_registered_draft,
    make_knowledge_acquired_draft,
    make_knowledge_claim_draft,
    make_knowledge_inferred_draft,
    make_knowledge_revised_draft,
    make_knowledge_shared_draft,
)
from resources.knowledge.model import (
    HolderRef,
    KnowledgeRecord,
    ProvenanceRef,
)


class KnowledgeState(dict):
    """Mapa de KnowledgeRecords indexado por record_id com metadados de alegações registradas."""

    def __init__(self, *args, registered_claims: Optional[Sequence[str]] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.registered_claims: Set[str] = set(registered_claims or ())


def _parse_provenance_list(
    raw_list: Sequence[Dict[str, Any]],
    default_game_time: str,
    default_sort: int,
) -> Tuple[ProvenanceRef, ...]:
    provs: List[ProvenanceRef] = []
    for pr in raw_list:
        provs.append(
            ProvenanceRef(
                source_type=pr.get("source_type", "observation"),
                source_id=pr.get("source_id", ""),
                channel=pr.get("channel", "observation"),
                acquired_at=pr.get("acquired_at", default_game_time),
                acquired_at_sort=pr.get("acquired_at_sort", default_sort),
                confidence=int(pr.get("confidence", 10000)),
                derived_from=tuple(pr.get("derived_from", ())),
                supports=bool(pr.get("supports", True)),
            )
        )
    return tuple(provs)


def project_knowledge_state(
    events: Sequence[Any],
    current_time_sort: Optional[int] = None,
    claim_validity_map: Optional[Dict[str, Tuple[Optional[int], Optional[int]]]] = None,
) -> Dict[str, KnowledgeRecord]:
    """Reconstrói deterministicamente o mapa de KnowledgeRecord (record_id -> KnowledgeRecord).

    Suporta os 5 eventos canônicos v1:
    - knowledge.claim_registered
    - knowledge.acquired
    - knowledge.inferred
    - knowledge.revised
    - knowledge.shared

    Regra de Ouro (AT15):
    Eventos 'correction.issued' NÃO alteram crenças ou memórias subjetivas dos agentes.
    """
    records: Dict[str, KnowledgeRecord] = {}
    claim_windows: Dict[str, Tuple[Optional[int], Optional[int]]] = dict(claim_validity_map or {})

    for ev in events:
        evt = getattr(ev, "event", ev)
        p = evt.payload or {}
        etype = evt.type
        gt = evt.game_time
        gts = evt.game_time_sort

        if etype == "knowledge.claim_registered":
            cid = p.get("claim_id")
            if cid:
                claim_windows[cid] = (p.get("valid_from"), p.get("valid_to"))

        elif etype == "knowledge.acquired":
            rid = p.get("record_id")
            if not rid:
                continue
            h_data = p.get("holder", {})
            holder = HolderRef(kind=h_data.get("kind", "npc"), id=h_data.get("id", ""))
            provs = _parse_provenance_list(p.get("provenance", ()), gt, gts)
            records[rid] = KnowledgeRecord(
                record_id=rid,
                holder=holder,
                claim_id=p.get("claim_id", ""),
                awareness=p.get("awareness", "known"),
                stance=p.get("stance", "believed"),
                confidence=int(p.get("confidence", 10000)),
                status=p.get("status") or "current",
                provenance=provs,
                acquired_at=p.get("acquired_at") or gt,
                acquired_at_sort=p.get("acquired_at_sort", gts),
                derived_from=tuple(p.get("derived_from", ())),
                supersedes=tuple(p.get("supersedes", ())),
                visibility=p.get("visibility") or "holder_only",
                shared_by=p.get("shared_by"),
            )

        elif etype == "knowledge.inferred":
            rid = p.get("record_id")
            if not rid:
                continue
            h_data = p.get("holder", {})
            holder = HolderRef(kind=h_data.get("kind", "npc"), id=h_data.get("id", ""))
            raw_prov = p.get("provenance", ())
            if not raw_prov and p.get("derived_from"):
                provs = (
                    ProvenanceRef(
                        source_type="inference",
                        source_id=f"inf_{rid}",
                        channel="inference",
                        acquired_at=gt,
                        acquired_at_sort=gts,
                        confidence=int(p.get("confidence", 8000)),
                        derived_from=tuple(p.get("derived_from", ())),
                        supports=True,
                    ),
                )
            else:
                provs = _parse_provenance_list(raw_prov, gt, gts)

            records[rid] = KnowledgeRecord(
                record_id=rid,
                holder=holder,
                claim_id=p.get("claim_id", ""),
                awareness="known",
                stance=p.get("stance", "believed"),
                confidence=int(p.get("confidence", 8000)),
                status=p.get("status") or "current",
                provenance=provs,
                acquired_at=p.get("acquired_at") or gt,
                acquired_at_sort=p.get("acquired_at_sort", gts),
                derived_from=tuple(p.get("derived_from", ())),
                supersedes=(),
                visibility=p.get("visibility") or "holder_only",
                shared_by=None,
            )

        elif etype == "knowledge.revised":
            rid = p.get("record_id")
            if not rid:
                continue
            old = records.get(rid)
            h_data = p.get("holder", {})
            holder = HolderRef(kind=h_data.get("kind", "npc"), id=h_data.get("id", "")) if h_data else (old.holder if old else HolderRef("npc", "unknown"))
            provs = _parse_provenance_list(p.get("provenance", ()), gt, gts) if "provenance" in p else (old.provenance if old else ())
            records[rid] = KnowledgeRecord(
                record_id=rid,
                holder=holder,
                claim_id=p.get("claim_id") or (old.claim_id if old else ""),
                awareness="known",
                stance=p.get("stance") or (old.stance if old else "believed"),
                confidence=int(p.get("confidence") if p.get("confidence") is not None else (old.confidence if old else 10000)),
                status=p.get("status") or "current",
                provenance=provs,
                acquired_at=old.acquired_at if old else gt,
                acquired_at_sort=old.acquired_at_sort if old else gts,
                derived_from=old.derived_from if old else (),
                supersedes=tuple(p.get("supersedes") or (old.supersedes if old else ())),
                visibility=p.get("visibility") or (old.visibility if old else "holder_only"),
                shared_by=old.shared_by if old else None,
            )

        elif etype == "knowledge.shared":
            rid = p.get("record_id")
            if not rid:
                continue
            to_h_data = p.get("to_holder", {})
            to_holder = HolderRef(kind=to_h_data.get("kind", "npc"), id=to_h_data.get("id", ""))
            from_h_data = p.get("from_holder", {})
            from_id = from_h_data.get("id", "unknown")
            from_kind = from_h_data.get("kind", "npc")
            scope = p.get("scope", "direct")
            vis = p.get("visibility")
            if not vis:
                vis = "subgroup_only" if scope == "subgroup_only" else ("faction_internal" if scope in ("faction", "faction_internal") else "holder_only")

            src_type = from_kind if from_kind in ("npc", "faction", "subgroup", "player", "protagonist", "system", "document", "event", "inference") else "npc"
            provs = (
                ProvenanceRef(
                    source_type=src_type,
                    source_id=from_id,
                    channel="communication",
                    acquired_at=gt,
                    acquired_at_sort=gts,
                    confidence=int(p.get("confidence", 10000)),
                    derived_from=(),
                    supports=True,
                ),
            )
            records[rid] = KnowledgeRecord(
                record_id=rid,
                holder=to_holder,
                claim_id=p.get("claim_id", ""),
                awareness="known",
                stance=p.get("stance") or "believed",
                confidence=int(p.get("confidence", 10000)),
                status="current",
                provenance=provs,
                acquired_at=gt,
                acquired_at_sort=gts,
                derived_from=(),
                supersedes=(),
                visibility=vis,
                shared_by=from_id,
            )

    # 1. Consolidação inter-registros de evidências conflitantes (contested / uncertain)
    by_holder_claim: Dict[Tuple[HolderRef, str], List[str]] = {}
    for rid, rec in records.items():
        by_holder_claim.setdefault((rec.holder, rec.claim_id), []).append(rid)

    for (holder, claim_id), rids in by_holder_claim.items():
        all_provs = [pr for rid in rids for pr in records[rid].provenance]
        has_sup = any(pr.supports for pr in all_provs)
        has_opp = any(not pr.supports for pr in all_provs)
        if has_sup and has_opp:
            for rid in rids:
                rec = records[rid]
                if rec.status == "current":
                    records[rid] = KnowledgeRecord(
                        record_id=rec.record_id,
                        holder=rec.holder,
                        claim_id=rec.claim_id,
                        awareness=rec.awareness,
                        stance="uncertain",
                        confidence=min(rec.confidence, 5000),
                        status="contested",
                        provenance=rec.provenance,
                        acquired_at=rec.acquired_at,
                        acquired_at_sort=rec.acquired_at_sort,
                        derived_from=rec.derived_from,
                        supersedes=rec.supersedes,
                        visibility=rec.visibility,
                        shared_by=rec.shared_by,
                    )

    # 2. Transição determinística para desatualizado (outdated) em janelas temporais expiradas
    if current_time_sort is not None:
        for rid, rec in list(records.items()):
            if rec.status == "current":
                window = claim_windows.get(rec.claim_id)
                if window and window[1] is not None and current_time_sort > window[1]:
                    records[rid] = KnowledgeRecord(
                        record_id=rec.record_id,
                        holder=rec.holder,
                        claim_id=rec.claim_id,
                        awareness=rec.awareness,
                        stance=rec.stance,
                        confidence=rec.confidence,
                        status="outdated",
                        provenance=rec.provenance,
                        acquired_at=rec.acquired_at,
                        acquired_at_sort=rec.acquired_at_sort,
                        derived_from=rec.derived_from,
                        supersedes=rec.supersedes,
                        visibility=rec.visibility,
                        shared_by=rec.shared_by,
                    )

    return KnowledgeState(records, registered_claims=list(claim_windows.keys()))


__all__ = [
    "KnowledgeState",
    "project_knowledge_state",
    "make_claim_registered_draft",
    "make_knowledge_acquired_draft",
    "make_knowledge_inferred_draft",
    "make_knowledge_revised_draft",
    "make_knowledge_shared_draft",
    "make_knowledge_claim_draft",
]
