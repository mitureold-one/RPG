"""Provedores causais de conhecimento epistêmico, fatos e consequências."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from contracts.context import (
    ContextItem,
    ContextOmission,
    ContextRequest,
    ContextSection,
)
from contracts.ports import ContextStateView
from contracts.serialization import canonical_json
from resources.knowledge.model import HolderRef, KnowledgeRecord, ProvenanceRef
from resources.knowledge.view import KnowledgeView


def _section_hash(items: Sequence[ContextItem], omissions: Sequence[ContextOmission]) -> str:
    payload = {
        "items": [(i.kind, i.id, i.score, i.availability) for i in items],
        "omissions": [(o.kind, o.reference, o.availability) for o in omissions],
    }
    raw = canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()[:16]}"


def _dict_to_knowledge_record(d: Mapping[str, Any]) -> KnowledgeRecord | None:
    if not isinstance(d, Mapping) or not d.get("record_id") or not d.get("claim_id"):
        return None
    h_data = d.get("holder", {})
    if isinstance(h_data, HolderRef):
        holder = h_data
    elif isinstance(h_data, dict):
        holder = HolderRef(kind=h_data.get("kind", "npc"), id=str(h_data.get("id", "")))
    else:
        return None

    prov_list: list[ProvenanceRef] = []
    for p in d.get("provenance", ()):
        if isinstance(p, ProvenanceRef):
            prov_list.append(p)
        elif isinstance(p, dict):
            source_type = str(p.get("source_type") or "event")
            source_id = str(p.get("source_id") or p.get("source_event_id") or "")
            channel = str(p.get("channel") or ("observation" if p.get("method") == "direct_observation" else "observation"))
            acquired_at = str(p.get("acquired_at") or d.get("acquired_at", "01/01 00:00"))
            acquired_at_sort = int(p.get("acquired_at_sort") or d.get("acquired_at_sort", 0))
            confidence = int(p.get("confidence") if p.get("confidence") is not None else (p.get("reliability") or 10000))
            derived_from = tuple(str(x) for x in p.get("derived_from", ()))
            supports = bool(p.get("supports", True))
            prov_list.append(
                ProvenanceRef(
                    source_type=source_type,
                    source_id=source_id,
                    channel=channel,
                    acquired_at=acquired_at,
                    acquired_at_sort=acquired_at_sort,
                    confidence=confidence,
                    derived_from=derived_from,
                    supports=supports,
                )
            )

    awareness = str(d.get("awareness", "known"))
    if awareness not in ("known", "unknown"):
        awareness = "known" if awareness in ("aware", "true") else "unknown"

    stance = str(d.get("stance", "believed"))
    if stance not in ("believed", "disbelieved", "uncertain"):
        stance = "believed" if stance in ("believes_true", "true") else "uncertain"

    status = str(d.get("status", "current"))
    if status not in ("current", "outdated", "contested", "refuted"):
        status = "current" if status in ("active", "valid") else "outdated"

    return KnowledgeRecord(
        record_id=str(d["record_id"]),
        holder=holder,
        claim_id=str(d["claim_id"]),
        awareness=awareness,
        stance=stance,
        confidence=int(d.get("confidence", 10000)),
        status=status,
        provenance=tuple(prov_list),
        acquired_at=str(d.get("acquired_at", "01/01 00:00")),
        acquired_at_sort=int(d.get("acquired_at_sort", 0)),
        derived_from=tuple(str(x) for x in d.get("derived_from", ())),
        supersedes=tuple(str(x) for x in d.get("supersedes", ())),
        visibility=str(d.get("visibility", "holder_only")),
        shared_by=str(d["shared_by"]) if d.get("shared_by") else None,
    )


class KnowledgeCausalProvider:
    """Provedor epistêmico: injeta claims e crenças filtradas por audiência."""

    key = "knowledge_causal"
    layer = "causal"
    priority = 60

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        items: list[ContextItem] = []
        omissions: list[ContextOmission] = []

        records_map: dict[str, KnowledgeRecord] = {}
        for item in state.knowledge():
            rec = item if isinstance(item, KnowledgeRecord) else _dict_to_knowledge_record(item)
            if rec is not None:
                records_map[rec.record_id] = rec

        target_holder = (
            HolderRef(request.viewer.kind, request.viewer.id)
            if request.mode in ("narrator", "writer")
            else None
        )
        audience = HolderRef(request.audience.kind, request.audience.id)
        view = KnowledgeView(
            records=records_map,
            holder=target_holder,
            audience=audience,
            purpose=request.purpose,
        )

        # Detecta referências explícitas a claims na ação ou no foco
        text_to_scan = f"{request.action} {' '.join(request.focus)}"
        mentioned_claims = sorted(set(re.findall(r"\bclm_[a-zA-Z0-9_]+\b", text_to_scan)))

        for cid in mentioned_claims:
            res = view.query_claim(cid, target_holder=target_holder)
            if res.availability == "known" and res.record is not None:
                # Narrator e writer nunca recebem player_meta
                if request.mode in ("narrator", "writer") and res.record.visibility == "player_meta":
                    omissions.append(
                        ContextOmission(
                            kind="claim",
                            reference=cid,
                            availability="unavailable",
                            reason="Sigilo epistêmico: player_meta inacessível à narrativa",
                        )
                    )
                    continue

                payload = {
                    "claim_id": cid,
                    "stance": res.effective_stance or res.record.stance,
                    "confidence": res.effective_confidence or res.record.confidence,
                    "visibility": res.record.visibility,
                    "record_id": res.record.record_id,
                }
                items.append(
                    ContextItem(
                        kind="claim",
                        id=cid,
                        label=f"Alegação {cid}",
                        layer="causal",
                        score=500,
                        reasons=("mencao_explicita",),
                        availability="known",
                        payload=payload,
                        sources=(res.record.record_id,),
                    )
                )
            else:
                omissions.append(
                    ContextOmission(
                        kind="claim",
                        reference=cid,
                        availability=res.availability,
                        reason=res.reason or "Consulta epistêmica",
                    )
                )

        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=tuple(items),
            omissions=tuple(omissions),
            hash=_section_hash(items, omissions),
        )


class FactsCausalProvider:
    """Provedor causal de fatos recentes, correções e consequências de estado."""

    key = "facts_causal"
    layer = "causal"
    priority = 65

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        items: list[ContextItem] = []
        omissions: list[ContextOmission] = []

        recent = list(state.recent_events(limit=50))
        corrected_events: set[Any] = set()

        # Identifica correções emitidas
        for ev in recent:
            etype = ev.get("type", "") if isinstance(ev, dict) else getattr(ev, "type", "")
            payload = ev.get("payload", {}) if isinstance(ev, dict) else getattr(ev, "payload", {})
            if etype == "correction.issued":
                target_seq = payload.get("corrects") or payload.get("target_event")
                if isinstance(target_seq, (list, tuple, set)):
                    for s in target_seq:
                        if s:
                            corrected_events.add(s)
                            corrected_events.add(str(s))
                elif target_seq:
                    corrected_events.add(target_seq)
                    corrected_events.add(str(target_seq))

        facts_count = 0
        consequences_count = 0

        for ev in reversed(recent):
            seq = ev.get("seq", 0) if isinstance(ev, dict) else getattr(ev, "seq", 0)
            event_id = ev.get("event_id", "") if isinstance(ev, dict) else getattr(ev, "id", "")
            etype = ev.get("type", "") if isinstance(ev, dict) else getattr(ev, "type", "")
            summary = ev.get("summary", "") if isinstance(ev, dict) else getattr(ev, "summary", "")
            payload = ev.get("payload", {}) if isinstance(ev, dict) else getattr(ev, "payload", {})

            if etype == "correction.issued":
                if consequences_count < request.limits.max_consequences:
                    items.append(
                        ContextItem(
                            kind="consequence",
                            id=f"correction_{seq}",
                            label=f"Correção: {summary or 'Correção de fato'}",
                            layer="causal",
                            score=150,
                            reasons=("correcao_emitida",),
                            availability="known",
                            payload={"seq": seq, "summary": summary, "changes": payload.get("changes", [])},
                            sources=(f"evt_{seq}",),
                        )
                    )
                    consequences_count += 1
                continue

            if seq in corrected_events or str(seq) in corrected_events or (event_id and event_id in corrected_events):
                # Fato corrigido não entra como vigente!
                continue

            if etype in ("turn.committed", "action.resolved") and facts_count < request.limits.max_facts:
                items.append(
                    ContextItem(
                        kind="fact",
                        id=f"fact_{seq}",
                        label=f"Fato ({seq}): {summary}",
                        layer="causal",
                        score=100,
                        reasons=("fato_recente",),
                        availability="known",
                        payload={"seq": seq, "summary": summary, "type": etype},
                        sources=(f"evt_{seq}",),
                    )
                )
                facts_count += 1
            elif etype in ("clock.advanced", "faction.reputation_changed", "npc.plan_updated") and consequences_count < request.limits.max_consequences:
                items.append(
                    ContextItem(
                        kind="consequence",
                        id=f"consequence_{seq}",
                        label=f"Consequência ({etype}): {summary}",
                        layer="causal",
                        score=120,
                        reasons=("consequencia_recente",),
                        availability="known",
                        payload={"seq": seq, "type": etype, "summary": summary},
                        sources=(f"evt_{seq}",),
                    )
                )
                consequences_count += 1

        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=tuple(items),
            omissions=tuple(omissions),
            hash=_section_hash(items, omissions),
        )


__all__ = ["FactsCausalProvider", "KnowledgeCausalProvider"]
