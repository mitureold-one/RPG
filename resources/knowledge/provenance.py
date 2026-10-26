"""resources/knowledge/provenance.py: Validação de Proveniência e Detecção de Ciclos Epistêmicos (Gate G3).

Garante que toda inferência ou alegação adquirida possua grafo acíclico (DAG) de premissas,
exige proveniência explícita, bloqueia dependências de premissas inexistentes ou refutadas,
e impede que inferências sem evidência direta declarem certeza absoluta (10000 bps).
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple
from resources.knowledge.model import KnowledgeRecord, ProvenanceRef


class ProvenanceCycleError(ValueError):
    """Lançado quando uma cadeia de proveniência forma um ciclo (violando DAG)."""
    pass


class InvalidPremiseError(ValueError):
    """Lançado quando uma inferência se baseia em premissa inexistente ou refutada."""
    pass


def detect_cycle_in_dag(
    target_id: str,
    direct_dependencies: Iterable[str],
    graph: Dict[str, Iterable[str]],
) -> Optional[List[str]]:
    """Detecta se adicionar direct_dependencies para target_id geraria um ciclo no DAG."""
    visited: Set[str] = set()

    def _dfs(current: str, path: List[str]) -> Optional[List[str]]:
        if current == target_id:
            return path + [current]
        if current in visited:
            return None
        visited.add(current)

        neighbors = graph.get(current, ())
        for n in neighbors:
            res = _dfs(n, path + [current])
            if res:
                return res
        return None

    for dep in direct_dependencies:
        if dep == target_id:
            return [target_id, dep]
        res = _dfs(dep, [target_id])
        if res:
            return res
    return None


def validate_provenance_chain(
    candidate_record: KnowledgeRecord,
    existing_records: Dict[str, KnowledgeRecord],
) -> Tuple[bool, List[str]]:
    """Valida estritamente a cadeia de proveniência de um candidato a registro epistêmico (P1-1).

    Critérios Obrigatórios:
    1. Proveniência não vazia: len(candidate_record.provenance) > 0.
    2. Existência de premissas: todas as referências em derived_from devem existir em existing_records.
    3. Bloqueio de premissas refutadas: nenhuma dependência pode ter status == 'refuted'.
    4. Aciclicidade: grafo direcionado não pode conter ciclos (DAG estrito).
    5. Calibração de inferência: canal 'inference' não pode ter confiança 10000 se premissas tiverem < 10000.
    """
    errors: List[str] = []

    # 1. Checagem de proveniência não vazia
    if not candidate_record.provenance:
        errors.append("Registro epistêmico carece de proveniência (provenance não pode ser vazia)")

    # 2 & 3. Checagem de premissas existentes e não-refutadas
    deps = list(candidate_record.derived_from)
    for p in candidate_record.provenance:
        deps.extend(p.derived_from)
    unique_deps: List[str] = list(dict.fromkeys(deps))

    for dep_id in unique_deps:
        if dep_id not in existing_records:
            errors.append(f"Premissa não localizada no repositório epistêmico: '{dep_id}'")
            continue

        premise = existing_records[dep_id]
        if premise.status == "refuted":
            errors.append(
                f"Premissa '{dep_id}' está refutada (status='refuted'). Impossível fundamentar inferência sobre premissa refutada."
            )

    # 4. Detecção de ciclos
    graph: Dict[str, Iterable[str]] = {}
    for r_id, r in existing_records.items():
        r_deps = list(r.derived_from)
        for p in r.provenance:
            r_deps.extend(p.derived_from)
        graph[r_id] = r_deps

    cycle = detect_cycle_in_dag(candidate_record.record_id, unique_deps, graph)
    if cycle:
        cycle_str = " -> ".join(cycle)
        errors.append(f"Ciclo detectado na cadeia de proveniência: {cycle_str}")

    # 5. Calibração de inferência: inferência derivada não pode inflar confiança além do elo mais fraco
    for p in candidate_record.provenance:
        if p.channel == "inference":
            if not p.derived_from and not candidate_record.derived_from:
                errors.append("Proveniência do canal 'inference' requer derived_from preenchido")
            else:
                premise_confidences = [
                    existing_records[d].confidence
                    for d in unique_deps
                    if d in existing_records
                ]
                if premise_confidences:
                    max_allowed = min(premise_confidences)
                    if candidate_record.confidence > max_allowed:
                        errors.append(
                            f"Inferência com confiança ({candidate_record.confidence}) superior à menor premissa ({max_allowed})"
                        )

    return (len(errors) == 0, errors)


def check_and_assert_provenance(
    candidate_record: KnowledgeRecord,
    existing_records: Dict[str, KnowledgeRecord],
) -> None:
    """Wrapper asserivo que levanta exceções tipadas de proveniência."""
    is_valid, errors = validate_provenance_chain(candidate_record, existing_records)
    if not is_valid:
        first_err = errors[0]
        if "Ciclo" in first_err:
            raise ProvenanceCycleError(first_err)
        raise InvalidPremiseError("; ".join(errors))


__all__ = [
    "ProvenanceCycleError",
    "InvalidPremiseError",
    "detect_cycle_in_dag",
    "validate_provenance_chain",
    "check_and_assert_provenance",
]
