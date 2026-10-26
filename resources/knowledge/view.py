"""resources/knowledge/view.py: Visões Epistêmicas e Provedor Contextualizado (Gate G3).

Consultas contextualizadas por holder/audience com matriz de visibilidade estrita (R-P0-2),
isolamento de player_meta/faction_internal e resultado tipado ClaimQueryResult (P0-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set
from contracts.ports import KnowledgeProvider
from resources.knowledge.model import HolderRef, KnowledgeRecord

VALID_AVAILABILITIES = {"known", "unknown", "unavailable", "inexistent"}


@dataclass(frozen=True)
class ClaimQueryResult:
    """Resultado tipado de uma consulta epistêmica sobre uma alegação."""
    claim_id: str
    availability: str
    record: Optional[KnowledgeRecord] = None
    effective_stance: Optional[str] = None
    effective_confidence: int = 0
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.availability not in VALID_AVAILABILITIES:
            raise ValueError(f"availability inválida: '{self.availability}'")


class KnowledgeView:
    """Visão de consulta epistêmica contextualizada por holder, audience e purpose."""

    def __init__(
        self,
        records_or_holder: Any = None,
        holder_or_audience: Any = None,
        audience_or_purpose: Any = None,
        purpose: str = "decision",
        npc_affiliations: Optional[Dict[str, Dict[str, str]]] = None,
        records: Optional[Dict[str, KnowledgeRecord]] = None,
        holder: Optional[HolderRef] = None,
        audience: Optional[HolderRef] = None,
    ) -> None:
        self._records = records if records is not None else (records_or_holder if isinstance(records_or_holder, dict) else {})
        self._holder = holder or (records_or_holder if isinstance(records_or_holder, HolderRef) else (holder_or_audience if isinstance(holder_or_audience, HolderRef) else None))
        self._audience = audience or (holder_or_audience if isinstance(holder_or_audience, HolderRef) and self._holder != holder_or_audience else (audience_or_purpose if isinstance(audience_or_purpose, HolderRef) else self._holder))
        self._purpose = purpose if isinstance(purpose, str) else (audience_or_purpose if isinstance(audience_or_purpose, str) else "decision")
        self._affiliations = npc_affiliations or {}
        self._registered_claims = set(getattr(self._records, "registered_claims", ()))

    @property
    def holder(self) -> Optional[HolderRef]:
        return self._holder

    @property
    def audience(self) -> Optional[HolderRef]:
        return self._audience

    @property
    def purpose(self) -> str:
        return self._purpose

    def _is_accessible(self, rec: KnowledgeRecord, aud: Optional[HolderRef]) -> bool:
        """Aplica a matriz estrita de visibilidade (FR-FIX-08)."""
        if not aud:
            return rec.visibility == "public"
        vis = rec.visibility
        if vis == "public":
            return True
        if vis == "player_meta":
            return aud.kind in ("player", "human")
        if vis == "protagonist_private":
            return aud.kind in ("protagonist", "player", "human")
        if vis == "holder_only":
            return aud == rec.holder
        if vis == "faction_internal":
            if rec.holder.kind == "faction":
                if aud == rec.holder:
                    return True
                aff = self._affiliations.get(aud.id, {})
                return aff.get("faction_id") == rec.holder.id and aff.get("stance_towards_leadership", "loyal") not in ("rebellious", "dissident")
            if aud == rec.holder:
                return True
            aff_aud = self._affiliations.get(aud.id, {})
            aff_rec = self._affiliations.get(rec.holder.id, {})
            f1, f2 = aff_aud.get("faction_id"), aff_rec.get("faction_id")
            return bool(f1 and f1 == f2 and aff_aud.get("stance_towards_leadership", "loyal") not in ("rebellious", "dissident"))
        if vis == "subgroup_only":
            if rec.holder.kind == "subgroup":
                if aud == rec.holder:
                    return True
                aff = self._affiliations.get(aud.id, {})
                return aff.get("subgroup_id") == rec.holder.id
            if aud == rec.holder:
                return True
            s1 = self._affiliations.get(aud.id, {}).get("subgroup_id")
            s2 = self._affiliations.get(rec.holder.id, {}).get("subgroup_id")
            return bool(s1 and s1 == s2)
        return aud == rec.holder

    def query_claim(
        self,
        claim_id: str,
        target_holder: Optional[HolderRef] = None,
    ) -> ClaimQueryResult:
        """Consulta o estado epistêmico de uma claim sob a ótica do holder e da audience."""
        h = target_holder or self._holder
        aud = self._audience or h

        all_for_claim = [r for r in self._records.values() if r.claim_id == claim_id]

        if not all_for_claim:
            if claim_id in self._registered_claims:
                return ClaimQueryResult(claim_id=claim_id, availability="unknown", reason="Alegação desconhecida pelo holder")
            return ClaimQueryResult(claim_id=claim_id, availability="inexistent", reason="Alegação inexiste no repositório")

        if h is None:
            first_known = next((r for r in all_for_claim if r.awareness == "known" and self._is_accessible(r, aud)), None)
            if first_known:
                return ClaimQueryResult(
                    claim_id=claim_id, availability="known", record=first_known,
                    effective_stance=first_known.stance, effective_confidence=first_known.confidence,
                )
            if any(r.visibility == "player_meta" for r in all_for_claim) and (not aud or aud.kind not in ("player", "human")):
                return ClaimQueryResult(claim_id=claim_id, availability="unavailable", reason="player_meta restrito")
            return ClaimQueryResult(claim_id=claim_id, availability="unavailable" if any(r.visibility == "holder_only" for r in all_for_claim) else "unknown", reason="Sem holder especificado")

        rec = next((r for r in all_for_claim if r.holder == h), None)

        # Herança coletiva de facção ou subgrupo
        if rec is None and h.kind == "npc":
            aff = self._affiliations.get(h.id, {})
            fac_id = aff.get("faction_id")
            sub_id = aff.get("subgroup_id")
            sub_stance = aff.get("stance_towards_leadership", "loyal")

            if sub_id:
                sub_h = HolderRef("subgroup", sub_id)
                rec = next((r for r in all_for_claim if r.holder == sub_h and r.visibility in ("public", "faction_internal", "subgroup_only")), None)

            if rec is None and fac_id and sub_stance not in ("rebellious", "dissident"):
                fac_h = HolderRef("faction", fac_id)
                rec = next((r for r in all_for_claim if r.holder == fac_h and r.visibility in ("public", "faction_internal")), None)

        if rec is None:
            # Se o holder não possui o registro, verifica se é player_meta sem versão pública
            if any(r.visibility == "player_meta" for r in all_for_claim) and not any(r.visibility == "public" for r in all_for_claim):
                if not aud or aud.kind not in ("player", "human"):
                    return ClaimQueryResult(claim_id=claim_id, availability="unavailable", reason="player_meta restrito")
            return ClaimQueryResult(claim_id=claim_id, availability="unknown", reason="Holder não tomou conhecimento")

        if not self._is_accessible(rec, aud):
            return ClaimQueryResult(claim_id=claim_id, availability="unavailable", record=rec, reason="Escopo restrito")

        if rec.awareness == "unknown":
            return ClaimQueryResult(claim_id=claim_id, availability="unknown", record=rec)

        return ClaimQueryResult(
            claim_id=claim_id,
            availability="known",
            record=rec,
            effective_stance=rec.stance,
            effective_confidence=rec.confidence,
        )

    def is_claim_known(self, claim_id: str, target_holder: Optional[HolderRef] = None) -> bool:
        res = self.query_claim(claim_id, target_holder)
        return res.availability == "known"

    def is_claim_believed(
        self,
        holder: Optional[HolderRef] = None,
        claim_id: str = "",
        include_collective: bool = True,
    ) -> bool:
        h = None if isinstance(holder, str) else holder
        cid = holder if isinstance(holder, str) else claim_id
        res = self.query_claim(cid, h)
        if res.availability != "known" or res.record is None:
            return False
        return res.effective_stance == "believed" and res.record.status in ("current", "contested")

    def get_beliefs_of(
        self,
        holder: HolderRef,
        include_collective: bool = True,
        audience: Optional[HolderRef] = None,
    ) -> List[KnowledgeRecord]:
        aud = audience or self._audience or holder
        results: List[KnowledgeRecord] = []
        seen_claims: Set[str] = set()

        for rec in self._records.values():
            if rec.holder == holder and rec.awareness != "unknown":
                if self._is_accessible(rec, aud):
                    results.append(rec)
                    seen_claims.add(rec.claim_id)

        if include_collective and holder.kind == "npc":
            aff = self._affiliations.get(holder.id, {})
            fac_id = aff.get("faction_id")
            sub_id = aff.get("subgroup_id")
            sub_stance = aff.get("stance_towards_leadership", "loyal")

            if fac_id and sub_stance not in ("rebellious", "dissident"):
                fac_holder = HolderRef(kind="faction", id=fac_id)
                for rec in self._records.values():
                    if rec.holder == fac_holder and rec.claim_id not in seen_claims:
                        if rec.awareness != "unknown" and self._is_accessible(rec, aud):
                            results.append(rec)
                            seen_claims.add(rec.claim_id)

            if sub_id:
                sub_holder = HolderRef(kind="subgroup", id=sub_id)
                for rec in self._records.values():
                    if rec.holder == sub_holder and rec.claim_id not in seen_claims:
                        if rec.awareness != "unknown" and self._is_accessible(rec, aud):
                            results.append(rec)
                            seen_claims.add(rec.claim_id)

        return results

    def query_by_claim(self, claim_id: str) -> List[KnowledgeRecord]:
        return [r for r in self._records.values() if r.claim_id == claim_id]


class DefaultKnowledgeProvider(KnowledgeProvider):
    """Implementação canônica de KnowledgeProvider com views contextualizadas."""
    name: str = "default_knowledge_provider"

    def __init__(self, view: Optional[KnowledgeView] = None) -> None:
        self._view = view

    def set_view(self, view: KnowledgeView) -> None:
        self._view = view

    def is_believed(self, holder: HolderRef, claim_id: str) -> bool:
        return self._view.is_claim_believed(holder, claim_id) if self._view else False

    def is_known(self, holder: HolderRef, claim_id: str) -> bool:
        return self._view.is_claim_known(claim_id, target_holder=holder) if self._view else False

    def get_beliefs(self, holder: HolderRef) -> List[KnowledgeRecord]:
        return self._view.get_beliefs_of(holder) if self._view else []

    def build_view(
        self,
        events: Sequence[Any],
        holder_kind: str,
        holder_id: str,
        audience_kind: str = "self",
        audience_id: str = "",
        purpose: str = "decision",
        npc_affiliations: Optional[Dict[str, Dict[str, str]]] = None,
        current_time_sort: Optional[int] = None,
        claim_validity_map: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeView:
        from resources.knowledge.service import project_knowledge_state
        records = project_knowledge_state(
            events,
            current_time_sort=current_time_sort,
            claim_validity_map=claim_validity_map,
        )
        h = HolderRef(holder_kind, holder_id)
        aud = HolderRef(holder_kind, holder_id) if audience_kind == "self" else HolderRef(audience_kind, audience_id or holder_id)
        view = KnowledgeView(
            records=records,
            holder=h,
            audience=aud,
            purpose=purpose,
            npc_affiliations=npc_affiliations,
        )
        self._view = view
        return view


__all__ = [
    "VALID_AVAILABILITIES",
    "ClaimQueryResult",
    "KnowledgeView",
    "DefaultKnowledgeProvider",
]
