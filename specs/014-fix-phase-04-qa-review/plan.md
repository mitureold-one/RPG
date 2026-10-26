# Implementation Plan: 014 — Remediação dos Bloqueantes de QA da Fase 04

**Feature:** `fix-phase-04-qa-review`  
**Spec:** [`spec.md`](spec.md) · **Research:** [`research.md`](research.md) · **Data Model:** [`data-model.md`](data-model.md) · **Contracts:** [`contracts/remediation_contracts.md`](contracts/remediation_contracts.md) · **Quickstart:** [`quickstart.md`](quickstart.md)  
**Status:** Draft para revisão e execução  
**Created:** 2026-10-26  

---

## 1. Estratégia de Remediação

A auditoria independente do QA identificou que, apesar de a suíte unitária reportar 249 testes verdes, fixtures artificiais mascararam defeitos críticos em dados reais (P0-1, P0-2, P1-1, P1-2, P1-3, P1-4, P1-5). A remediação adota a estratégia de correção na raiz (Ground Truth First):

1. **Unificação Canônica de Tipos:** Eliminar a divergência entre `contracts.context.HolderRef` e `resources.knowledge.model.HolderRef` sem violar as restrições de importação de camadas (`contracts/` não importa `resources/`).
2. **Robustez a Dados Canônicos:** Reconstruir `ProvenanceRef` com seus 6 atributos canônicos e normalizar vetores relacionais de NPCs (`list[dict]` e `dict`) prevenindo exceções de tempo de execução.
3. **Determinismo e Estabilidade de Cache:** Desacoplar a numeração de auditoria (`projection.rebuilt`) do hash de projeções e assegurar alinhamento perfeito de `last_seq` em `estado.json` e `store`, eliminando o loop infinito de staleness.
4. **Precisão Causal de Correções:** Indexar `event_id` nos eventos recentes e suportar a anulação de fatos corrigidos tanto por `event_id` quanto por sequência numérica.
5. **Preservação Comportamental do Gameplay:** Restaurar os fallbacks de seleção de atores focais e filtros de missões ativas conforme o comportamento legado consolidado.
6. **Adequação da Suíte de Testes:** Substituir todas as fixtures artificiais por geradores canônicos e integrar testes de regressão para os cenários reais do QA.

---

## 2. Inventário de Módulos e Metas de Tamanho

Todos os módulos modificados devem permanecer estritamente abaixo do teto arquitetural de **300 linhas**:

| Módulo | Linhas Atuais | Linhas Estimadas | Responsabilidade da Alteração |
| :--- | :---: | :---: | :--- |
| `contracts/context.py` | 275 | ~275 | Unificação da classe `HolderRef` com validação de `VALID_HOLDER_KINDS`. |
| `resources/knowledge/model.py` | 150 | ~145 | Reexportação de `HolderRef` de `contracts.context`. |
| `resources/context/relevance.py` | 288 | ~295 | Helper `_extract_relational_vector`, suporte a `active_plan` em facções. |
| `application/context/knowledge.py` | 251 | ~265 | `_dict_to_knowledge_record` canônico e `FactsCausalProvider` com `event_id`. |
| `application/context/state.py` | 198 | ~220 | Tolerância a eventos de auditoria e validação de `schema_version`. |
| `application/context/scene.py` | 218 | ~225 | Fallback legado de 2 NPCs focais e filtro de missões com `status == "ACTIVE"`. |
| `application/context/query.py` | 206 | ~220 | Resolução do protagonista real a partir da ficha no CLI `query`. |
| `application/projectors/state.py` | 154 | ~165 | Inclusão de `event_id` em `recent_events` e alinhamento de `last_seq`. |
| `application/rebuild.py` | 150 | ~160 | Atualização de `last_seq` em `estado.json` após emissão de auditoria. |
| `interfaces/cli/main.py` | 383 | ~385 | Passagem do protagonista real para `ContextQueryService`. |
| `tests/test_phase04_causal_context.py` | 319 | ~380 | Fixtures 100% canônicas (com proveniência e `event_id`). |
| `tests/test_phase04_state_cache.py` | 134 | ~160 | Testes de staleness com `emit_audit_event=True`. |

---

## 3. Plano de Fases de Execução

### Fase 1: Fundação de Contratos e Modelos (P0-1 & P1-3)
- [ ] Atualizar `contracts/context.py` com `VALID_HOLDER_KINDS` e invariantes em `HolderRef`.
- [ ] Atualizar `resources/knowledge/model.py` para reexportar `HolderRef` de `contracts.context`.
- [ ] Validar importações com `python -m unittest tests/test_architecture_boundaries.py`.

### Fase 2: Robustez Relacional e Provedor Epistêmico (P0-1, P0-2, P2-1)
- [ ] Em `resources/context/relevance.py`:
  - Implementar `_extract_relational_vector(npc_data, target_id="")`.
  - Atualizar `score_npc` para utilizar o normalizador sem falha de `.get()`.
  - Atualizar `score_faction` para verificar `active_plan` além de `plan`/`initiative`.
- [ ] Em `application/context/knowledge.py`:
  - Corrigir `_dict_to_knowledge_record` para reconstruir `ProvenanceRef` canônica (6 campos).
  - Tratar exceções de integridade sem supressão cega.

### Fase 3: Cache, Sequenciamento e Histórico Causal (P1-1, P1-2, P2-8)
- [ ] Em `application/projectors/state.py`:
  - Incluir `"event_id": getattr(ev, "id", "")` em cada registro de `recent_events`.
  - Definir `last_seq` a partir de `view.last_seq`.
- [ ] Em `application/rebuild.py`:
  - Sincronizar o `last_seq` no arquivo `estado.json` em disco após append do `projection.rebuilt`.
- [ ] Em `application/context/state.py`:
  - Validar `schema_version == 1`.
  - Verificar se a defasagem entre `cached_seq` e `expected_seq` decorre apenas de eventos técnicos de projeção.
- [ ] Em `application/context/knowledge.py`:
  - Atualizar `FactsCausalProvider` para processar `corrects` por string `event_id` e número de sequência.

### Fase 4: Preservação de Comportamento Legado e CLI Query (P1-3, P1-4)
- [ ] Em `application/context/scene.py`:
  - Restaurar fallback de até 2 NPCs presentes em `resolve_scene_actors`.
  - Filtrar missões estritamente por `status == "ACTIVE"` em `build_quest_context`.
- [ ] Em `application/context/query.py` e `interfaces/cli/main.py`:
  - Resolver o nome do protagonista a partir de `ficha.md` quando `--audience protagonist` for invocado.

### Fase 5: Atualização da Suíte de Testes e Homologação (P1-5)
- [ ] Atualizar `tests/test_phase04_causal_context.py` com eventos canônicos completos (proveniência válida e `corrects` com `event_id`).
- [ ] Atualizar `tests/test_phase04_state_cache.py` para testar `rebuild` com `emit_audit_event=True`.
- [ ] Executar as sondas de QA (`probe_phase04.py` e `probe_phase04b.py`).
- [ ] Rodar suíte completa (`250+` testes verdes) e testes de fronteira.

---

## 4. Portões de Qualidade (Gates)

- **Gate G0 (Arquitetura e Limites):** Nenhum arquivo com 300+ linhas; nenhuma violação de fronteira entre `contracts/` e outras camadas.
- **Gate G1 (Contratos e Tipos):** `contracts.context.HolderRef is resources.knowledge.model.HolderRef`.
- **Gate G2 (Dados Canônicos):** Zero `AttributeError` em NPCs com relacionamentos; zero descarte silencioso de conhecimento com proveniência.
- **Gate G3 (Determinismo de Cache):** `rebuild` com auditoria não gera contexto obsoleto nem loop de reconstrução.
- **Gate G4 (Suíte e Regressão):** 100% dos testes verdes sem fixtures sintéticas de conveniência.

---

## 5. Checagem de Constituição e Diretrizes

- **Zero Emojis:** Todos os módulos de código, mensagens e artefatos de documentação não possuem emojis.
- **Anti-puppeteering:** O fluxo de contexto não antecipa nem prescreve decisões mecânicas ou narrativas do jogador.
- **SSOT Markdown:** Os arquivos Markdown continuam sendo a fonte soberana de persistência e projeções; o cache `estado.json` é estritamente derivado e descartável.
- **Lazy Senior Dev (Ponytail):** Soluções concisas, reutilização das estruturas de domínio existentes (como `ProvenanceRef` e `RelationalVector` da Fase 03), sem camadas de abstração desnecessárias.
