"""Montador central e determinístico de camadas de contexto para o prepare."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping, Sequence

from contracts.context import (
    ContextItem,
    ContextOmission,
    ContextQueryHandles,
    ContextRequest,
    ContextSection,
    TurnContext,
)
from contracts.ports import ContextProvider, ContextStateView
from contracts.serialization import canonical_json
from resources.context.relevance import select


def _section_hash(items: Sequence[ContextItem], omissions: Sequence[ContextOmission]) -> str:
    payload = {
        "items": [(i.kind, i.id, i.score, i.availability) for i in items],
        "omissions": [(o.kind, o.reference, o.availability) for o in omissions],
    }
    raw = canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()[:16]}"


class ContextAssembler:
    """Orquestra a execução dos provedores e compõe o TurnContext determinístico."""

    def __init__(self, providers: Sequence[ContextProvider]) -> None:
        self.providers = sorted(providers, key=lambda p: (p.priority, p.key))

    def assemble(self, request: ContextRequest, state: ContextStateView) -> TurnContext:
        core_items: list[ContextItem] = []
        causal_candidates: list[ContextItem] = []
        collected_omissions: list[ContextOmission] = []
        executed_provider_keys: list[str] = []

        # 1. Executa provedores registrados ordenados por prioridade
        for p in self.providers:
            executed_provider_keys.append(p.key)
            sec = p.provide(request, state)
            for item in sec.items:
                if item.layer == "core":
                    core_items.append(item)
                else:
                    causal_candidates.append(item)
            collected_omissions.extend(sec.omissions)

        # 2. Detecta referências explícitas na ação sem correspondência no estado (omissões inexistent)
        known_npcs = {k.lower() for k in state.npcs()}
        known_factions = {k.lower() for k in state.factions()}

        # Busca por padrões de IDs explícitos como npc_*, fac_* ou clm_*
        mentioned_tokens = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", f"{request.action} {' '.join(request.focus)}")
        for tok in set(mentioned_tokens):
            tok_low = tok.lower()
            if tok_low.startswith("clm_"):
                # Se não gerou item nem omissão de conhecimento, é inexistent
                if not any(i.id == tok for i in causal_candidates) and not any(o.reference == tok for o in collected_omissions):
                    collected_omissions.append(
                        ContextOmission(
                            kind="claim",
                            reference=tok,
                            availability="inexistent",
                            reason="Alegação inexistente no estado persistente",
                        )
                    )
            elif tok_low.startswith("npc_") and tok_low not in known_npcs:
                collected_omissions.append(
                    ContextOmission(
                        kind="npc",
                        reference=tok,
                        availability="inexistent",
                        reason="NPC inexistente no estado persistente",
                    )
                )
            elif tok_low.startswith("fac_") and tok_low not in known_factions:
                collected_omissions.append(
                    ContextOmission(
                        kind="faction",
                        reference=tok,
                        availability="inexistent",
                        reason="Facção inexistente no estado persistente",
                    )
                )

        # 3. Aplica filtro de relevância e limites na camada causal
        selected_causal = select(causal_candidates, request.limits)
        selected_ids = {i.id for i in selected_causal}

        # Itens descartados por limite geram omissão informando descarte
        for cand in causal_candidates:
            if cand.id not in selected_ids and cand.score >= request.limits.min_relevance:
                collected_omissions.append(
                    ContextOmission(
                        kind=cand.kind,
                        reference=cand.id,
                        availability="unavailable",
                        reason=f"Descartado pelo limite da camada causal (score={cand.score})",
                    )
                )

        # 4. Ordena omissões de forma determinística
        sorted_omissions = tuple(
            sorted(collected_omissions, key=lambda o: (o.kind, o.reference, o.availability))
        )

        # 5. Constrói seções e hashes canônicos
        core_sec = ContextSection(
            key="core",
            layer="core",
            items=tuple(core_items),
            omissions=(),
            hash=_section_hash(core_items, ()),
        )
        causal_sec = ContextSection(
            key="causal",
            layer="causal",
            items=tuple(selected_causal),
            omissions=(),
            hash=_section_hash(selected_causal, ()),
        )

        query_handles = ContextQueryHandles(
            holder=request.viewer,
            audience=request.audience,
            purpose=request.purpose,
            entities={
                "npc": tuple(sorted(state.npcs().keys())),
                "faction": tuple(sorted(state.factions().keys())),
                "quest": tuple(sorted(getattr(q, "id", "") if hasattr(q, "id") else q.get("id", "") for q in state.quests() if (hasattr(q, "id") or "id" in q))),
                "clock": tuple(sorted(getattr(c, "name", "") if hasattr(c, "name") else c.get("name", "") for c in state.clocks() if (hasattr(c, "name") or "name" in c))),
            },
            commands=(
                "query claim <id>",
                "query npc <id>",
                "query faction <id>",
                "query quest <id>",
                "query clock <id>",
            ),
        )

        # 6. Calcula o context_hash determinístico SHA-256
        hash_payload = {
            "version": 1,
            "audience": f"{request.audience.kind}:{request.audience.id}",
            "purpose": request.purpose,
            "source_last_seq": state.last_seq,
            "core_hash": core_sec.hash,
            "causal_hash": causal_sec.hash,
            "omissions": [(o.kind, o.reference, o.availability) for o in sorted_omissions],
        }
        raw_hash_data = canonical_json(hash_payload).encode("utf-8")
        context_hash = f"sha256:{hashlib.sha256(raw_hash_data).hexdigest()}"

        return TurnContext(
            version=1,
            request=request,
            core=core_sec,
            causal=causal_sec,
            query=query_handles,
            omissions=sorted_omissions,
            source_last_seq=state.last_seq,
            context_hash=context_hash,
            stale=state.stale,
            providers=tuple(executed_provider_keys),
        )


def turn_context_to_payload(tc: TurnContext) -> dict[str, Any]:
    """Converte TurnContext em estrutura de dicionários serializáveis para o prepare."""
    return {
        "context_version": tc.version,
        "source_last_seq": tc.source_last_seq,
        "context": {
            "version": tc.version,
            "audience": f"{tc.request.audience.kind}:{tc.request.audience.id}",
            "purpose": tc.request.purpose,
            "source_last_seq": tc.source_last_seq,
            "context_hash": tc.context_hash,
            "stale": tc.stale,
            "providers": list(tc.providers),
            "core": {
                "items": [
                    {
                        "kind": i.kind,
                        "id": i.id,
                        "label": i.label,
                        "layer": i.layer,
                        "score": i.score,
                        "reasons": list(i.reasons),
                        "availability": i.availability,
                        "payload": dict(i.payload),
                    }
                    for i in tc.core.items
                ],
                "hash": tc.core.hash,
            },
            "causal": {
                "items": [
                    {
                        "kind": i.kind,
                        "id": i.id,
                        "label": i.label,
                        "layer": i.layer,
                        "score": i.score,
                        "reasons": list(i.reasons),
                        "availability": i.availability,
                        "payload": dict(i.payload),
                    }
                    for i in tc.causal.items
                ],
                "hash": tc.causal.hash,
            },
            "query": {
                "holder": {"kind": tc.query.holder.kind, "id": tc.query.holder.id},
                "audience": {"kind": tc.query.audience.kind, "id": tc.query.audience.id},
                "purpose": tc.query.purpose,
                "entities": {k: list(v) for k, v in tc.query.entities.items()},
                "commands": list(tc.query.commands),
            },
        },
        "context_omissions": [
            {
                "kind": o.kind,
                "reference": o.reference,
                "availability": o.availability,
                "reason": o.reason,
                "sources": list(o.sources),
            }
            for o in tc.omissions
        ],
    }


__all__ = ["ContextAssembler", "turn_context_to_payload"]
