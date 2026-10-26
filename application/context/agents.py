"""Provedores causais de NPCs e facções baseados em relevância causal."""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Mapping, Sequence

from contracts.context import (
    ContextItem,
    ContextOmission,
    ContextRequest,
    ContextSection,
)
from contracts.ports import ContextStateView
from contracts.serialization import canonical_json
from resources.context.relevance import score_faction, score_npc


def _section_hash(items: Sequence[ContextItem], omissions: Sequence[ContextOmission]) -> str:
    payload = {
        "items": [(i.kind, i.id, i.score, i.availability) for i in items],
        "omissions": [(o.kind, o.reference, o.availability) for o in omissions],
    }
    raw = canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()[:16]}"


class NpcCausalProvider:
    """Provedor causal de NPCs relevantes (presentes e distantes)."""

    key = "npc_causal"
    layer = "causal"
    priority = 50

    def __init__(self, all_npcs: Sequence[Mapping[str, Any]] | None = None) -> None:
        self._all_npcs = all_npcs

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        items: list[ContextItem] = []
        omissions: list[ContextOmission] = []

        # Une os NPCs projetados do estado com eventuais NPCs de markdown
        merged_npcs: dict[str, dict[str, Any]] = {}
        for nid, nstate in state.npcs().items():
            if dataclasses.is_dataclass(nstate):
                nd = dataclasses.asdict(nstate)
            elif isinstance(nstate, dict):
                nd = dict(nstate)
            else:
                nd = dict(getattr(nstate, "__dict__", {}))
            merged_npcs[nid.lower()] = nd

        if self._all_npcs is not None:
            for n in self._all_npcs:
                nd = dict(n)
                name = str(nd.get("name") or "").strip()
                nid = str(nd.get("id") or name).strip().lower()
                if nid in merged_npcs:
                    for k, v in nd.items():
                        if k not in merged_npcs[nid] or not merged_npcs[nid][k]:
                            merged_npcs[nid][k] = v
                else:
                    merged_npcs[nid] = nd

        for nid, npc_dict in merged_npcs.items():
            name = str(npc_dict.get("name") or nid).strip()
            score, reasons = score_npc(npc_dict, request, state)

            # Presença não é suficiência (C03): presença física sem nenhum fator causal
            # não promove o NPC a causal.items (permanece em background_cast)
            if set(reasons) <= {"presenca"}:
                continue

            # Só inclui no pool causal se atingir o limiar
            if score >= request.limits.min_relevance:
                payload = {
                    "name": name,
                    "attitude": npc_dict.get("attitude", ""),
                    "location": npc_dict.get("location", ""),
                    "plan": npc_dict.get("plan") or npc_dict.get("active_plan") or {},
                    "relationships": npc_dict.get("relationships", ()),
                    "capabilities": npc_dict.get("capabilities", ()),
                }
                items.append(
                    ContextItem(
                        kind="npc",
                        id=nid,
                        label=name,
                        layer="causal",
                        score=score,
                        reasons=reasons,
                        availability="known",
                        payload=payload,
                    )
                )

        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=tuple(items),
            omissions=tuple(omissions),
            hash=_section_hash(items, omissions),
        )


class FactionCausalProvider:
    """Provedor causal de facções relevantes (locais e distantes)."""

    key = "faction_causal"
    layer = "causal"
    priority = 55

    def __init__(self, all_factions: Sequence[Mapping[str, Any]] | None = None) -> None:
        self._all_factions = all_factions

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        items: list[ContextItem] = []
        omissions: list[ContextOmission] = []

        factions_source = (
            self._all_factions if self._all_factions is not None else list(state.factions().values())
        )

        for fac in factions_source:
            fac_dict = dict(fac)
            tag = str(fac_dict.get("tag") or fac_dict.get("id") or "").strip()
            name = str(fac_dict.get("name") or tag).strip()
            if not tag:
                continue

            score, reasons = score_faction(fac_dict, request, state)

            if score >= request.limits.min_relevance:
                payload = {
                    "tag": tag,
                    "name": name,
                    "power": fac_dict.get("power", 0),
                    "cohesion": fac_dict.get("cohesion", 0),
                    "territory": fac_dict.get("territory", ""),
                    "clock": fac_dict.get("clock", ""),
                    "leadership": fac_dict.get("leadership", {}),
                }
                items.append(
                    ContextItem(
                        kind="faction",
                        id=tag,
                        label=f"{name} ({tag})",
                        layer="causal",
                        score=score,
                        reasons=reasons,
                        availability="known",
                        payload=payload,
                    )
                )

        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=tuple(items),
            omissions=tuple(omissions),
            hash=_section_hash(items, omissions),
        )


__all__ = ["FactionCausalProvider", "NpcCausalProvider"]
