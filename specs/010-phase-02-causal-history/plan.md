# Implementation Plan: 010 — Fase 02: História Causal & Refatoração R1

**Feature:** `phase-02-causal-history`  
**Status:** Ready for Tasks / Implementation  
**Created:** 2026-10-24  
**Target:** Fase 02 do [`ROADMAP.md`](../../ROADMAP.md) e etapa R1 da refatoração arquitetural  
**Base Analisada:**
- [`specs/010-phase-02-causal-history/spec.md`](spec.md) (G1/G2 ratificados em 23/10/2026)
- [`specs/010-phase-02-causal-history/checklists/g1-g2-ratification.md`](checklists/g1-g2-ratification.md)
- [`specs/010-phase-02-causal-history/research.md`](research.md)
- [`specs/010-phase-02-causal-history/data-model.md`](data-model.md)
- [`specs/010-phase-02-causal-history/contracts/store_and_projection_contracts.md`](contracts/store_and_projection_contracts.md)
- [`specs/010-phase-02-causal-history/quickstart.md`](quickstart.md)
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §2 (D1/D2/D4), §5.0–§5.5, §6, §8, §11
- [`ROADMAP.md`](../../ROADMAP.md) §3 (Fase 02), §5 (G1/G2), §6.4 (R1)
- [`EXECUCAO.md`](../../EXECUCAO.md) `EX-0012` e `EX-0013`

---

## 1. Plan Overview & Objectives

Este plano define a estratégia executável para implementar a **Fase 02 (História Causal)** e a etapa **R1 da Refatoração Arquitetural** do RPGPRO. O objetivo central é transformar o modelo legado baseado em "Markdown mutável gravado diretamente no commit" em uma arquitetura robusta de **"Event Store Append-Only em JSONL Canônico + Projeções Reconstruíveis Byte-Idênticas + Grafo de Dependências Causal + Auditoria de Correções"**, mantendo a compatibilidade retroativa e 100% dos testes verdes.

### Objetivos Centrais de R1:
1. **`JsonlEventStore` Concreto com Marcadores Atômicos e Resiliência (C1)**:
   - Implementar o store em disco em `adapters/persistence/event_store.py` com rotação de segmentos (1.000 eventos ou 1 MB).
   - Atomicidade all-or-nothing garantida pelos marcadores `batch.open` e `batch.committed`.
   - Recuperação prévia no append que trunca automaticamente lotes parciais/órfãos decorrentes de crashes.
   - Cálculo e validação dos dois hashes independentes: hash individual do evento e hash consolidado do lote.
   - Rejeição de `game_time` / `game_time_sort` ausentes (o store não inventa defaults).
2. **Catálogo Mínimo v1 e Upcasters (`kernel/` & `resources/`)**:
   - Registrar os 23 tipos de eventos do catálogo v1 com schemas de payload estritos.
   - Suporte a upcasters determinísticos $N \to N+1$ e rejeição de schemas futuros (`SchemaError`).
   - Registro explícito e imutável no `bootstrap.py` (sem auto-descoberta).
3. **Grafo de Dependências Causal (DAG) & Dependências Intra-Lote (C2)**:
   - Validação prévia de `meta.dependencies` garantindo aciclicidade e profundidade $\le 64$.
   - Suporte nativo a referências intra-lote (eventos do mesmo turno referenciando eventos que os antecedem no mesmo lote).
4. **Motor de Projeções Determinístico, Checkpoints e Rebuild (C3)**:
   - Implementar projectors para `diario.md`, `ficha.md` e `npcs.md`.
   - Garantir reconstrução byte-idêntica (`rebuild`) a partir do zero ou de snapshots sem executar efeitos secundários (sem LLM).
   - Emissão de `projection.rebuilt` isolada do cálculo de hash das projeções (o evento de auditoria não altera o hash auditado).
5. **Subsistema de Correções, Compensações e Contradições (C4)**:
   - Emissão de `correction.issued` append-only (o passado original nunca é apagado).
   - Reavaliação seletiva de dependentes transitivos com emissão de eventos compensatórios com `meta.correction_id`.
   - Registro explícito de inconsistência (`inconsistency_detected: true`) para fatos contraditórios, impedindo mutação silenciosa do passado.
6. **Prosa Imutável e Fila Esqueleto**:
   - Armazenamento em `artifacts/prose/turn_{seq:06d}-{hash}.md` com apontador em `prose.recorded`.
   - Fila append-only em `queue.jsonl` registrando ciclo de vida `pending` $\to$ `done`/`failed`.
7. **Modularização de `council/ssot.py` para `resources/`**:
   - Extrair responsabilidades de relógios, ficha, diário e missões para módulos em `resources/` mantendo cada arquivo rigorosamente abaixo de 300 linhas de código.
   - Preservar a API pública de `council/ssot.py` delegando para os novos recursos sem quebrar testes legados.

---

## 2. Technical Context & Constitution Gates

* **D1 — O Event Log é a Verdade Única**:
  `diario.md`, `ficha.md` e `npcs.md` são projeções derivadas e reconstruíveis. `mundo.md` e `regras.md` permanecem arquivos estáticos de configuração.
* **D2 — JSONL Canônico por Campanha**:
  A verdade reside nos arquivos de segmento `events/*.jsonl`. O índice SQLite é derivado e opcional; nenhuma leitura básica depende dele.
* **D4 — Campanhas Antigas Descartadas**:
  Zero código de migração de campanhas legadas. Campanhas antigas foram arquivadas em R0.5.
* **Ponytail Standard Library First**:
  Implementação 100% pura em Python Standard Library (`json`, `hashlib`, `pathlib`, `re`, `dataclasses`, `typing`, `unittest`). Nenhuma dependência externa.
* **Limites Rígidos de Código e Linhas**:
  - Alvo de 150 a 300 linhas por arquivo; alerta aos 400; falha aos 600 (fiscalizado por `tests/test_architecture_boundaries.py`).
  - `lazy_turn.py` permanece menor que 200 linhas.
* **Fronteira AST de Importações**:
  - `contracts/` e `kernel/` não fazem I/O nem importam camadas superiores.
  - `adapters/persistence` não importa domínio (`council/`, `rulesets/`, etc.).
  - `application/` não importa interfaces CLI.
* **Soberania do RPGPRO & Zero Emojis**:
  - Respostas, logs e artefatos sem emojis, garantindo foco técnico, anti-puppeteering e consistência determinística.

---

## 3. Work Breakdown Structure (WBS)

### Fase 1: Fundação do `JsonlEventStore` e Resiliência a Falhas (Critério C1)
- [ ] **Task 1.1**: Implementar `adapters/persistence/event_store.py`:
  - Rotação de segmentos em `events/<segment:06d>.jsonl` (1.000 eventos ou 1 MB).
  - Marcadores atômicos `batch.open` e `batch.committed`.
  - Serialização JSON canônica ordenada e cálculo de SHA-256 para eventos e lotes (FR-G1-10).
  - Suporte a lock exclusivo cooperativo por campanha via lockfile.
- [ ] **Task 1.2**: Implementar rotina de recuperação no append (Critério C1, FR-G1-09):
  - Inspecionar cauda do segmento ativo antes de qualquer novo append.
  - Se houver `batch.open` sem `batch.committed`, truncar o arquivo até o último committed e forçar `fsync`.
  - Recalcular `last_seq` estritamente a partir do último evento confirmado.
- [ ] **Task 1.3**: Validação estrita de tempo e concorrência:
  - Rejeitar rascunhos sem `game_time` ou sem `game_time_sort` com `InvalidDraftError` (FR-G1-05).
  - Validar `expected_last_seq` sob lock disparando `SeqConflictError` (FR-G1-03).
  - Rejeitar lotes duplicados com `DuplicateBatchError` (FR-G2-07).
- [ ] **Task 1.4**: Conectar `JsonlEventStore` na suíte de contrato `EventStoreContract` em `tests/test_contract_event_store.py` e criar testes de simulação de falha antes/durante/depois de marcadores (C1).

---

### Fase 2: Catálogo Mínimo de Eventos v1, Schemas e Upcasters
- [ ] **Task 2.1**: Criar módulo de catálogo de schemas em `kernel/event_catalog.py` (ou `resources/event_types.py`):
  - Definir os 23 schemas de payload v1 validados por `kernel/schema.py`.
  - Configurar dicionário de upcasters $N \to N+1$.
- [ ] **Task 2.2**: Atualizar `bootstrap.py` para registrar todos os `EventType`s no `Registry` congelado.
- [ ] **Task 2.3**: Integrar validação de schema no método `append()` do `EventStore`:
  - Rejeitar tipos não registrados com `UnknownEventTypeError` (FR-G1-04).
  - Rejeitar payloads que violam o schema com `SchemaError`.
  - No `read()`, aplicar cadeia de upcasters para eventos antigos e rejeitar versões futuras com `SchemaError` (FR-G1-07).
- [ ] **Task 2.4**: Criar testes unitários dedicados em `tests/test_event_catalog.py` validando os 23 tipos e upcasting.

---

### Fase 3: Grafo de Dependências Causal (DAG) & Dependências Intra-Lote (Critério C2)
- [ ] **Task 3.1**: Criar `kernel/dag.py`:
  - Validador de aciclicidade e profundidade de dependências ($\le 64$).
  - Resolução de dependências históricas a partir de `store.read()`.
- [ ] **Task 3.2**: Suporte a dependências intra-lote (Critério C2, FR-G2-09):
  - Permitir que eventos de um lote referenciem `event_id` provisórios de eventos que os antecedem no mesmo lote.
  - Rejeitar dependências futuras no mesmo lote e auto-dependências com `DependencyCycleError` ou `DependencyError`.
- [ ] **Task 3.3**: Criar testes dedicados em `tests/test_causal_dag.py` cobrindo DAG, detecção de ciclos, limite de profundidade e resolução intra-lote.

---

### Fase 4: Motor de Projeções, Checkpoints e Rebuild Byte-Idêntico (Critério C3)
- [ ] **Task 4.1**: Implementar `Projector`s especializados em `application/projectors/`:
  - `JournalProjector` (projeção para `diario.md`).
  - `CharacterSheetProjector` (projeção para `ficha.md`).
  - `NpcProjector` (projeção para `npcs.md`).
- [ ] **Task 4.2**: Implementar `ProjectionEngine` e `ProjectionWriter`:
  - Aplicação sequencial dos projectors baseada em `EventStreamView`.
  - Escrita atômica em arquivos via temporário e `os.replace`.
  - Cálculo do `projection_hash` consolidado.
  - Checkpoint em `snapshots/<seq:06d>.json` a cada 500 eventos ou fechamento de arco.
- [ ] **Task 4.3**: Implementar serviço de Rebuild (`application/rebuild.py`):
  - Reconstrução completa a partir do zero ou de snapshot mais recente.
  - Garantia de resultado byte-idêntico ao fluxo normal (FR-G2-04, FR-G2-05).
  - **Isolamento do evento de auditoria (Critério C3, FR-G2-10):** Gravar `projection.rebuilt` após o cálculo e validação do hash, comprovando que o evento de auditoria não altera os arquivos de projeção auditados.
- [ ] **Task 4.4**: Criar testes em `tests/test_projection_rebuild.py` validando reconstrução determinística, idempotência e ausência de autoinfluência no hash.

---

### Fase 5: Modularização de `council/ssot.py` para `resources/`
- [ ] **Task 5.1**: Criar pacote `resources/` com módulos com responsabilidade única (< 300 linhas):
  - `resources/clocks.py`: gerenciamento e avanço de relógios narrativos.
  - `resources/sheet.py`: vitais, atributos, habilidades e inventário do protagonista.
  - `resources/ledger.py`: registros cronológicos, notas e histórico de reputação.
  - `resources/progression.py`: XP, níveis e pontos de progressão.
- [ ] **Task 5.2**: Refatorar `council/ssot.py` para delegar chamadas para os módulos em `resources/`, mantendo total retrocompatibilidade com a API legada utilizada em testes e na CLI.
- [ ] **Task 5.3**: Garantir conformidade com `tests/test_architecture_boundaries.py` (nenhum arquivo $> 300$ linhas, zero imports proibidos).

---

### Fase 6: Subsistema de Correção, Compensação e Contradições (Critério C4)
- [ ] **Task 6.1**: Implementar `application/correction.py`:
  - Processamento de `correction.issued` como fato append-only (FR-G2-01).
  - Identificação de dependentes transitivos no DAG causal via `DependencyGraph`.
  - Emissão de eventos compensatórios com `meta.correction_id` para recursos numéricos reversíveis (XP, vitais, relógios).
- [ ] **Task 6.2**: Suporte a correções contraditórias (Critério C4, FR-G2-11):
  - Identificar premissas invalidadas em fatos posteriores não reversíveis.
  - Gravar `correction.recomputed` anotando a inconsistência (`inconsistency_detected: true`) sem alterar silenciosamente o passado.
  - Atualizar `council/reviewer.py` para sinalizar a inconsistência pendente de revisão.
- [ ] **Task 6.3**: Criar testes em `tests/test_causal_correction.py` cobrindo compensações seletivas e detenção de contradições.

---

### Fase 7: Prosa Imutável e Fila Esqueleto (`queue.jsonl`)
- [ ] **Task 7.1**: Implementar `application/prose_store.py`:
  - Gravação de textos narrativos em `campaigns/<id>/artifacts/prose/turn_{seq:06d}-{hash}.md`.
  - Verificação de hash SHA-256 e emissão de `prose.recorded`.
  - Blindagem contra edição de prosas antigas (FR-G2-06).
- [ ] **Task 7.2**: Implementar `adapters/persistence/skeleton_queue.py`:
  - Gravação append-only em `queue.jsonl` de trabalhos com `wrk_<ulid>` e status `pending`.
  - Finalização via novo registro com status `done` ou `failed` referenciando `work_id` (FR-G2-08).
- [ ] **Task 7.3**: Criar testes unitários em `tests/test_prose_and_queue.py`.

---

### Fase 8: Integração na CLI, Comandos e Validação Global
- [ ] **Task 8.1**: Integrar emissão de eventos e projeções no pipeline de `lazy_turn.py`:
  - No `commit_turn`: montar lote atômico com drafts do turno, persistir via `EventStore.append()`, executar projeções e gravar prosa.
  - Adicionar comando CLI `rebuild` em `lazy_turn.py` (`python lazy_turn.py rebuild --campaign <id>`).
  - Adicionar comando CLI `correct` em `lazy_turn.py` para emissão formal de correções.
- [ ] **Task 8.2**: Executar suíte de testes ponta a ponta e testes de contrato da CLI (`tests/test_cli_contracts.py`).
- [ ] **Task 8.3**: Validar ausência de regressões na suíte completa (`python -m unittest discover -s tests`).
- [ ] **Task 8.4**: Documentar execução em `EXECUCAO.md` e atualizar status no `ROADMAP.md`.

---

## 4. Mapeamento de Requisitos Funcionais e Critérios

| Requisito / Critério | Descrição | WBS Task | Teste de Aceite |
|---|---|---|---|
| **FR-G1-01** | Atribuição de `event_id`, `seq` e `recorded_at` pelo store | Task 1.1 | `test_append_assigns_identity_order_and_time` |
| **FR-G1-02** | Falha no lote não deixa eventos visíveis nem consome seq | Task 1.1 | `test_failed_batch_persists_nothing` |
| **FR-G1-03** | Conflito de `expected_last_seq` gera `SeqConflictError` | Task 1.3 | `test_divergent_expected_last_seq_raises` |
| **FR-G1-04** | Validação de payload e rejeição de tipo desconhecido | Task 2.3 | `test_unknown_event_type_rejected` |
| **FR-G1-05** | Rejeição de draft sem `game_time` / `game_time_sort` | Task 1.3 | `test_missing_game_time_rejected` |
| **FR-G1-06** | Serialização canônica e hash SHA-256 reproduzível | Task 1.1 | `test_canonical_serialization_and_hash` |
| **FR-G1-07** | Upcasters $1 \to 2$ e rejeição de versão futura | Task 2.3 | `test_schema_upcasting_and_future_rejection` |
| **FR-G1-08** | Segmentação e snapshots para rebuild | Task 1.1, 4.2 | `test_segmentation_and_snapshot_rebuild` |
| **FR-G1-09 / C1** | Resiliência a crashes e recuperação por truncamento | Task 1.2 | `test_crash_recovery_truncates_incomplete_batch` |
| **FR-G1-10** | Hashes de evento e lote distintos e auditáveis | Task 1.1 | `test_event_and_batch_hashes_independent` |
| **FR-G2-01** | Correção é novo evento que referencia o original | Task 6.1 | `test_correction_issues_new_event` |
| **FR-G2-02** | Grafo de dependências é DAG (sem ciclos) | Task 3.1 | `test_dag_cycle_rejection` |
| **FR-G2-03** | Correção reavalia apenas dependentes afetados | Task 6.1 | `test_selective_reevaluation` |
| **FR-G2-04** | Rebuild reproduz Markdown byte-idêntico | Task 4.3 | `test_rebuild_byte_identical` |
| **FR-G2-05** | Rebuild não reexecuta LLM nem duplica XP | Task 4.3 | `test_rebuild_does_not_duplicate_effects` |
| **FR-G2-06** | Prosa imutável recuperável por hash/caminho | Task 7.1 | `test_prose_immutability_and_lookup` |
| **FR-G2-07** | Retomada e reenvio não duplicam efeitos | Task 1.3, 4.2 | `test_duplicate_batch_rejection` |
| **FR-G2-08** | Fila esqueleto append-only (`queue.jsonl`) | Task 7.2 | `test_skeleton_queue_lifecycle` |
| **FR-G2-09 / C2** | Validação de dependências intra-lote | Task 3.2 | `test_intra_batch_dependencies_accepted` |
| **FR-G2-10 / C3** | `projection.rebuilt` emitido fora do hash auditado | Task 4.3 | `test_rebuild_audit_isolated_from_hash` |
| **FR-G2-11 / C4** | Correção contraditória anota inconsistência | Task 6.2 | `test_contradictory_correction_flags_inconsistency` |

---

## 5. Gerenciamento de Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| **Quebra de compatibilidade em testes legados ao migrar `ssot.py`** | Alto | Manter wrappers transparentes em `council/ssot.py` que repassam chamadas aos novos módulos em `resources/` sem alterar assinaturas. |
| **Corrupção de segmento por falha concorrente no Windows** | Alto | Uso de arquivo de lock cooperativo (`.lock`) com timeouts curtos e operações atômicas de escrita e flush/fsync. |
| **Degradação de performance na leitura de segmentos longos** | Médio | Varredura em streaming linha a linha sem carregar arquivos inteiros em memória; snapshots a cada 500 eventos aceleram o rebuild. |
| **Divergência de hash de projeção por quebras de linha (`\r\n` vs `\n`)** | Alto | Normalização forçada de quebras de linha para `\n` e codificação UTF-8 estrita em todas as saídas e cálculos de hash. |
