# Feature Specification: 014 — Remediação dos Bloqueantes P0/P1 e Achados de QA da Fase 04 (Contexto Causal)

**Feature Name**: `fix-phase-04-qa-review`  
**Status**: Draft — especificação de remediação para desbloqueio e homologação da Fase 04.  
**Created**: 2026-10-26  
**Target Backlog Phase**: Fase 04 / R2 (Contexto Causal no `prepare`, Cache Projetado e Consulta Semântica)  
**Base Analisada**: [`specs/013-phase-04-causal-context/qa-review.md`](file:///c:/Users/Konor/Documents/RPGPRO/specs/013-phase-04-causal-context/qa-review.md), [`specs/013-phase-04-causal-context/spec.md`](file:///c:/Users/Konor/Documents/RPGPRO/specs/013-phase-04-causal-context/spec.md), [`EXECUCAO.md`](file:///c:/Users/Konor/Documents/RPGPRO/EXECUCAO.md) (`EX-0033`), [`ARCHITECTURE.md`](file:///c:/Users/Konor/Documents/RPGPRO/ARCHITECTURE.md), [`ROADMAP.md`](file:///c:/Users/Konor/Documents/RPGPRO/ROADMAP.md).

---

## 1. Executive Summary & Problem Statement

Na auditoria independente de QA da Fase 04 (`specs/013-phase-04-causal-context/qa-review.md`), a implementação inicial foi **reprovada**. Embora a suíte unitária tenha reportado 249 testes passando, foi demonstrado que os testes usaram fixtures não canônicas e atalhos artificiais que mascararam falhas graves de execução em dados reais da Fase 02 e Fase 03. Foram identificados **2 bloqueantes P0**, **5 bloqueantes P1** e **8 achados P2**:

1. **P0-1 (Descarte Silencioso de Conhecimento Canônico com Proveniência)**: `_dict_to_knowledge_record` instancia `ProvenanceRef` com atributos inexistentes (`source_event_id`, `method`, `source_agent`, `reliability`), enquanto o modelo canônico da Fase 03 exige `(source_type, source_id, channel, acquired_at, acquired_at_sort, confidence)`. O `TypeError` resultante é engolido por um `except Exception: return None`, descartando 100% dos registros de conhecimento canônicos adquiridos.
2. **P0-2 (Falha Fatal ao Pontuar Relevância de NPCs com Relacionamentos)**: `score_npc` em `resources/context/relevance.py` invoca `.get("rivalry", 0)` assumindo que `relationships` é um dicionário, quando `estado.json` o serializa canonicamente como `list[dict]`, provocando `AttributeError` e abortando o `prepare` em qualquer campanha com relacionamentos ativos.
3. **P1-1 (Loop Infinito de Staleness no Cache `estado.json` Pós-Rebuild)**: `rebuild_projections` padrão emite o evento de auditoria `projection.rebuilt`. Como `StateProjector` filtrava eventos de projeção ao computar `last_seq`, o arquivo `estado.json` ficava defasado em relação ao `store.last_seq`, fazendo com que todo `prepare` subsequente considerasse o cache obsoleto e disparasse reconstruções infinitas.
4. **P1-2 (Correções Canônicas por `event_id` não Invalidam Fatos)**: `FactsCausalProvider` aceita apenas `corrects` como lista de inteiros (`seq`), enquanto a Fase 02 especifica canonicamente identificadores de evento no formato string `evt_<ulid>`. Com isso, fatos retificados continuavam ativos no contexto causal.
5. **P1-3 (Duplicação e Incompatibilidade de `HolderRef` no Serviço de Query)**: Existência de duas classes `HolderRef` incompatíveis (`contracts.context.HolderRef` e `resources.knowledge.model.HolderRef`), quebrando a igualdade de chave e a recuperação de claims no `ContextQueryService`, agravado pela resolução padrão da audiência `protagonist` como string literal em vez do nome real do protagonista.
6. **P1-4 (Regressão de Gameplay Legado e Filtros de Missão)**: O fallback de seleção de atores focais em `resolve_scene_actors` deixou de priorizar os 2 primeiros NPCs presentes na cena quando ausentes campos de vontade/plano, e `build_quest_context` deixou de filtrar missões por status ativo (`ACTIVE`), poluindo o briefing com missões já concluídas.
7. **P1-5 (Suíte de Testes Alienada do Modelo Canônico)**: Ausência de fixtures canônicas nos testes unitários e de integração da Fase 04, gerando falsa confiança ao testar dados artificiais.

### 1.1 Objetivo da Especificação
Estabelecer os requisitos funcionais, cenários de aceitação e critérios mensuráveis para sanar todos os apontamentos P0 e P1 (e os P2s críticos de plano de facção, universo de conhecimento do GM e validação de schema do cache), garantindo que a Fase 04 opere de ponta a ponta sobre eventos e estruturas 100% canônicas.

---

## 2. User Scenarios & Testing

### User Scenario 1: Ingestão e Consulta de Conhecimento Canônico com Proveniência (P0-1 & P1-3)
* **As a** Mestre de Jogo ou Narrador executando `prepare` ou `query claim`,
* **I want** que todos os registros de conhecimento (`knowledge.acquired`) persistidos no histórico com metadados canônicos de proveniência sejam lidos, validados e consultáveis sem descarte silencioso,
* **So that** as alegações e segredos conhecidos pelos atores em cena apareçam no contexto causal respeitando estritamente a audiência epistêmica.
* **Acceptance Scenarios**:
  1. **Given** um evento canônico `knowledge.acquired` contendo `provenance` com campos `(source_type, source_id, channel, acquired_at, acquired_at_sort, confidence)`, **When** o `prepare` ou `query claim` é executado, **Then** o registro é reconstruído com sucesso, nenhum `TypeError` é suprimido, e as claims ativas são retornadas sem descarte.
  2. **Given** uma instância de `HolderRef`, **When** utilizada na camada de aplicação, contratos ou modelo de conhecimento, **Then** a classe de referência de detentor é unificada e suas instâncias comparam como iguais quando possuem o mesmo `holder_type` e `holder_id`.
  3. **Given** uma consulta via CLI `lazy_turn.py query claim <claim_id> --audience protagonist`, **When** executada para uma campanha com ficha de protagonista válida, **Then** a audiência é mapeada para o identificador real do protagonista (ex: `Aemon Targaryen`) e a alegação conhecida é reportada como `known`.

### User Scenario 2: Cálculo Robusto de Relevância de NPCs com Relacionamentos (P0-2)
* **As a** motor de arbitragem e montagem de contexto,
* **I want** que o cálculo de pontuação de NPCs tolere tanto relacionamentos estruturados como lista de dicionários (`list[dict]`) quanto como dicionários indexados (`dict`),
* **So that** o cálculo de relevância nunca falhe com `AttributeError` e priorize corretamente NPCs com rivalidades ou alianças com o protagonista.
* **Acceptance Scenarios**:
  1. **Given** um estado projetado onde um NPC possui `relationships` serializado como `list[dict]` (formato padrão do `NpcState` da Fase 03), **When** `score_npc` avalia o NPC para a cena atual, **Then** o vetor de relacionamento com o protagonista é extraído corretamente e a pontuação de relevância reflete o valor de rivalidade/aliança sem exceção de tempo de execução.
  2. **Given** um NPC presente na cena com vetor relacional contendo rivalidade com o protagonista, **When** `prepare` constrói o pacote de contexto, **Then** o NPC recebe pontuação condizente e é incluído no elenco focal ou causal da cena.

### User Scenario 3: Estabilidade do Cache `estado.json` e Tolerância a Eventos de Auditoria (P1-1 & P2-8)
* **As a** operador executando o fluxo completo de jogo (`rebuild` seguido de `prepare`),
* **I want** que o cache de estado derivado (`estado.json`) permaneça sincronizado e não entre em ciclo contínuo de invalidação após reconstruções que emitem `projection.rebuilt`,
* **So that** chamadas sucessivas de `prepare` desfrutem da leitura rápida em memória sem reexecutar desnecessariamente projetores completos nem marcar o contexto como obsoleto.
* **Acceptance Scenarios**:
  1. **Given** uma campanha que sofreu `rebuild` com emissão do evento canônico de auditoria `projection.rebuilt`, **When** `prepare` é executado em seguida, **Then** `ContextStateViewImpl.load` reconhece o cache como fresco (`stale=False`), `last_seq` coincide com a sequência do log e nenhum rebuild secundário é disparado.
  2. **Given** um arquivo `estado.json` com `schema_version` divergente da versão suportada pelo motor, **When** o cache é lido, **Then** o sistema detecta incompatibilidade de schema, invalida o cache de forma controlada e executa reconstrução limpa.

### User Scenario 4: Invalidação de Fatos por Identificador de Evento (P1-2)
* **As a** Mestre de Jogo aplicando correções causais a fatos narrativos passados,
* **I want** que o provedor causal de fatos (`FactsCausalProvider`) identifique e anule fatos retificados cujos identificadores de evento (`event_id` no formato `evt_<ulid>`) constem no campo `corrects` do evento compensatório,
* **So that** fatos contraditos ou corrigidos não apareçam como vigentes na montagem do contexto narrativo.
* **Acceptance Scenarios**:
  1. **Given** um evento que estabeleceu um fato e um evento subsequente de correção cujo payload traz `corrects: ["evt_01J..."]`, **When** o contexto de fatos recentes é computado pelo `prepare`, **Then** o fato referenciado pelo `event_id` corrigido é suprimido da lista de fatos vigentes.
  2. **Given** a projeção de eventos recentes em `StateProjector`, **When** os eventos recentes são compilados para `recent_events`, **Then** cada item contém obrigatoriamente seu `event_id` além do número de sequência `seq`.

### User Scenario 5: Preservação do Comportamento de Cena e Filtro de Missões (P1-4)
* **As a** Mestre de Jogo consumindo as orientações do `prepare`,
* **I want** que o elenco focal da cena preserve o comportamento de seleção dos NPCs presentes e que o sumário de missões liste exclusivamente objetivos ativos,
* **So that** o `step_2_narrator_briefing` e os mandatos narrativos mantenham a consistência da narrativa sem poluição por objetivos já encerrados.
* **Acceptance Scenarios**:
  1. **Given** uma cena com múltiplos NPCs presentes onde nenhum possui metas ou vontades complexas preenchidas, **When** `resolve_scene_actors` determina os atores focais, **Then** os dois primeiros NPCs presentes são mantidos como atores focais por fallback, garantindo que o briefing não fique sem antagonistas/interlocutores.
  2. **Given** uma campanha com missões ativas e concluídas (`COMPLETED`), **When** `build_quest_context` gera as diretrizes de missão, **Then** apenas missões com `status == "ACTIVE"` são incluídas nas pressões da cena, omitindo missões arquivadas.

### User Scenario 6: Suíte de Aceitação Canônica e Sondas de Verificação (P1-5)
* **As a** engenheiro de QA e desenvolvedor sustentando a plataforma,
* **I want** que todos os testes da Fase 04 utilizem geradores e fixtures de eventos idênticos aos emitidos pelo motor oficial nas Fases 02 e 03,
* **So that** a suíte verde reflita com fidelidade a integridade da arquitetura de produção.
* **Acceptance Scenarios**:
  1. **Given** a suíte de testes de integração da Fase 04 (`tests/test_phase04_causal_context.py`), **When** executada, **Then** nenhum fixture omite campos obrigatórios de proveniência nem utiliza tipos fora de contrato (como inteiros em `corrects`).
  2. **Given** os scripts de sonda adversarial desenvolvidos durante o QA (`probe_phase04.py` e `probe_phase04b.py`), **When** executados contra o motor remediado, **Then** todas as verificações de cache, conhecimento, relacionamentos e correções passam sem erro.

### Edge Cases
* **Conhecimento sem proveniência legítima em legado**: Se um evento antigo inválido for encontrado, o erro deve ser registrado de forma audível com diagnóstico explícito, sem derrubar silenciosamente registros válidos adjacentes.
* **Relacionamento vazio ou nulo**: NPCs sem nenhum relacionamento declarado devem ser pontuados com vetor neutro (zero) sem falhas.
* **Correções em cadeia**: Quando um evento corrige um evento anterior que por sua vez corrigia outro, a invalidação causal em `FactsCausalProvider` deve aplicar a exclusão de todos os IDs de eventos afetados.

---

## 3. Functional Requirements

* **FR-FIX-01 (Unificação de `HolderRef` e Reconstrução Estrita de Proveniência)**: A entidade `HolderRef` DEVE ser unificada em um único local canônico em `contracts/context.py` (ou reexportada deterministicamente), e a função `_dict_to_knowledge_record` DEVE reconstruir `ProvenanceRef` utilizando estritamente a assinatura canônica da Fase 03 (`source_type`, `source_id`, `channel`, `acquired_at`, `acquired_at_sort`, `confidence`), sem mascarar exceções inesperadas.
* **FR-FIX-02 (Normalização de Vetores Relacionais de NPCs)**: O resolvedor de relevância `score_npc` DEVE normalizar `relationships` independentemente de estar serializado como `list[dict]` ou `dict`, extraindo a atitude relacional com o protagonista com suporte a chaves `rivalry`, `affinity` e `trust`.
* **FR-FIX-03 (Alinhamento de Sequência de Auditoria e Cache `estado.json`)**: O `StateProjector` e o gerenciador de cache `ContextStateViewImpl` DEVEM registrar e validar `last_seq` considerando o log de eventos total (incluindo eventos de auditoria como `projection.rebuilt`) para evitar loops de staleness pós-rebuild, validando também `schema_version`.
* **FR-FIX-04 (Resolução Causal de Correções por `event_id`)**: O `StateProjector` DEVE incluir `event_id` nos dicionários de `recent_events`, e `FactsCausalProvider` DEVE suportar a checagem de exclusão de fatos através de identificadores canônicos do tipo string (`evt_<ulid>`) presentes em `corrects`.
* **FR-FIX-05 (Resolução de Audiência Real no CLI `query`)**: O serviço de consulta de contexto `ContextQueryService` e a CLI `query` DEVEM resolver a audiência `protagonist` utilizando o nome real do protagonista extraído da campanha em vez da string literal `"protagonist"`.
* **FR-FIX-06 (Restauração do Fallback de Atores Focais e Filtro de Missões)**: O resolvedor `resolve_scene_actors` DEVE restabelecer o fallback legado de seleção dos 2 primeiros NPCs presentes na cena quando nenhum critério avançado de vontade/plano for atendido, e `build_quest_context` DEVE filtrar rigorosamente apenas missões com `status == "ACTIVE"`.
* **FR-FIX-07 (Suporte a Planos Ativos de Facção — P2-1)**: O cálculo de relevância de facções `score_faction` DEVE inspecionar a chave `active_plan` (serializada pelo estado canônico) para conceder o modificador de `plano_iminente`.
* **FR-FIX-08 (Adequação da Suíte de Testes da Fase 04)**: Os testes em `tests/test_phase04_causal_context.py` e testes correlatos DEVEM ser atualizados para usar exclusivamente fixtures com proveniência completa, correções por `event_id`, e incluir cenários específicos para relacionamentos em `list[dict]` e rebuild com evento de auditoria.

---

## 4. Key Entities

* **`HolderRef`**: Estrutura unificada de referência epistêmica a um sujeito cognoscente (`holder_type: "player" | "protagonist" | "npc" | "faction"`, `holder_id: str`).
* **`ProvenanceRef`**: Registro canônico imutável de rastreabilidade de como o conhecimento foi obtido (`source_type`, `source_id`, `channel`, `acquired_at`, `acquired_at_sort`, `confidence`).
* **`StateCacheSnapshot`**: Representação persistida em `estado.json` contendo `schema_version`, `last_seq`, `npcs`, `factions`, `quests`, `clocks` e `recent_events` (com `event_id` e `seq`).

---

## 5. Assumptions

* A estrutura dos eventos emitidos nas Fases 02 e 03 é imutável e soberana; a Fase 04 deve se adequar estritamente aos contratos canônicos já estabelecidos.
* O limite arquitetural de 300 linhas por módulo deve continuar sendo respeitado em todos os arquivos modificados ou novos.
* Nenhuma quebra de retrocompatibilidade do formato do `prepare` (contrato JSON consumido pelo writer) é permitida.

---

## 6. Success Criteria

* **SC-01**: Execução do comando `prepare` e da CLI `query` sobre campanhas contendo eventos de conhecimento com proveniência canônica sem nenhuma exceção e sem descarte de registros (`100%` de recuperação de conhecimento válido).
* **SC-02**: Execução sem erros do `prepare` em campanhas com NPCs que possuem listas de relacionamentos e cálculo correto de relevância relacional.
* **SC-03**: Inexistência de loops de reconstrução de cache: após `lazy_turn.py rebuild` (com `emit_audit_event=True`), chamadas subsequentes de `prepare` devem carregar o cache com `stale=False`.
* **SC-04**: Anulação completa de fatos retificados por correções causais baseadas em `event_id` no contexto entregue ao narrador.
* **SC-05**: Preservação dos comportamentos legados de seleção focal (mínimo de 2 NPCs presentes em cena por fallback) e supressão de missões concluídas no briefing de cena.
* **SC-06**: Suíte completa de testes passando (`250+` testes verdes), sem nenhuma fixture artificial e com aprovação de 100% das sondas adversariais do QA.
