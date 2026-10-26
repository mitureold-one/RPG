"""Provedores padrão de núcleo obrigatório e de estrutura causal.

Implementam o protocolo ContextProvider para ruleset, protagonista, cena,
missões e relógios.
"""

from __future__ import annotations

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


def _section_hash(items: Sequence[ContextItem], omissions: Sequence[ContextOmission]) -> str:
    payload = {
        "items": [(i.kind, i.id, i.score, i.availability) for i in items],
        "omissions": [(o.kind, o.reference, o.availability) for o in omissions],
    }
    raw = canonical_json(payload).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()[:16]}"


class RulesetCoreProvider:
    """Provedor de regras, sistema e restrições do núcleo obrigatório."""

    key = "ruleset_core"
    layer = "core"
    priority = 10

    def __init__(self, ruleset: Any = None, system_name: str = "") -> None:
        self._ruleset = ruleset
        self._system_name = system_name

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        sys_name = self._system_name or getattr(self._ruleset, "name", "d20_dirty")
        payload = {
            "system": sys_name,
            "dc_ladder": getattr(self._ruleset, "dc_ladder", {}),
            "tier_names": getattr(self._ruleset, "tier_names", ()),
        }
        item = ContextItem(
            kind="ruleset",
            id=sys_name,
            label=f"Sistema de Regras ({sys_name})",
            layer="core",
            score=1000,
            reasons=("regra_obrigatoria",),
            availability="known",
            payload=payload,
        )
        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=(item,),
            omissions=(),
            hash=_section_hash((item,), ()),
        )


class ProtagonistCoreProvider:
    """Provedor do estado mecânico do protagonista (ficha, vitais, atributos)."""

    key = "protagonist_core"
    layer = "core"
    priority = 20

    def __init__(self, ficha: Mapping[str, Any] | None = None) -> None:
        self._ficha = dict(ficha or {})

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        protagonist_name = self._ficha.get("name", "Protagonista")
        payload = {
            "name": protagonist_name,
            "vitals": self._ficha.get("vitals", {}),
            "stats": self._ficha.get("stats", {}),
            "progression": self._ficha.get("progression", {}),
        }
        item = ContextItem(
            kind="protagonist",
            id=protagonist_name,
            label=f"Protagonista ({protagonist_name})",
            layer="core",
            score=1000,
            reasons=("protagonista_obrigatorio",),
            availability="known",
            payload=payload,
        )
        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=(item,),
            omissions=(),
            hash=_section_hash((item,), ()),
        )


class SceneCoreProvider:
    """Provedor espaciotemporal da cena e arco ativo."""

    key = "scene_core"
    layer = "core"
    priority = 30

    def __init__(self, diario: Mapping[str, Any] | None = None) -> None:
        self._diario = dict(diario or {})

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        payload = {
            "location": request.scene.location,
            "game_time": request.scene.game_time,
            "game_time_sort": request.scene.game_time_sort,
            "present": request.scene.present,
            "scene_type": request.scene.scene_type,
            "arc": state.arc(),
        }
        item = ContextItem(
            kind="scene",
            id=f"scene_{request.scene.game_time_sort}",
            label=f"Cena em {request.scene.location}",
            layer="core",
            score=1000,
            reasons=("cena_obrigatoria",),
            availability="known",
            payload=payload,
        )
        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=(item,),
            omissions=(),
            hash=_section_hash((item,), ()),
        )


class QuestCausalProvider:
    """Provedor causal de missões ativas e objetivos pendentes."""

    key = "quest_causal"
    layer = "causal"
    priority = 40

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        items: list[ContextItem] = []
        quests = state.quests()
        for q in quests:
            q_id = getattr(q, "id", "") if hasattr(q, "id") else q.get("id", "")
            q_title = getattr(q, "title", q_id) if hasattr(q, "title") else q.get("title", q_id)
            q_status = getattr(q, "status", "active") if hasattr(q, "status") else q.get("status", "active")
            if q_status in ("active", "ACTIVE"):
                contractor = getattr(q, "contractor", "") if hasattr(q, "contractor") else q.get("contractor", "")
                target = getattr(q, "target", "") if hasattr(q, "target") else q.get("target", "")
                reasons = ["missao_ativa"]
                score = 250
                # Bônus de foco se citada na ação ou foco
                if q_id.lower() in request.action.lower() or q_title.lower() in request.action.lower():
                    score += 500
                    reasons.append("foco_explicito")

                payload = {
                    "title": q_title,
                    "status": q_status,
                    "contractor": contractor,
                    "target": target,
                    "objectives": getattr(q, "objectives", ()) if hasattr(q, "objectives") else q.get("objectives", ()),
                }
                items.append(
                    ContextItem(
                        kind="quest",
                        id=q_id,
                        label=f"Missão: {q_title}",
                        layer="causal",
                        score=score,
                        reasons=tuple(reasons),
                        availability="known",
                        payload=payload,
                    )
                )

        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=tuple(items),
            omissions=(),
            hash=_section_hash(items, ()),
        )


class ClockCausalProvider:
    """Provedor causal de relógios de tensão ativos e críticos."""

    key = "clock_causal"
    layer = "causal"
    priority = 45

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        items: list[ContextItem] = []
        clocks = state.clocks()
        for clk in clocks:
            name = getattr(clk, "name", "") if hasattr(clk, "name") else clk.get("name", "")
            cur = getattr(clk, "current", 0) if hasattr(clk, "current") else clk.get("current", 0)
            mx = getattr(clk, "max", 4) if hasattr(clk, "max") else clk.get("max", 4)
            status = getattr(clk, "status", "ACTIVE") if hasattr(clk, "status") else clk.get("status", "ACTIVE")

            if status in ("ACTIVE", "active"):
                is_critical = cur >= max(1, mx - 1)
                score = 300 if is_critical else 150
                reasons = ["relogio_critico"] if is_critical else ["relogio_ativo"]
                if name.lower() in request.action.lower():
                    score += 500
                    reasons.append("foco_explicito")

                payload = {
                    "name": name,
                    "current": cur,
                    "max": mx,
                    "status": status,
                    "is_critical": is_critical,
                }
                items.append(
                    ContextItem(
                        kind="clock",
                        id=name,
                        label=f"Relógio: {name} ({cur}/{mx})",
                        layer="causal",
                        score=score,
                        reasons=tuple(reasons),
                        availability="known",
                        payload=payload,
                    )
                )

        return ContextSection(
            key=self.key,
            layer=self.layer,
            items=tuple(items),
            omissions=(),
            hash=_section_hash(items, ()),
        )


def default_context_providers(
    ruleset: Any = None,
    system_name: str = "",
    ficha: Mapping[str, Any] | None = None,
    diario: Mapping[str, Any] | None = None,
    all_npcs: Sequence[Mapping[str, Any]] | None = None,
) -> list[ContextProvider]:
    """Retorna a suíte padrão dos 9 provedores modulares de contexto."""
    from application.context.agents import FactionCausalProvider, NpcCausalProvider
    from application.context.knowledge import FactsCausalProvider, KnowledgeCausalProvider

    return [
        RulesetCoreProvider(ruleset=ruleset, system_name=system_name),
        ProtagonistCoreProvider(ficha=ficha),
        SceneCoreProvider(diario=diario),
        QuestCausalProvider(),
        ClockCausalProvider(),
        NpcCausalProvider(all_npcs=all_npcs),
        FactionCausalProvider(),
        KnowledgeCausalProvider(),
        FactsCausalProvider(),
    ]


__all__ = [
    "ClockCausalProvider",
    "ProtagonistCoreProvider",
    "QuestCausalProvider",
    "RulesetCoreProvider",
    "SceneCoreProvider",
    "default_context_providers",
]
