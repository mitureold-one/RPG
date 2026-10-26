"""resources/knowledge/model.py: Entidades canônicas do Contrato Epistêmico (Gate G3).

Define HolderRef, ClaimProposition, Claim, ProvenanceRef e KnowledgeRecord.
Pure stdlib, imutáveis e determinísticos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Tuple, Optional

from contracts.context import HolderRef, VALID_HOLDER_KINDS
VALID_CLAIM_TYPES = {"occurrence", "state", "prediction", "normative", "counterfactual"}
VALID_SOURCE_TYPES = {"event", "npc", "faction", "document", "inference", "system", "player", "protagonist", "subgroup"}
VALID_CHANNELS = {"observation", "testimony", "document", "communication", "inference", "mechanism"}
VALID_AWARENESS = {"known", "unknown"}
VALID_STANCE = {"believed", "disbelieved", "uncertain"}
VALID_RECORD_STATUS = {"current", "outdated", "contested", "refuted"}
VALID_VISIBILITY = {
    "public",
    "holder_only",
    "faction_internal",
    "subgroup_only",
    "protagonist_private",
    "player_meta",
}


@dataclass(frozen=True)
class ClaimProposition:
    """Proposição atômica formal: sujeito - predicado - objeto."""
    subject: str
    predicate: str
    object: str
    scope: str = "global"


@dataclass(frozen=True)
class Claim:
    """Alegação atômica identificada canonicamente por clm_<ulid>."""
    claim_id: str
    proposition: ClaimProposition
    claim_type: str
    valid_from: Optional[int] = None
    valid_to: Optional[int] = None
    source_event_id: Optional[str] = None
    fact_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.claim_id or not self.claim_id.startswith("clm_"):
            raise ValueError(f"claim_id deve iniciar com 'clm_': {self.claim_id}")
        if self.claim_type not in VALID_CLAIM_TYPES:
            raise ValueError(f"claim_type inválido: '{self.claim_type}' (esperado: {VALID_CLAIM_TYPES})")
        if self.valid_from is not None and self.valid_to is not None and self.valid_from > self.valid_to:
            raise ValueError(f"valid_from ({self.valid_from}) não pode ser maior que valid_to ({self.valid_to})")


@dataclass(frozen=True)
class ProvenanceRef:
    """Rastreabilidade de origem e canal de aquisição de uma alegação."""
    source_type: str
    source_id: str
    channel: str
    acquired_at: str
    acquired_at_sort: int
    confidence: int  # 0..10000 (basis points estritos, sem bool)
    derived_from: Tuple[str, ...] = ()
    supports: bool = True

    def __post_init__(self) -> None:
        if self.source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"source_type inválido: '{self.source_type}' (esperado: {VALID_SOURCE_TYPES})")
        if self.channel not in VALID_CHANNELS:
            raise ValueError(f"channel inválido: '{self.channel}' (esperado: {VALID_CHANNELS})")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, int):
            raise ValueError(f"confidence deve ser int estrito (não bool): {self.confidence}")
        if not (0 <= self.confidence <= 10000):
            raise ValueError(f"confidence fora do intervalo 0..10000: {self.confidence}")
        if self.channel == "inference" and not self.derived_from:
            raise ValueError("canal 'inference' exige ao menos uma dependência em derived_from")


@dataclass(frozen=True)
class KnowledgeRecord:
    """Estado epistêmico de um agente em relação a uma alegação."""
    record_id: str
    holder: HolderRef
    claim_id: str
    awareness: str
    stance: str
    confidence: int
    status: str
    provenance: Tuple[ProvenanceRef, ...]
    acquired_at: str
    acquired_at_sort: int
    derived_from: Tuple[str, ...] = ()
    supersedes: Tuple[str, ...] = ()
    visibility: str = "holder_only"
    shared_by: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.record_id or not self.record_id.startswith("knw_"):
            raise ValueError(f"record_id deve iniciar com 'knw_': {self.record_id}")
        if not self.claim_id or not self.claim_id.startswith("clm_"):
            raise ValueError(f"claim_id deve iniciar com 'clm_': {self.claim_id}")
        if self.awareness not in VALID_AWARENESS:
            raise ValueError(f"awareness inválido: '{self.awareness}' (esperado: {VALID_AWARENESS})")
        if self.stance not in VALID_STANCE:
            raise ValueError(f"stance inválido: '{self.stance}' (esperado: {VALID_STANCE})")
        if self.status not in VALID_RECORD_STATUS:
            raise ValueError(f"status inválido: '{self.status}' (esperado: {VALID_RECORD_STATUS})")
        if self.visibility not in VALID_VISIBILITY:
            raise ValueError(f"visibility inválido: '{self.visibility}' (esperado: {VALID_VISIBILITY})")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, int):
            raise ValueError(f"confidence deve ser int estrito: {self.confidence}")
        if not (0 <= self.confidence <= 10000):
            raise ValueError(f"confidence fora do intervalo 0..10000: {self.confidence}")
        # unknown awareness cannot be believed
        if self.awareness == "unknown" and self.stance == "believed":
            raise ValueError("awareness == 'unknown' não pode ter stance == 'believed'")


__all__ = [
    "VALID_HOLDER_KINDS",
    "VALID_CLAIM_TYPES",
    "VALID_SOURCE_TYPES",
    "VALID_CHANNELS",
    "VALID_AWARENESS",
    "VALID_STANCE",
    "VALID_RECORD_STATUS",
    "VALID_VISIBILITY",
    "HolderRef",
    "ClaimProposition",
    "Claim",
    "ProvenanceRef",
    "KnowledgeRecord",
]
