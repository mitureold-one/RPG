"""Projector determinístico para estado derivado em estado.json.

Gera projeção agregada de NPCs, facções, conhecimento e eventos recentes,
com schema_version, last_seq e hash para validação de staleness pelo prepare.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any, Mapping, Sequence

from contracts.ports import EventStreamView, ProjectionSection
from contracts.serialization import canonical_json
from resources.factions.service import project_factions_state
from resources.knowledge.service import project_knowledge_state
from resources.npcs.service import project_npcs_state


def _serialize_dataclass(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [_serialize_dataclass(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize_dataclass(v) for k, v in obj.items()}
    return obj


class StateProjector:
    """Projeta o cache de estado consolidado em estado.json."""

    file = "estado.json"
    section = "body"
    order = 50

    def __init__(self, initial_text: str | None = None) -> None:
        self.initial_text = initial_text

    def project(self, view: EventStreamView) -> ProjectionSection:
        # Filtra eventos técnicos de projeção para garantir determinismo de rebuild C3
        domain_events = [e for e in view.events if not e.type.startswith("projection.")]

        base_npcs: dict[str, Any] = {}
        base_factions: dict[str, Any] = {}
        base_knowledge: dict[str, Any] = {}
        base_recent: list[dict[str, Any]] = []
        base_last_seq = 0

        if self.initial_text:
            try:
                base_data = json.loads(self.initial_text)
                base_last_seq = int(base_data.get("last_seq", 0))
                for n in base_data.get("npcs", []):
                    nid = n.get("id") or n.get("name")
                    if nid:
                        base_npcs[str(nid)] = n
                for f in base_data.get("factions", []):
                    tag = f.get("tag") or f.get("name")
                    if tag:
                        base_factions[str(tag)] = f
                for k in base_data.get("knowledge", []):
                    rid = k.get("record_id")
                    if rid:
                        base_knowledge[str(rid)] = k
                base_recent = list(base_data.get("recent_events", []))
            except Exception:
                pass

        # Projeta entidades e conhecimento a partir dos eventos desta visão
        delta_npcs = project_npcs_state(domain_events)
        delta_factions = project_factions_state(domain_events)
        delta_knowledge = project_knowledge_state(domain_events)

        # Mescla com baseline
        for k, v in delta_npcs.items():
            base_npcs[k] = _serialize_dataclass(v)
        for k, v in delta_factions.items():
            base_factions[k] = _serialize_dataclass(v)
        dk_items = (
            delta_knowledge.items()
            if isinstance(delta_knowledge, dict)
            else {getattr(x, "record_id", ""): x for x in delta_knowledge}.items()
        )
        for k, v in dk_items:
            if k:
                base_knowledge[k] = _serialize_dataclass(v)

        npcs_list = [base_npcs[k] for k in sorted(base_npcs.keys())]
        factions_list = [base_factions[k] for k in sorted(base_factions.keys())]
        knowledge_list = [base_knowledge[k] for k in sorted(base_knowledge.keys())]

        # Resumo dos eventos recentes
        new_recent: list[dict[str, Any]] = []
        for ev in domain_events:
            p = ev.payload or {}
            summary = p.get("summary") or p.get("action") or ev.type
            refs: list[str] = list(p.get("refs") or [])
            for key in ("npc_id", "target_npc", "actor_id"):
                if key in p and p[key]:
                    refs.append(f"npc:{p[key]}")
            for key in ("faction", "faction_tag", "tag"):
                if key in p and p[key]:
                    refs.append(f"faction:{p[key]}")
            if "claim_id" in p and p["claim_id"]:
                refs.append(f"claim:{p['claim_id']}")

            new_recent.append(
                {
                    "seq": ev.seq,
                    "event_id": getattr(ev, "event_id", "") or getattr(ev, "id", "") or f"evt_{ev.seq}",
                    "type": ev.type,
                    "game_time": getattr(ev, "game_time", ""),
                    "game_time_sort": getattr(ev, "game_time_sort", 0),
                    "actor": {"kind": ev.actor.kind, "id": ev.actor.id},
                    "summary": str(summary),
                    "refs": sorted(set(refs)),
                    "payload": p,
                }
            )

        combined_recent = (base_recent + new_recent)[-50:]
        last_seq = (
            domain_events[-1].seq
            if domain_events
            else (base_last_seq or 0)
        )

        payload_to_hash = {
            "schema_version": 1,
            "last_seq": last_seq,
            "npcs": npcs_list,
            "factions": factions_list,
            "knowledge": knowledge_list,
            "recent_events": combined_recent,
        }
        raw_canonical = canonical_json(payload_to_hash).encode("utf-8")
        hash_hex = hashlib.sha256(raw_canonical).hexdigest()

        final_data = {
            "schema_version": 1,
            "last_seq": last_seq,
            "hash": f"sha256:{hash_hex}",
            "npcs": npcs_list,
            "factions": factions_list,
            "knowledge": knowledge_list,
            "recent_events": combined_recent,
        }

        content = canonical_json(final_data) + "\n"
        return ProjectionSection(file=self.file, section=self.section, content=content)


__all__ = ["StateProjector"]
