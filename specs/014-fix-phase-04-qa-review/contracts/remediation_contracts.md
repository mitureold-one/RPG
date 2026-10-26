# Remediation Interface Contracts: 014 — Remediação de QA da Fase 04

**Feature:** `fix-phase-04-qa-review`  
**Data:** 2026-10-26  
**Status:** Consolidado  

---

## 1. Contrato Epistêmico e Deserialização de Conhecimento

### `_dict_to_knowledge_record` (`application/context/knowledge.py`)
Reconstrói uma instância estrita de `KnowledgeRecord` com suas proveniências tipadas a partir do payload JSON em `estado.json`.

```python
def _dict_to_knowledge_record(d: Mapping[str, Any]) -> KnowledgeRecord | None:
    """Deserializa um registro de conhecimento persistido em estado.json.
    
    Invariantes:
    1. Reconstitui ProvenanceRef com:
       - source_type (str)
       - source_id (str)
       - channel (str)
       - acquired_at (str)
       - acquired_at_sort (int)
       - confidence (int 0..10000)
       - derived_from (tuple[str, ...])
       - supports (bool)
    2. Utiliza HolderRef unificado de contracts.context.
    3. Converte awareness para 'known'/'unknown' e stance para 'believed'/'disbelieved'/'uncertain'.
    4. Não silencia erros inesperados: falha alto se os tipos fundamentais forem inválidos.
    """
```

---

## 2. Contrato de Extração Relacional e Relevância de NPCs

### `_extract_relational_vector` (`resources/context/relevance.py`)
Normalizador de vetores relacionais direcionados.

```python
def _extract_relational_vector(
    npc_data: Mapping[str, Any],
    target_id: str = "",
) -> dict[str, Any]:
    """Extrai e normaliza o vetor relacional de um NPC para um dicionário padronizado.
    
    Invariantes:
    1. Suporta npc_data['relationships'] como list[dict] ou dict.
    2. Suporta fallback em npc_data['relational_vector'].
    3. Se target_id for fornecido, busca o vetor onde target_id bate com o solicitado.
    4. Retorna dict com chaves 'trust', 'rivalry', 'debt', 'loyalty', 'dependency' como inteiros.
    """
```

### `score_npc` (`resources/context/relevance.py`)
```python
def score_npc(
    npc_data: Mapping[str, Any],
    request: ContextRequest,
    state: ContextStateView,
    context_facts: Sequence[str] = (),
    target_id: str = "",
) -> tuple[int, tuple[str, ...]]:
    """Calcula pontuação de relevância de um NPC e retorna (score, reasons).
    
    Invariantes:
    1. Nunca dispara AttributeError ao acessar relacionamentos.
    2. Aplica +200 e reason 'ameaca' se rivalry >= 2 ou trust <= -2.
    3. Aplica +150 e reason 'divida' se debt != 0.
    """
```

---

## 3. Contrato de Cache e Gestão de Staleness

### `ContextStateViewImpl.load` (`application/context/state.py`)
```python
@classmethod
def load(
    cls,
    campaign_id: str,
    campaign_dir: Path | str,
    store: EventStore | None = None,
    diario_data: Mapping[str, Any] | None = None,
) -> ContextStateView:
    """Carrega estado.json com validação de schema_version e alinhamento de sequência.
    
    Invariantes:
    1. Valida se data['schema_version'] == 1; caso contrário, marca como corrompido/stale.
    2. Se cached_seq < expected_seq, inspeciona se os eventos pós-cached_seq são apenas
       eventos de auditoria ('projection.*'). Em caso afirmativo, o cache NÃO é considerado stale.
    3. Se rebuild for executado, o novo estado.json é lido sem loops infinitos de staleness.
    """
```

---

## 4. Contrato de Fatos e Correções Causais

### `FactsCausalProvider.provide` (`application/context/knowledge.py`)
```python
class FactsCausalProvider:
    """Provedor causal de fatos e consequências recentes com suporte a correções."""

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        """Coleta fatos e consequências recentes.
        
        Invariantes:
        1. Identifica IDs de eventos corrigidos em correction.issued via 'corrects'
           (aceitando strings 'evt_<ulid>' e inteiros de sequência).
        2. Omite do contexto vigente qualquer fato cujo event_id ou seq conste nas correções.
        3. Registra a correção como item de consequência recente.
        """
```

---

## 5. Contrato de Seleção de Atores de Cena e Missões

### `resolve_scene_actors` (`application/context/scene.py`)
```python
def resolve_scene_actors(
    all_npcs: Sequence[Mapping[str, Any]],
    diario_data: Mapping[str, Any] | None,
    focus: str = "",
    action: str = "",
) -> tuple[tuple[str, ...], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Determina elenco presente, atores focais e figurantes.
    
    Invariantes:
    1. Se nenhum NPC for identificado por foco ou ação, seleciona até os 2 primeiros
       NPCs presentes na cena (scene_npcs[:2]) como atores focais por fallback legado.
    """
```

### `build_quest_context` (`application/context/scene.py`)
```python
def build_quest_context(diario_path: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extrai missões ativas e formula mandato de pressão.
    
    Invariantes:
    1. Filtra estritamente apenas missões com status == 'ACTIVE'.
    2. Ignora missões com status 'COMPLETED', 'FAILED' ou 'ABANDONED'.
    """
```
