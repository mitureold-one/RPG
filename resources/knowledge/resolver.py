"""resources/knowledge/resolver.py: Resolvedor Determinístico de Verdade Canônica (Gate G3).

Avalia uma alegação em relação à verdade do motor no ponto da linha do tempo:
TRUE, FALSE, UNKNOWN ou INDETERMINATE.
Alinhado a correções canônicas de eventos e sem falsificação indevida de histórico (P1-3).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Literal, Sequence, Set
from contracts.event import Event
from resources.knowledge.model import Claim

TruthValue = Literal["TRUE", "FALSE", "UNKNOWN", "INDETERMINATE"]

NEGATION_MARKERS = frozenset({
    "não", "nao", "not", "nunca", "jamais",
    "impediu", "failed", "falhou", "rejeitou", "evitou",
})


def resolve_claim(
    claim: Claim,
    at_time_sort: int,
    events: Sequence[Any],
    projected_state: Dict[str, Any],
) -> TruthValue:
    """Avalia o valor de verdade determinístico de uma alegação contra os eventos e estado projetado.

    Regras Epistêmicas Canônicas:
    1. Tipos não-empíricos ('normative', 'counterfactual'): sempre 'INDETERMINATE'.
    2. Predições ('prediction'): se at_time_sort anterior ao horizonte da predição, 'INDETERMINATE'.
    3. Causalidade e Correções: se claim.source_event_id aponta para evento anulado em
       'correction.issued' (pelo campo 'corrects'), retorna 'UNKNOWN'.
    4. Janela temporal:
       - Se at_time_sort < claim.valid_from: o fato ainda não ocorreu/estabeleceu ('UNKNOWN').
       - Se claim.claim_type == 'state' e at_time_sort > claim.valid_to: o estado expirou ('FALSE').
       - Se claim.claim_type == 'occurrence': ocorrência no passado permanece 'TRUE' historicamente.
    5. Fact Ref & Projected State: se claim.fact_ref definido, avalia valor no estado projetado.
    """
    # 1. Normativos e contrafactuais não são fatos empíricos
    if claim.claim_type in ("normative", "counterfactual"):
        return "INDETERMINATE"

    # 2. Predições para o futuro
    if claim.claim_type == "prediction":
        target_time = claim.valid_from or claim.valid_to
        if target_time is not None and at_time_sort < target_time:
            return "INDETERMINATE"

    # 3. Janela temporal inicial
    if claim.valid_from is not None and at_time_sort < claim.valid_from:
        return "UNKNOWN"

    # 4. Checagem de correções retroativas no log de eventos
    corrected_event_ids: Set[str] = set()
    for ev in events:
        evt = getattr(ev, "event", ev)
        if evt.type == "correction.issued":
            p = evt.payload or {}
            # O campo canônico do catálogo v1 é 'corrects' (lista de event_ids)
            for eid in p.get("corrects", ()):
                corrected_event_ids.add(eid)
            # Compatibilidade com variações
            for ch in p.get("changes", ()):
                if isinstance(ch, dict) and "target_event_id" in ch:
                    corrected_event_ids.add(ch["target_event_id"])

    if claim.source_event_id and claim.source_event_id in corrected_event_ids:
        return "UNKNOWN"

    # 5. Avaliação contra fact_ref e projected_state para estados
    if claim.claim_type == "state":
        if claim.fact_ref:
            parts = claim.fact_ref.split(":")
            cur: Any = projected_state
            found = True
            for part in parts:
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    found = False
                    break

            if found:
                expected = claim.proposition.object
                return "TRUE" if str(cur).lower() == str(expected).lower() else "FALSE"

        elif claim.proposition.subject in projected_state:
            cur = projected_state[claim.proposition.subject]
            if isinstance(cur, dict) and claim.proposition.predicate in cur:
                val = cur[claim.proposition.predicate]
                expected = claim.proposition.object
                return "TRUE" if str(val).lower() == str(expected).lower() else "FALSE"

        # Janela temporal expirada para estados quando não há estado vigente contrastante
        if claim.valid_to is not None and at_time_sort > claim.valid_to:
            return "FALSE"

    # 6. Avaliação baseada na ocorrência de eventos canônicos no log
    if claim.claim_type == "occurrence":
        prop = claim.proposition
        pred = prop.predicate.lower()
        matched_event = False
        explicitly_negated = False

        for ev in events:
            evt = getattr(ev, "event", ev)
            if evt.type.startswith(("knowledge.", "proposal.", "campaign.", "projection.")):
                continue
            evt_sort = getattr(evt, "game_time_sort", 0) or 0
            if evt_sort > at_time_sort:
                continue
            evt_id = getattr(evt, "event_id", getattr(evt, "id", ""))
            if evt_id in corrected_event_ids:
                continue

            payload = evt.payload or {}
            subj = str(payload.get("name") or payload.get("actor", "") or payload.get("id") or "").lower()
            evt_text = f"{evt.type} {str(payload)}".lower()

            # Se o sujeito e predicado constam no evento
            if prop.subject.lower() in subj or prop.subject.lower() in evt_text:
                if pred in evt_text:
                    # Antinegação: marcadores de negação imediatamente antes do predicado
                    idx = evt_text.find(pred)
                    window_before = evt_text[max(0, idx - 30):idx]
                    words_before = set(re.findall(r"\w+", window_before))
                    if words_before & NEGATION_MARKERS:
                        if not prop.object or prop.object.lower() in evt_text:
                            explicitly_negated = True
                        continue

                    if not prop.object or prop.object.lower() in evt_text:
                        matched_event = True
                        break

        if matched_event:
            return "TRUE"
        if explicitly_negated:
            return "FALSE"
        return "UNKNOWN"

    return "UNKNOWN"


__all__ = [
    "TruthValue",
    "resolve_claim",
]
