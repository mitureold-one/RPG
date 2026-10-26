"""Serviço de consulta sob demanda ao estado e alegações (ContextQueryService)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from contracts.context import ContextQueryResult, HolderRef
from contracts.ports import EventStore
from application.context.state import ContextStateViewImpl
from resources.knowledge.model import KnowledgeRecord
from resources.knowledge.view import KnowledgeView


class ContextQueryService:
    """Permite consultas pontuais ao estado persistente respeitando visibilidade epistêmica."""

    def __init__(
        self,
        campaign_id: str,
        campaign_dir: Path | str,
        audience: HolderRef | None = None,
        purpose: str = "query",
        store: EventStore | None = None,
    ) -> None:
        self.campaign_id = campaign_id
        self.campaign_dir = Path(campaign_dir)
        aud = audience or HolderRef("player", "gm")
        if aud.kind == "protagonist" and aud.id in ("protagonist", ""):
            ficha_path = self.campaign_dir / "ficha.md"
            if ficha_path.exists():
                try:
                    import re
                    text = ficha_path.read_text(encoding="utf-8")
                    m = re.search(r"\*\s*\*\*Nome:\*\*\s*([^\n\r*]+)", text)
                    if m:
                        aud = HolderRef("protagonist", m.group(1).strip())
                except Exception:
                    pass
        self.audience = aud
        self.purpose = purpose
        self.state = ContextStateViewImpl.load(
            campaign_id=campaign_id,
            campaign_dir=self.campaign_dir,
            store=store,
        )

    def claim(self, claim_id: str) -> ContextQueryResult:
        records_map: dict[str, KnowledgeRecord] = {}
        for item in self.state.knowledge():
            if isinstance(item, KnowledgeRecord):
                records_map[item.record_id] = item
            elif isinstance(item, dict) and "record_id" in item:
                from application.context.knowledge import _dict_to_knowledge_record
                rec = _dict_to_knowledge_record(item)
                if rec is not None:
                    records_map[rec.record_id] = rec

        target_holder = self.audience if self.audience.kind == "protagonist" else None
        view = KnowledgeView(
            records=records_map,
            holder=target_holder,
            audience=self.audience,
            purpose=self.purpose,
            registered_claims=set(self.state.registered_claims()),
        )
        res = view.query_claim(claim_id, target_holder=target_holder)
        if res.availability == "known" and res.record is not None:
            payload = {
                "claim_id": claim_id,
                "stance": res.effective_stance or res.record.stance,
                "confidence": res.effective_confidence or res.record.confidence,
                "visibility": res.record.visibility,
                "holder": {"kind": res.record.holder.kind, "id": res.record.holder.id},
            }
            return ContextQueryResult(
                kind="claim",
                id=claim_id,
                availability="known",
                payload=payload,
                sources=(res.record.record_id,),
            )
        return ContextQueryResult(
            kind="claim",
            id=claim_id,
            availability=res.availability,
            reason=res.reason or "Alegação não conhecida ou inacessível",
        )

    def npc(self, npc_id: str) -> ContextQueryResult:
        nid_low = npc_id.lower().strip()
        for k, v in self.state.npcs().items():
            if k.lower() == nid_low or str(v.get("name", "")).lower() == nid_low:
                return ContextQueryResult(
                    kind="npc",
                    id=k,
                    availability="known",
                    payload=dict(v),
                    sources=(f"npc:{k}",),
                )
        npcs_md_path = self.campaign_dir / "npcs.md"
        if npcs_md_path.exists():
            try:
                from council import parse_npcs_md

                for n in parse_npcs_md(npcs_md_path):
                    if str(n.get("name", "")).lower() == nid_low:
                        return ContextQueryResult(
                            kind="npc",
                            id=str(n.get("name")),
                            availability="known",
                            payload=dict(n),
                            sources=(f"npc:{n.get('name')}",),
                        )
            except Exception:
                pass
        return ContextQueryResult(
            kind="npc",
            id=npc_id,
            availability="inexistent",
            reason=f"NPC '{npc_id}' não encontrado no estado da campanha",
        )

    def faction(self, tag: str) -> ContextQueryResult:
        t_low = tag.lower().strip()
        for k, v in self.state.factions().items():
            if k.lower() == t_low or str(v.get("name", "")).lower() == t_low:
                return ContextQueryResult(
                    kind="faction",
                    id=k,
                    availability="known",
                    payload=dict(v),
                    sources=(f"faction:{k}",),
                )
        mundo_path = self.campaign_dir / "mundo.md"
        if mundo_path.exists():
            try:
                from council.factions import parse_factions_from_mundo

                for f in parse_factions_from_mundo(mundo_path):
                    if f.get("tag", "").lower() == t_low or f.get("name", "").lower() == t_low:
                        return ContextQueryResult(
                            kind="faction",
                            id=f.get("tag", tag),
                            availability="known",
                            payload=dict(f),
                            sources=(f"faction:{f.get('tag')}",),
                        )
            except Exception:
                pass
        return ContextQueryResult(
            kind="faction",
            id=tag,
            availability="inexistent",
            reason=f"Facção '{tag}' não encontrada no estado da campanha",
        )

    def quest(self, quest_id: str) -> ContextQueryResult:
        qid_low = quest_id.lower().strip()
        for q in self.state.quests():
            cur_id = str(getattr(q, "id", "") if hasattr(q, "id") else q.get("id", ""))
            cur_title = str(getattr(q, "title", "") if hasattr(q, "title") else q.get("title", ""))
            if cur_id.lower() == qid_low or cur_title.lower() == qid_low:
                payload = q if isinstance(q, dict) else dict(getattr(q, "__dict__", {}))
                return ContextQueryResult(
                    kind="quest",
                    id=cur_id,
                    availability="known",
                    payload=payload,
                    sources=(f"quest:{cur_id}",),
                )
        return ContextQueryResult(
            kind="quest",
            id=quest_id,
            availability="inexistent",
            reason=f"Missão '{quest_id}' não encontrada no estado da campanha",
        )

    def clock(self, name: str) -> ContextQueryResult:
        c_low = name.lower().strip()
        for clk in self.state.clocks():
            cur_name = str(getattr(clk, "name", "") if hasattr(clk, "name") else clk.get("name", ""))
            if cur_name.lower() == c_low:
                payload = clk if isinstance(clk, dict) else dict(getattr(clk, "__dict__", {}))
                return ContextQueryResult(
                    kind="clock",
                    id=cur_name,
                    availability="known",
                    payload=payload,
                    sources=(f"clock:{cur_name}",),
                )
        return ContextQueryResult(
            kind="clock",
            id=name,
            availability="inexistent",
            reason=f"Relógio '{name}' não encontrado no estado da campanha",
        )

    def query(self, kind: str, entity_id: str) -> ContextQueryResult:
        k = kind.lower().strip()
        if k == "claim":
            return self.claim(entity_id)
        if k == "npc":
            return self.npc(entity_id)
        if k == "faction":
            return self.faction(entity_id)
        if k == "quest":
            return self.quest(entity_id)
        if k == "clock":
            return self.clock(entity_id)
        return ContextQueryResult(
            kind=kind,
            id=entity_id,
            availability="inexistent",
            reason=f"Tipo de consulta desconhecido: '{kind}'",
        )


__all__ = ["ContextQueryService"]
