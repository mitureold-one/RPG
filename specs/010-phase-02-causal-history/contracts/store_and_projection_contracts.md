# Interface Contracts: 010 — Fase 02: História Causal & Refatoração R1

**Feature:** `phase-02-causal-history`  
**Status:** Completed  
**Created:** 2026-10-24  
**Context:** Definição formal das interfaces de adaptadores, serviços de domínio e contratos de erro para o R1/Fase 02.

---

## 1. Contrato da Implementação `JsonlEventStore` (`adapters/persistence/event_store.py`)

A classe `JsonlEventStore` implementa a porta [`contracts.ports.EventStore`](../../contracts/ports.py).

### 1.1 Assinatura dos Métodos

```python
class JsonlEventStore:
    def __init__(
        self,
        base_dir: Path,
        max_events_per_segment: int = 1000,
        max_bytes_per_segment: int = 1_000_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        ...

    def append(
        self,
        campaign_id: str,
        drafts: Sequence[EventDraft],
        expected_last_seq: int | None = None,
    ) -> AppendResult:
        """Persiste um lote atômico de eventos na campanha.
        
        Garantias:
        1. Lock exclusivo cooperativo por campanha durante a escrita.
        2. Verificação e recuperação automática de segmento antes do append.
        3. Validação de expected_last_seq dentro da seção crítica.
        4. Validação de schema e tipo de cada draft.
        5. Validação de dependências intra-lote e históricas (DAG).
        6. Atribuição de event_id (evt_<ulid>), seq monotônico e recorded_at UTC.
        7. Gravação de marcador batch.open, eventos e batch.committed com fsync.
        8. Nenhum lote parcial fica visível para leitores em caso de falha.
        """
        ...

    def read(self, campaign_id: str, after_seq: int = 0) -> Iterable[Event]:
        """Lê eventos confirmados da campanha em ordem crescente de seq.
        
        Eventos pertencentes a lotes sem marcador batch.committed são ignorados.
        """
        ...

    def last_seq(self, campaign_id: str) -> int:
        """Devolve a última sequência confirmada da campanha (0 se vazia)."""
        ...
```

### 1.2 Semântica de Recuperação e Truncamento (Critério C1, FR-G1-09)

Antes de iniciar a escrita de qualquer novo lote:
1. O store abre o segmento ativo mais recente e localiza a última linha.
2. Se o último marcador de lote for `batch.open` (indicando crash ou interrupção durante a escrita anterior), o store calcula o byte offset imediatamente após o último marcador `batch.committed` verificado.
3. O arquivo é truncado (`file.truncate(offset)`) e forçado ao disco via `os.fsync()`.
4. A sequência corrente é recalculada com base no último evento confirmado.
5. Somente então o novo lote é gravado.

### 1.3 Contrato de Erros Tipados

| Exceção | Código (`code`) | Condição de Disparo |
|---|---|---|
| `SeqConflictError` | `SEQ_CONFLICT` | `expected_last_seq` difere da sequência atual dentro do lock |
| `DuplicateBatchError` | `DUPLICATE_BATCH` | Tentativa de reprocessar lote idêntico já persistido |
| `DependencyError` | `DEPENDENCY_MISSING` | Evento referencia dependência inexistente no histórico nem no lote anterior |
| `DependencyCycleError` | `DEPENDENCY_CYCLE` | Ciclo detectado nas dependências declaradas |
| `DependencyDepthError` | `DEPENDENCY_DEPTH_EXCEEDED` | Cadeia de dependência excede a profundidade máxima (64) |
| `SchemaError` | `SCHEMA_VALIDATION_FAILED` | Payload do evento viola o schema registrado para o `schema_version` |
| `UnknownEventTypeError` | `UNKNOWN_EVENT_TYPE` | Tipo de evento não registrado no Registry |
| `InvalidDraftError` | `INVALID_EVENT_DRAFT` | `game_time` ou `game_time_sort` ausentes ou inválidos no draft |

---

## 2. Contrato do Grafo de Dependências (`kernel/dag.py` ou `resources/dependencies.py`)

```python
class DependencyGraph:
    def __init__(self, max_depth: int = 64) -> None:
        ...

    def validate_batch(
        self,
        drafts: Sequence[EventDraft],
        provisional_ids: Sequence[str],
        known_event_ids: AbstractSet[str],
    ) -> None:
        """Valida que todas as referências em meta.dependencies são válidas.
        
        Regras (Critério C2):
        1. Toda dependência deve existir em known_event_ids OU no conjunto de provisional_ids
           que antecedem o evento atual na mesma sequência do lote.
        2. Dependências futuras dentro do mesmo lote são rejeitadas (DEPENDENCY_MISSING).
        3. Auto-dependência direta é rejeitada como ciclo (DEPENDENCY_CYCLE).
        4. O grafo resultante deve ser um DAG com profundidade <= max_depth.
        """
        ...

    def get_dependents_transitive(
        self,
        root_event_ids: Iterable[str],
        events_stream: Iterable[Event],
    ) -> list[Event]:
        """Devolve em ordem causal/topológica todos os eventos que dependem dos roots."""
        ...
```

---

## 3. Contrato do Motor de Projeções e Rebuild (`application/projection_engine.py`)

```python
class ProjectionEngine:
    def __init__(
        self,
        projectors: Sequence[Projector],
        campaign_dir: Path,
    ) -> None:
        ...

    def project_batch(self, events: Sequence[Event]) -> dict[str, str]:
        """Aplica eventos aos projectors registrados e devolve conteúdo renderizado."""
        ...

    def write_projections_atomic(self, sections: dict[str, str]) -> str:
        """Grava atomicamente os arquivos de projeção via arquivo temporário e os.replace.
        
        Devolve o projection_hash (SHA-256) dos conteúdos consolidados.
        """
        ...

    def rebuild_projections(
        self,
        store: EventStore,
        campaign_id: str,
        snapshot: Snapshot | None = None,
    ) -> tuple[int, str]:
        """Reconstrói do zero ou a partir de snapshot.
        
        Garantias (Critério C3):
        1. Aplica eventos válidos do stream sem executar efeitos secundários (sem LLM).
        2. Grava arquivos em projections/ (ou raiz de campanha).
        3. Calcula projection_hash.
        4. Grava projection.rebuilt fora do cálculo do hash (não altera o hash verificado).
        5. Devolve (last_seq_projetado, projection_hash).
        """
        ...
```

---

## 4. Contrato do Subsistema de Correção e Inconsistência (`application/correction.py`)

```python
class CorrectionService:
    def __init__(
        self,
        store: EventStore,
        dep_graph: DependencyGraph,
        engine: ProjectionEngine,
    ) -> None:
        ...

    def issue_correction(
        self,
        campaign_id: str,
        actor: ActorRef,
        corrects: Sequence[str],
        reason: str,
        changes: Sequence[dict[str, Any]],
        game_time: str,
        game_time_sort: int,
    ) -> AppendResult:
        """Emite correction.issued e processa reavaliação seletiva.
        
        Garantias (Critério C4):
        1. O evento original permanece inalterado no log.
        2. Avalia impacto sobre dependentes transitivos.
        3. Para efeitos numéricos reversíveis, gera drafts de compensação com meta.correction_id.
        4. Para contradições narrativas/irreversíveis, emite anotação e marca inconsistência
           (inconsistency_detected: true) sem alterar silenciosamente o passado.
        5. Submete lote atômico ao EventStore.append().
        """
        ...
```

---

## 5. Contrato do Repositório de Prosa Imutável (`application/prose_store.py`)

```python
class ProseStore:
    def __init__(self, campaign_dir: Path) -> None:
        ...

    def store_turn_prose(
        self,
        turn: int,
        content: str,
        scene_type: str = "action",
    ) -> tuple[str, str, int]:
        """Grava prosa em artifacts/prose/turn_{turn:06d}-{sha256[:8]}.md.
        
        Devolve: (relative_path, sha256_hash, byte_size).
        Se o arquivo já existir com o mesmo hash, é idempotente.
        Se existir com hash divergente, emite novo artefato versionado.
        """
        ...

    def verify_prose(self, relative_path: str, expected_hash: str) -> bool:
        """Verifica se o artefato existe e se o hash confere."""
        ...
```
