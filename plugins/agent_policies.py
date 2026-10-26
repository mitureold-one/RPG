"""plugins/agent_policies.py: Políticas Padrão de Comportamento e Decisão Estratégica.

Implementa UtilityBehaviorPolicy (BehaviorPolicy) e StrategicFactionPolicy (FactionPolicy).
Determinísticas, puras e desacopladas de I/O.
"""

from __future__ import annotations

from typing import List, Tuple
from contracts.ports import (
    BehaviorPolicy,
    FactionContext,
    FactionPolicy,
    Intent,
    ReactionContext,
)


class UtilityBehaviorPolicy(BehaviorPolicy):
    """Política determinística de utilidade e reação para NPCs."""
    name: str = "utility_behavior_policy"
    version: str = "1.0.0"

    def propose(self, ctx: ReactionContext) -> Tuple[Intent, ...]:
        npc = ctx.npc_state
        if not npc:
            return ()

        intents: List[Intent] = []
        # 1. Se tem plano ativo, tenta avançar o passo atual
        if hasattr(npc, "active_plan") and npc.active_plan and npc.active_plan.status == "active":
            plan = npc.active_plan
            idx = plan.current_step_index
            if 0 <= idx < len(plan.steps):
                step = plan.steps[idx]
                intents.append(
                    Intent(
                        actor_kind="npc",
                        actor_id=npc.id,
                        intent_kind="plan_step",
                        description=f"Executar passo {step.order} do plano '{plan.plan_id}': {step.description}",
                        target_id=getattr(step, "target_ref", None),
                        meta={"plan_id": plan.plan_id, "step_id": step.step_id},
                    )
                )
                return tuple(intents)

        # 2. Se tem metas ativas, propõe ação voltada à meta de maior prioridade
        if hasattr(npc, "goals") and npc.goals:
            active_goals = [g for g in npc.goals if g.status == "active"]
            if active_goals:
                best_goal = max(active_goals, key=lambda g: g.priority)
                intents.append(
                    Intent(
                        actor_kind="npc",
                        actor_id=npc.id,
                        intent_kind="action",
                        description=f"Perseguir objetivo '{best_goal.description}'",
                        target_id=best_goal.target_ref,
                        meta={"goal_id": best_goal.goal_id},
                    )
                )
                return tuple(intents)

        # 3. Reação situacional com atores presentes
        for actor in ctx.present_actors:
            if actor != npc.id:
                intents.append(
                    Intent(
                        actor_kind="npc",
                        actor_id=npc.id,
                        intent_kind="action",
                        description=f"Observar e avaliar postura de {actor}",
                        target_id=actor,
                    )
                )
                break

        return tuple(intents)


class StrategicFactionPolicy(FactionPolicy):
    """Política determinística estratégica para tomadas de decisão de facções."""
    name: str = "strategic_faction_policy"
    version: str = "1.0.0"

    def propose(self, ctx: FactionContext) -> Tuple[Intent, ...]:
        fac = ctx.faction_state
        if not fac:
            return ()

        intents: List[Intent] = []

        # 1. Se a coesão estiver baixa (< 50), prioriza reorganização interna
        if getattr(fac, "cohesion", 100) < 50:
            intents.append(
                Intent(
                    actor_kind="faction",
                    actor_id=fac.tag,
                    intent_kind="action",
                    description=f"Consolidar liderança e restaurar coesão interna de {fac.name}",
                    acts_for_faction=fac.tag,
                    meta={"action_type": "restore_cohesion"},
                )
            )
            return tuple(intents)

        # 2. Se há relógio ativo da facção nos relógios do mundo, foca em avançá-lo
        fac_clock = getattr(fac, "clock", "")
        if fac_clock:
            intents.append(
                Intent(
                    actor_kind="faction",
                    actor_id=fac.tag,
                    intent_kind="action",
                    description=f"Mobilizar recursos para avançar o relógio '{fac_clock}'",
                    acts_for_faction=fac.tag,
                    meta={"clock_name": fac_clock},
                )
            )
            return tuple(intents)

        # 3. Default: manter patrulha e influência territorial
        intents.append(
            Intent(
                actor_kind="faction",
                actor_id=fac.tag,
                intent_kind="action",
                description=f"Exercer influência territorial e vigiar rivais de {fac.name}",
                acts_for_faction=fac.tag,
            )
        )
        return tuple(intents)


__all__ = [
    "UtilityBehaviorPolicy",
    "StrategicFactionPolicy",
]
