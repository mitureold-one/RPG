"""resources/admission.py: Validador de Admissão de Intenções de Agentes (Gate G3).

Verifica deterministicamente se uma intenção proposta cumpre os pré-requisitos:
- Epistêmicos: agente tem conhecimento/ciência da alegação (is_known / is_believed).
- Governança: agente possui autoridade de liderança caso aja em nome de facção (acts_for_faction).
- Físicos: ator coincide com a localização necessária e não está incapacitado.
- Capacidades: agente possui os talentos/habilidades exigidos.
- Recursos: agente possui os recursos materiais/financeiros necessários.
Em caso de rejeição, gera o evento canônico 'proposal.rejected' alinhado ao catálogo (AT17).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from contracts.event import ActorRef, EventDraft
from contracts.ports import Intent, KnowledgeProvider
from resources.knowledge.model import HolderRef


def validate_intent_admission(
    intent: Intent,
    knowledge_provider: KnowledgeProvider,
    actor_capabilities: Sequence[str] = (),
    actor_resources: Optional[Dict[str, Any]] = None,
    actor_location: Optional[str] = None,
    actor_condition: Optional[str] = None,
    faction_state: Optional[Any] = None,
    is_leader: bool = False,
) -> Tuple[bool, List[str]]:
    """Valida se uma intenção proposta por um agente é admissível para resolução.

    Critérios de Validação Determinística:
    1. EPISTEMIC_UNSATISFIED: Ator desconhece a claim (sem awareness/crença requerida).
    2. UNAUTHORIZED_FACTION_LEADERSHIP: Ator declara agir pela facção sem autoridade de liderança.
    3. ACTOR_INCAPACITATED / LOCATION_MISMATCH: Ator não cumpre requisitos físicos/condição.
    4. CAPABILITY_MISSING: Ator não possui alguma das capacidades requeridas.
    5. INSUFFICIENT_RESOURCES: Ator não possui saldo/recursos suficientes.
    """
    errors: List[str] = []
    holder = HolderRef(kind=intent.actor_kind, id=intent.actor_id)

    # 1. Checagem de Pré-requisitos Epistêmicos (AT02: awareness='known' basta para fatos)
    for claim_id in intent.required_claims:
        known = False
        if hasattr(knowledge_provider, "is_known"):
            known = bool(knowledge_provider.is_known(holder, claim_id))
        if not known:
            known = bool(knowledge_provider.is_believed(holder, claim_id))

        if not known:
            errors.append(
                f"EPISTEMIC_UNSATISFIED: Ator '{intent.actor_id}' desconhece a alegação necessária '{claim_id}'"
            )

    # 2. Checagem de Autoridade de Liderança de Facção (P1-4)
    if intent.acts_for_faction:
        has_authority = is_leader
        if not has_authority and faction_state is not None:
            ld = getattr(faction_state, "leadership", None)
            if ld is not None:
                has_authority = (ld.leader_id == intent.actor_id)
        if not has_authority:
            errors.append(
                f"UNAUTHORIZED_FACTION_LEADERSHIP: Ator '{intent.actor_id}' não possui autoridade para agir em nome da facção '{intent.acts_for_faction}'"
            )

    # 3. Checagem de Condição e Localização Física
    if actor_condition in ("incapacitated", "dead", "unconscious", "paralyzed"):
        errors.append(
            f"ACTOR_INCAPACITATED: Ator '{intent.actor_id}' está '{actor_condition}' e não pode executar ações ativas"
        )

    if intent.location is not None and actor_location is not None:
        if intent.location.strip().lower() != actor_location.strip().lower():
            errors.append(
                f"LOCATION_MISMATCH: Ator '{intent.actor_id}' está em '{actor_location}', mas a intenção exige '{intent.location}'"
            )

    # 4. Checagem de Capacidades Requeridas
    caps_set = set(actor_capabilities)
    for cap in intent.required_capabilities:
        if cap not in caps_set:
            errors.append(
                f"CAPABILITY_MISSING: Ator '{intent.actor_id}' carece da capacidade requerida '{cap}'"
            )

    # 5. Checagem de Recursos Requeridos
    res_map = actor_resources or {}
    req_resources = intent.required_resources or {}
    for res_key, required_qty in req_resources.items():
        current_qty = res_map.get(res_key, 0)
        try:
            if int(current_qty) < int(required_qty):
                errors.append(
                    f"INSUFFICIENT_RESOURCES: Ator '{intent.actor_id}' possui {current_qty} de '{res_key}', mas necessita de {required_qty}"
                )
        except (ValueError, TypeError):
            errors.append(
                f"INSUFFICIENT_RESOURCES: Recurso '{res_key}' inválido ou indisponível para o ator"
            )

    return (len(errors) == 0, errors)


def make_proposal_rejected_draft(
    intent: Intent,
    reasons: Sequence[str],
    game_time: str,
    game_time_sort: int,
    payload_summary: Optional[Dict[str, Any]] = None,
    actor: Optional[ActorRef] = None,
) -> EventDraft:
    """Cria um draft canônico de evento proposal.rejected alinhado estritamente ao catálogo v1."""
    act = actor or ActorRef(kind=intent.actor_kind, id=intent.actor_id)
    summary = dict(payload_summary or {})
    summary.setdefault("intent_kind", intent.intent_kind)
    summary.setdefault("description", intent.description)
    if intent.acts_for_faction:
        summary.setdefault("acts_for_faction", intent.acts_for_faction)

    return EventDraft(
        type="proposal.rejected",
        schema_version=1,
        actor=act,
        game_time=game_time,
        game_time_sort=game_time_sort,
        payload={
            "proposal_kind": intent.intent_kind,
            "actor_id": intent.actor_id,
            "reasons": list(reasons),
            "payload_summary": summary,
        },
    )


__all__ = [
    "validate_intent_admission",
    "make_proposal_rejected_draft",
]
