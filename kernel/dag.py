"""kernel/dag.py: Validação e travessia de Grafo Acíclico Dirigido (DAG) causal."""

from __future__ import annotations

from typing import AbstractSet, Any, Iterable, Mapping, Sequence

from contracts.event import EventDraft
from kernel.errors import (
    DependencyCycleError,
    DependencyDepthError,
    DependencyError,
)


class DependencyGraph:
    """Validador de causalidade e dependências acíclicas."""

    def __init__(self, max_depth: int = 64) -> None:
        self.max_depth = max(1, int(max_depth))

    def validate_batch(
        self,
        drafts: Sequence[EventDraft],
        provisional_ids: Sequence[str],
        known_event_ids: AbstractSet[str],
        parent_map: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        """Valida que meta.dependencies de cada draft obedece aciclicidade e profundidade.
        
        Permite dependências intra-lote (Critério C2) apenas para eventos anteriores no lote.
        """
        combined_parents: dict[str, list[str]] = {}
        if parent_map:
            for k, v in parent_map.items():
                combined_parents[k] = list(v)

        for i, draft in enumerate(drafts):
            current_eid = provisional_ids[i]
            deps = draft.meta.get("dependencies", [])
            if not isinstance(deps, (list, tuple)):
                raise DependencyError(
                    f"meta.dependencies deve ser lista no evento {current_eid}",
                    details={"event_id": current_eid},
                )

            valid_prev_provisional = set(provisional_ids[:i])
            future_provisional = set(provisional_ids[i + 1 :])

            deps_clean: list[str] = []
            for dep in deps:
                if not isinstance(dep, str):
                    raise DependencyError(
                        f"Identificador de dependência deve ser string: {dep!r}",
                        details={"event_id": current_eid, "dep": dep},
                    )
                if (dep.startswith("batch:") and dep[6:].isdigit()) or (dep.startswith("@") and dep[1:].isdigit()):
                    raw_idx = dep[6:] if dep.startswith("batch:") else dep[1:]
                    target_idx = int(raw_idx)
                    if target_idx >= i:
                        raise DependencyError(
                            f"Dependência para frente proibida dentro do lote: {dep}",
                            details={"event_id": current_eid, "dep": dep},
                        )
                    dep = provisional_ids[target_idx]

                if dep == current_eid:
                    raise DependencyCycleError(
                        f"Auto-dependência detectada no evento {current_eid}",
                        details={"event_id": current_eid},
                    )
                if dep in future_provisional:
                    raise DependencyError(
                        f"Dependência para frente proibida dentro do lote: {dep}",
                        details={"event_id": current_eid, "dep": dep},
                    )
                if dep not in known_event_ids and dep not in valid_prev_provisional:
                    raise DependencyError(
                        f"Dependência inexistente: '{dep}'",
                        details={"event_id": current_eid, "dep": dep},
                    )
                deps_clean.append(dep)

            combined_parents[current_eid] = deps_clean

        # Verificação de ciclos e cálculo de profundidade máxima
        # 0: não visitado, 1: em visitação na pilha atual, 2: completamente visitado
        visited_state: dict[str, int] = {}
        depth_memo: dict[str, int] = {}

        def compute_depth(node: str, stack: list[str]) -> int:
            if node in stack:
                cycle_str = " -> ".join(stack[stack.index(node) :] + [node])
                raise DependencyCycleError(
                    f"Ciclo causal detectado: {cycle_str}",
                    details={"cycle": cycle_str},
                )
            if node in depth_memo:
                return depth_memo[node]

            parents = combined_parents.get(node, ())
            if not parents:
                depth_memo[node] = 1
                return 1

            stack.append(node)
            max_p_depth = 0
            for p in parents:
                p_depth = compute_depth(p, stack)
                if p_depth > max_p_depth:
                    max_p_depth = p_depth
            stack.pop()

            total_depth = max_p_depth + 1
            if total_depth > self.max_depth:
                raise DependencyDepthError(
                    f"Profundidade de dependência ({total_depth}) excedeu limite máximo ({self.max_depth})",
                    details={"node": node, "depth": total_depth, "limit": self.max_depth},
                )
            depth_memo[node] = total_depth
            return total_depth

        for eid in provisional_ids:
            compute_depth(eid, [])

    def get_dependents_transitive(
        self,
        root_event_ids: Iterable[str],
        forward_adj: Mapping[str, Sequence[str]],
    ) -> list[str]:
        """Devolve em ordem topológica todos os nós dependentes alcançáveis a partir dos roots."""
        visited: set[str] = set()
        order: list[str] = []

        def dfs(node: str) -> None:
            for child in forward_adj.get(node, ()):
                if child not in visited:
                    visited.add(child)
                    dfs(child)
                    order.append(child)

        for root in root_event_ids:
            dfs(root)

        return list(reversed(order))


__all__ = ["DependencyGraph"]
