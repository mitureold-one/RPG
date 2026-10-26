"""resources/knowledge/drafts.py: Fábricas de Drafts Canônicos de Conhecimento (Gate G3)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence
from contracts.event import ACTOR_KINDS, ActorRef, EventDraft
from kernel.ids import new_knowledge_id
from resources.knowledge.model import HolderRef, ProvenanceRef


def _default_actor_for_holder(holder: HolderRef) -> ActorRef:
    k = holder.kind
    if k == "player":
        return ActorRef(kind="human", id=holder.id)
    if k == "protagonist":
        return ActorRef(kind="npc", id=holder.id)
    if k == "subgroup":
        return ActorRef(kind="faction", id=holder.id)
    if k in ACTOR_KINDS:
        return ActorRef(kind=k, id=holder.id)
    return ActorRef(kind="agent", id=holder.id)


def make_claim_registered_draft(
    claim_id: str,
    proposition: Dict[str, Any],
    claim_type: str,
    game_time: str,
    game_time_sort: int,
    valid_from: Optional[int] = None,
    valid_to: Optional[int] = None,
    source_event_id: Optional[str] = None,
    fact_ref: Optional[str] = None,
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de knowledge.claim_registered."""
    act = actor or ActorRef(kind="system", id="engine")
    p: Dict[str, Any] = {
        "claim_id": claim_id,
        "proposition": dict(proposition),
        "claim_type": claim_type,
    }
    if valid_from is not None:
        p["valid_from"] = valid_from
    if valid_to is not None:
        p["valid_to"] = valid_to
    if source_event_id is not None:
        p["source_event_id"] = source_event_id
    if fact_ref is not None:
        p["fact_ref"] = fact_ref

    return EventDraft(
        type="knowledge.claim_registered",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload=p,
    )


def make_knowledge_acquired_draft(
    record_id: str,
    holder: HolderRef,
    claim_id: str,
    game_time: str,
    game_time_sort: int,
    awareness: str = "known",
    stance: str = "believed",
    confidence: int = 10000,
    provenance: Sequence[Dict[str, Any]] = (),
    status: Optional[str] = "current",
    visibility: Optional[str] = "holder_only",
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de knowledge.acquired."""
    act = actor or _default_actor_for_holder(holder)
    return EventDraft(
        type="knowledge.acquired",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "record_id": record_id,
            "holder": {"kind": holder.kind, "id": holder.id},
            "claim_id": claim_id,
            "awareness": awareness,
            "stance": stance,
            "confidence": confidence,
            "status": status,
            "provenance": list(provenance),
            "acquired_at": game_time,
            "acquired_at_sort": game_time_sort,
            "visibility": visibility,
        },
    )


def make_knowledge_inferred_draft(
    record_id: str,
    holder: HolderRef,
    claim_id: str,
    derived_from: Sequence[str],
    game_time: str,
    game_time_sort: int,
    stance: str = "believed",
    confidence: int = 8000,
    method: Optional[str] = "deduction",
    provenance: Sequence[Dict[str, Any]] = (),
    status: Optional[str] = "current",
    visibility: Optional[str] = "holder_only",
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de knowledge.inferred."""
    act = actor or _default_actor_for_holder(holder)
    return EventDraft(
        type="knowledge.inferred",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "record_id": record_id,
            "holder": {"kind": holder.kind, "id": holder.id},
            "claim_id": claim_id,
            "stance": stance,
            "confidence": confidence,
            "derived_from": list(derived_from),
            "method": method,
            "status": status,
            "provenance": list(provenance),
            "acquired_at": game_time,
            "acquired_at_sort": game_time_sort,
            "visibility": visibility,
        },
    )


def make_knowledge_revised_draft(
    record_id: str,
    holder: HolderRef,
    claim_id: str,
    stance: str,
    confidence: int,
    status: str,
    reason: str,
    game_time: str,
    game_time_sort: int,
    supersedes: Sequence[str] = (),
    provenance: Sequence[Dict[str, Any]] = (),
    visibility: Optional[str] = "holder_only",
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de knowledge.revised."""
    act = actor or _default_actor_for_holder(holder)
    return EventDraft(
        type="knowledge.revised",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "record_id": record_id,
            "holder": {"kind": holder.kind, "id": holder.id},
            "claim_id": claim_id,
            "stance": stance,
            "confidence": confidence,
            "status": status,
            "reason": reason,
            "supersedes": list(supersedes),
            "provenance": list(provenance),
            "acquired_at": game_time,
            "acquired_at_sort": game_time_sort,
            "visibility": visibility,
        },
    )


def make_knowledge_shared_draft(
    record_id: str,
    from_holder: HolderRef,
    to_holder: HolderRef,
    claim_id: str,
    scope: str,
    confidence: int,
    game_time: str,
    game_time_sort: int,
    stance: Optional[str] = "believed",
    visibility: Optional[str] = None,
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de knowledge.shared."""
    act = actor or _default_actor_for_holder(from_holder)
    p: Dict[str, Any] = {
        "record_id": record_id,
        "from_holder": {"kind": from_holder.kind, "id": from_holder.id},
        "to_holder": {"kind": to_holder.kind, "id": to_holder.id},
        "claim_id": claim_id,
        "scope": scope,
        "confidence": confidence,
        "stance": stance,
    }
    if visibility is not None:
        p["visibility"] = visibility

    return EventDraft(
        type="knowledge.shared",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload=p,
    )


def make_knowledge_claim_draft(
    holder: HolderRef,
    claim_id: str,
    game_time: str,
    game_time_sort: int,
    awareness: str = "known",
    stance: str = "believed",
    confidence: int = 10000,
    provenance: Sequence[ProvenanceRef] = (),
    derived_from: Sequence[str] = (),
    visibility: str = "holder_only",
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Wrapper retrocompatível para gerar knowledge.acquired."""
    rid = new_knowledge_id()
    prov_dicts = [
        {
            "source_type": pr.source_type,
            "source_id": pr.source_id,
            "channel": pr.channel,
            "acquired_at": pr.acquired_at,
            "acquired_at_sort": pr.acquired_at_sort,
            "confidence": pr.confidence,
            "derived_from": list(pr.derived_from),
            "supports": pr.supports,
        }
        for pr in provenance
    ]
    return make_knowledge_acquired_draft(
        record_id=rid,
        holder=holder,
        claim_id=claim_id,
        game_time=game_time,
        game_time_sort=game_time_sort,
        awareness=awareness,
        stance=stance,
        confidence=confidence,
        provenance=prov_dicts,
        status="current",
        visibility=visibility,
        actor=actor,
    )


__all__ = [
    "make_claim_registered_draft",
    "make_knowledge_acquired_draft",
    "make_knowledge_inferred_draft",
    "make_knowledge_revised_draft",
    "make_knowledge_shared_draft",
    "make_knowledge_claim_draft",
]
