# Feature Specification: 011 — Fechamento dos 5 Achados P2 do QA da Fase 02/R1

**Feature Name**: `close-phase02-qa-p2`  
**Status**: Ready for Planning  
**Created**: 2026-10-24  
**Target Backlog Phase**: Fase 02 / R1 (Congelamento Definitivo do Baseline Causal e Aprovação Total de QA)  
**Base Analisada**: [`specs/010-phase-02-causal-history/qa-review.md`](../010-phase-02-causal-history/qa-review.md), [`specs/010-phase-02-causal-history/spec.md`](../010-phase-02-causal-history/spec.md), [`EXECUCAO.md`](../../EXECUCAO.md) (`EX-0017` e `EX-0018`), [`ARCHITECTURE.md`](../../ARCHITECTURE.md), [`ROADMAP.md`](../../ROADMAP.md).

---

## 1. Executive Summary & Problem Statement

Na reverificação de QA da Fase 02/R1 (`EX-0017` e `EX-0018`, commit `d18e3b9`), todos os bloqueantes críticos (**P0** e **P1**, incluindo `P1-A` de idempotência com `expected_last_seq` e `P1-B` de subcampos estruturados de NPCs) foram sanados com **206 testes verdes**. Contudo, o QA reteve a aprovação plena para congelamento definitivo da Fase 02 devido a **5 achados P2 abertos** em [`qa-review.md`](../010-phase-02-causal-history/qa-review.md):

1. **P2-1 (Perda de `diario.md` impede descoberta e reconstrução)**: Quando `diario.md` na raiz da campanha é perdido ou removido acidentalmente, a localização da campanha falha com erro fatal mesmo que o histórico imutável (`events/`) e as configurações (`regras.md`, `mundo.md`) existam, impedindo que o operador execute `rebuild` para recuperar o diário.
2. **P2-2 (Snapshots completos em `meta` substituem derivação por eventos)**: Os eventos de turno e de comando carregam cópias integrais dos arquivos Markdown em `meta` (`diario_after`, `ficha_after`, `npcs_after`), fazendo com que a reconstrução (`rebuild`) apenas reaplique textos prontos em vez de derivar o estado real a partir dos payloads semânticos dos eventos registrados.
3. **P2-3 (Compensação e reavaliação causal limitadas)**: O mecanismo de correção (`correct`) emite eventos compensatórios apenas para XP, ficha e reputação de facção, deixando de fora correções de relógios (`clock`), missões (`quest`) e arcos (`arc`), além de registrar eventos dependentes afetados sem recomputar automaticamente o estado projetado após a compensação.
4. **P2-4 (Limites de tamanho de módulo e pureza de camadas)**: Ainda restam módulos acima da meta arquitetural de 300 linhas (`application/commit.py`, `adapters/persistence/event_store.py`, `council/reviewer.py`) e acoplamentos diretos entre camadas que precisam respeitar estritamente as fronteiras declaradas na arquitetura.
5. **P2-5 (Lacunas na suíte de testes e alinhamento documental)**: A suíte atual (206 testes) e a documentação canônica ainda não cobrem explicitamente a recuperação de `diario.md` ausente via `rebuild`, a derivação pura de projeções sem blobs em `meta` e as compensações causais de relógio, missão e arco.

### 1.1 Objetivo da Especificação
Definir os requisitos funcionais, cenários de aceite e critérios mensuráveis para zerar os **5 achados P2**, garantindo que o histórico de eventos seja a única fonte de verdade auto-suficiente e obtendo a aprovação incondicional do QA para o congelamento da Fase 02/R1.

---

## 2. User Scenarios & Testing

### User Scenario 1: Recuperação de Campanha após Perda de `diario.md` (P2-1)
* **As a** Mestre de Jogo ou operador do sistema enfrentando corrupção ou exclusão acidental de arquivos Markdown na raiz da campanha,
* **I want** que o comando `rebuild` consiga localizar a campanha a partir do seu histórico de eventos (`events/`) e configurações (`regras.md`/`mundo.md`) mesmo quando `diario.md`, `ficha.md` ou `npcs.md` não existirem na raiz,
* **So that** qualquer projeção perdida seja integralmente restaurada a partir do log append-only sem intervenção manual.
* **Acceptance Scenarios**:
  1. **Given** uma campanha válida com histórico de eventos em `events/`, **When** `diario.md` é removido da raiz e o operador executa `rebuild`, **Then** o sistema localiza a campanha pelo diretório e log de eventos, reconstrói `diario.md`, `ficha.md` e `npcs.md` na raiz e em `projections/`, e retorna sucesso.
  2. **Given** uma campanha sem `diario.md` e também sem histórico de eventos (`events/` ausente ou vazio), **When** qualquer comando é executado, **Then** o sistema continua falhando de forma clara e determinística informando corrupção da campanha.
  3. **Given** que `diario.md` foi restaurado via `rebuild`, **When** o comando `review` é executado em seguida, **Then** o status do SSOT reportado é `CLEAN` e o conteúdo de `diario.md` é byte-idêntico ao estado anterior à remoção.

### User Scenario 2: Reconstrução Pura Derivada de Eventos sem Blobs em `meta` (P2-2)
* **As a** auditor de integridade causal,
* **I want** que os projetores de `diario.md`, `ficha.md` e `npcs.md` derivem cada seção exclusivamente dos payloads dos eventos canônicos (e do baseline inicial da campanha), sem depender de cópias completas (`diario_after`, `ficha_after`, `npcs_after`) embutidas em `meta`,
* **So that** o log de eventos represente verdadeiramente todas as transformações de estado e que qualquer compensação ou correção no histórico reflita imediatamente no estado reconstruído.
* **Acceptance Scenarios**:
  1. **Given** um turno com mutações de cena, vitais, habilidades, itens, marcos, relógios, missões, progressão de XP, reputação de facções, fila de cenas, arco e NPCs, **When** o turno é confirmado (`commit`), **Then** nenhum evento gravado no log contém chaves de snapshot bruto (`diario_after`, `ficha_after`, `npcs_after`) em `meta`.
  2. **Given** uma sequência de comandos (`clock`, `quest`, `progress`, `faction`, `plan`, `arc`, `upsert-npc`) e turnos (`commit`), **When** `rebuild --force` é executado do zero, **Then** os arquivos `diario.md`, `ficha.md` e `npcs.md` reconstruídos pelos projetores preservam todas as seções canônicas e produzem hashes idênticos entre a raiz e `projections/`.

### User Scenario 3: Compensação Causal de Relógios, Missões e Arcos com Reprojeção Automática (P2-3)
* **As a** Mestre de Jogo ou Showrunner corrigindo um erro de arbitragem passado,
* **I want** emitir correções causais (`correct`) que compensem também avanços/estados de relógios, status de missões e estado de arcos narrativos, atualizando automaticamente as projeções da campanha após a compensação,
* **So that** nenhum recurso de jogo fique sem mecanismo de retificação append-only e o estado atual reflita imediatamente a correção aplicada.
* **Acceptance Scenarios**:
  1. **Given** um evento passado que avançou indevidamente um relógio ou alterou uma missão/arco, **When** o operador executa `correct` especificando a alteração compensatória de relógio, missão ou arco, **Then** o sistema registra `correction.issued`, emite o respectivo evento compensatório (`clock.*`, `quest.*` ou `arc.updated`) + `correction.recomputed`, e atualiza imediatamente as projeções (`diario.md`, `ficha.md`, `npcs.md`).
  2. **Given** uma correção com eventos dependentes na cadeia causal, **When** a compensação é concluída sem contradição insolúvel, **Then** as projeções na raiz e em `projections/` passam a exibir o novo valor compensado sem exigir um `rebuild` manual separado.

### User Scenario 4: Conformidade Estrita de Tamanho de Módulos e Fronteiras de Camadas (P2-4)
* **As a** arquiteto mantendo a sustentabilidade do motor,
* **I want** que todos os módulos de código respeitem os limites de linhas e as regras de dependência unidirecional entre camadas,
* **So that** o congelamento do R1 cumpra integralmente o contrato estrutural definido para o projeto.
* **Acceptance Scenarios**:
  1. **Given** a árvore de código do repositório, **When** a verificação de fronteiras arquiteturais é executada, **Then** os módulos alvo da auditoria (`application/commit.py`, `adapters/persistence/event_store.py`, `council/reviewer.py` e demais pacotes de domínio/aplicação/infraestrutura) respeitam o teto arquitetural acordado e nenhuma camada inferior importa camadas superiores.

### User Scenario 5: Cobertura Executável dos Novos Casos e Sincronização Documental (P2-5)
* **As a** engenheiro de QA homologando o fechamento da Fase 02/R1,
* **I want** testes automatizados cobrindo explicitamente os cenários de perda de `diario.md`, ausência de blobs `*_after`, compensação de relógio/missão/arco e limites arquiteturais, além de documentos canônicos sincronizados,
* **So that** nenhuma regressão futura reabra os itens P2 e a documentação reflita fielmente o estado real do repositório.
* **Acceptance Scenarios**:
  1. **Given** a suíte de testes automatizados, **When** executada integralmente, **Then** todos os testes existentes e os novos testes para P2-1 a P2-4 passam com zero falhas e zero avisos de recursos não fechados.
  2. **Given** os documentos canônicos (`qa-review.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `README.md`, `EXECUCAO.md`), **When** inspecionados após a entrega, **Then** todas as contagens de testes, status de pendências P2 e registros de execução estão consistentes e atualizados.

### Edge Cases
* **Remoção simultânea de múltiplos arquivos projetados (`diario.md`, `ficha.md`, `npcs.md`)**: O `rebuild` deve restaurar todos os três arquivos desde que `events/` contenha pelo menos o evento `campaign.created` e `regras.md` seja válido.
* **Campanha corrompida sem `diario.md` em comandos normais (`prepare`, `commit`, `review`)**: Comandos que leem o estado projetado podem falhar informando que `diario.md` está ausente e orientando o uso de `rebuild`, enquanto `rebuild` (ou descoberta tolerante a projeção ausente) recupera os arquivos sem erro.
* **Compensação de relógio nos limites (`0` ou `max`)**: Um ajuste compensatório negativo em relógio não pode reduzir o contador abaixo de `0`, e se reduzir abaixo de `max` um relógio antes `BREACHED`, deve restaurar seu status para `ACTIVE` (salvo se explicitamente resolvido).
* **Tentativa de repetir correção idêntica de relógio/missão/arco**: Deve ser bloqueada pela regra de idempotência já vigente (`DuplicateBatchError`) sem duplicar o efeito compensatório.

---

## 3. Functional Requirements

* **FR-001 (Descoberta e Rebuild Resiliente sem `diario.md` — P2-1)**: O localizador de campanhas e o fluxo de `rebuild` DEVEM permitir identificar e reconstruir uma campanha válida quando `diario.md` (ou `ficha.md`/`npcs.md`) estiver ausente na raiz, obtendo `schema_version` e metadados a partir do histórico de eventos (`events/`) ou `projections/diario.md` quando disponível.
* **FR-002 (Remoção de Blobs `*_after` em Eventos — P2-2)**: Os construtores de eventos de turno e de comando NÃO DEVEM persistir cópias integrais dos arquivos Markdown (`diario_after`, `ficha_after`, `npcs_after`) no campo `meta` dos novos eventos; toda informação necessária para reconstrução DEVE constar nos payloads tipados dos eventos emitidos.
* **FR-003 (Projetores Completos por Eventos — P2-2)**: Os projetores de `diario.md`, `ficha.md` e `npcs.md` DEVEM aplicar deterministicamente todos os eventos do catálogo v1 (incluindo criação/atualização de arcos, fila de cenas, missões, marcos, habilidades, itens, condições, atributos, vitais, reputação, relógios, NPCs, turnos e correções) sobre o estado inicial de `campaign.created`, produzindo arquivos idênticos na raiz e em `projections/`.
* **FR-004 (Compensação de Relógios, Missões e Arcos — P2-3)**: O serviço de correção causal e a interface CLI `correct` DEVEM suportar alterações compensatórias para relógios (ajuste de avanço/status), missões (ajuste de status/progresso) e arcos narrativos (ajuste de fase/estado), emitindo os eventos correspondentes no mesmo lote atômico de `correction.issued`.
* **FR-005 (Reprojeção Automática Pós-Correção — P2-3)**: Sempre que uma correção causal for registrada (ou resolvida via `--resolve`), o fluxo de aplicação DEVE reexecutar os projetores sobre o log atualizado, garantindo que `diario.md`, `ficha.md` e `npcs.md` na raiz e em `projections/` reflitam imediatamente o estado compensado e a lista de eventos afetados.
* **FR-006 (Adequação de Tamanho de Módulos e Fronteiras — P2-4)**: Os módulos que excedem o limite arquitetural DEVEM ser decompostos em submódulos coesos respeitando o teto de linhas definido para os pacotes do projeto, e as importações entre camadas DEVEM respeitar a direção arquitetural (`interfaces -> application -> domain/resources/contracts/kernel` e `adapters -> contracts/kernel`).
* **FR-007 (Suíte de Testes e Documentação — P2-5)**: A suíte de testes automatizados DEVE incluir casos de teste verificando explicitamente P2-1, P2-2, P2-3 e P2-4, e os documentos canônicos (`qa-review.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `README.md`, `EXECUCAO.md`) DEVEM ser atualizados com as evidências e a nova contagem de testes.

---

## 4. Key Entities

* **Evento Causal (`Event` / `EventDraft`)**: Registro imutável no log cujo `payload` descreve integralmente a transição de domínio, sem depender de snapshots completos de texto em `meta` nos turnos e comandos.
* **Projetor Canônico (`JournalProjector`, `CharacterSheetProjector`, `NpcProjector`)**: Componente determinístico responsável por transformar a sequência de eventos desde `campaign.created` (ou último snapshot oficial em `snapshots/`) na representação exata dos arquivos Markdown do SSOT.
* **Lote de Correção e Compensação (`CorrectionBatch`)**: Conjunto atômico composto por `correction.issued`, zero ou mais eventos compensatórios (`protagonist.progression_changed`, `protagonist.sheet_changed`, `faction.reputation_changed`, `clock.*`, `quest.*`, `arc.updated`) e `correction.recomputed`, seguido de atualização imediata das projeções.

---

## 5. Assumptions

* **Baseline em `campaign.created`**: Mantém-se o baseline inicial dos templates gravado no evento inaugural `campaign.created` (momento zero da campanha) como ponto de partida legítimo dos projetores; o que é eliminado em P2-2 é o atalho de sobrescrever as projeções a cada turno/comando via `diario_after`/`ficha_after`/`npcs_after`.
* **Compatibilidade de leitura com eventos antigos em testes**: Caso algum teste unitário legado forneça mocks sintéticos, os projetores continuam operando normalmente pelo caminho semântico de eventos.
* **Escopo restrito à Fase 02 / R1**: Nenhuma funcionalidade das Fases 03–08 (como IA comportamental autônoma ou SQLite derivado) é antecipada nesta especificação.

---

## 6. Success Criteria

1. **Recuperação Total sem `diario.md` (100%)**: Em 100% das execuções de teste onde `diario.md`, `ficha.md` e/ou `npcs.md` são deletados da raiz de uma campanha com `events/` íntegro, o comando `rebuild` restaura os arquivos sem erro e com hash SHA-256 idêntico ao estado pré-exclusão.
2. **Zero Snapshots Brutos em `meta` de Turnos/Comandos (0 ocorrências)**: 0 eventos emitidos por `commit`, `clock`, `quest`, `progress`, `faction`, `plan`, `arc` ou `upsert-npc` contêm as chaves `diario_after`, `ficha_after` ou `npcs_after` em `meta`, mantendo 100% de igualdade byte a byte entre raiz e `projections/` após `rebuild --force`.
3. **Cobertura Completa de Compensação Causal (6 domínios)**: O comando `correct` compensa e reprojeta deterministicamente alterações nos 6 domínios mutáveis da campanha (XP, ficha/vitais, reputação de facção, relógios, missões e arcos), refletindo a mudança imediatamente nos arquivos Markdown da raiz.
4. **Conformidade Estrutural e de Tamanho (100%)**: 100% dos arquivos monitorados pela suíte de fronteiras arquiteturais respeitam os limites de linhas e regras de importação entre camadas, sem exceções abertas para `commit.py`, `event_store.py` ou `reviewer.py`.
5. **Aprovação da Suíte e Fechamento dos P2 (0 P0/P1/P2 abertos)**: 100% da suíte de testes automatizados passa sem erros e os 5 itens P2 constam como `Corrigido` com evidência verificável para aprovação final do QA.
