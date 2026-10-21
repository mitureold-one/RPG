# Feature Specification: P1 — Eliminação de Duplicação & Redução de Carga Neural

**Feature Name**: `eliminate-duplication-p1`  
**Status**: Draft  
**Created**: 2026-10-21  
**Target Backlog Phase**: P1 (Deduplication & Cognitive Load Reduction)

---

## 1. Executive Summary & Problem Statement

O ecossistema RPGPRO atualmente sofre de **alta redundância textual e sobrecarga de contexto** (neural load), decorrente de práticas defensivas de engenharia de prompt onde as mesmas diretrizes foram repetidas em múltiplos arquivos estáticos (`AGENTS.md`, `SKILL.md`, `references/1_turn_discipline_and_prose.md`, `references/3_campaign_crud_and_state.md`, `templates/regras.template.md` e nos arquivos `regras.md` de cada campanha ativa).

Essa dispersão gera quatro problemas arquiteturais graves:
1. **Concorrência e Inconsistência de Mandatos de Prosa**: Quando regras de prosa são redigidas em `AGENTS.md`, na `SKILL.md` e em `council/writer.py`, qualquer evolução de estilo ou ajuste em modificadores de cena (`--scene-type`) compete com regras estáticas herdadas no contexto global. O payload dinâmico injetado deterministamente por `lazy_turn.py prepare` (`step_3_writer_mandate`) deve ser a autoridade única que vence em tempo de execução.
2. **`AGENTS.md` Hipertrofiado**: Com mais de 70 linhas descrevendo minuciosamente o loop de turnos, detalhes de dados, diretrizes de prosa e formatação de cabeçalho, o arquivo é injetado como regra de sistema em absolutamente todas as mensagens, consumindo tokens desnecessários e competindo com a atenção do modelo.
3. **Duplicação de Comandos de Relógios e Fila de Cenas**: O Módulo 3 (`references/3_campaign_crud_and_state.md`) repete blocos inteiros de comandos CLI de `clock` e `plan` que são de responsabilidade estratégica exclusiva da skill `rpg-showrunner`, violando o princípio de SSOT (*Single Source of Truth*).
4. **Escada Universal de DC Replicada em Todas as Campanhas**: Todas as 3 campanhas ativas e o template de regras repetem de forma idêntica a escala universal de DC (10/15/20/25), que é uma regra invariante de Grau 1 (Framework Universal) e pertence ao ruleset central, e não à diegese de cada campanha (Grau 2).

Esta especificação P1 define a refatoração para eliminar essas duplicatas, transformando o `AGENTS.md` em um roteador conciso (máximo 15 linhas), consolidando a autoridade de escrita no payload dinâmico `step_3_writer_mandate`, delegando o uso operacional de relógios/arcos ao Showrunner e centralizando a escada de DC no ruleset universal.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Inicialização Limpa de Turno com Roteador Minimalista
* **As a** Game Master agent processando mensagens e comandos do jogador,
* **I want** o arquivo soberano `AGENTS.md` restrito a no máximo 15 linhas como um roteador de campanha, precedência e acionamento do engine,
* **So that** o consumo fixo de tokens de sistema seja reduzido em mais de 70% e não haja poluição com regras de prosa no nível raiz.
* **Acceptance Criteria**:
  - `AGENTS.md` possui no máximo 15 linhas de conteúdo efetivo.
  - Define exclusivamente: precedência soberana de regras (Graus 1 a 3), identificação de campanha ativa, roteamento para as skills (`rpg-narrative-engine` e `rpg-showrunner`) e o ciclo básico invariável (`prepare` -> obedeça `step_3_writer_mandate` -> `commit`).
  - Nenhuma regra detalhada de prosa (ex: proibição de tags de roteiro, cabeçalho canônico detalhado, 4 batidas dramáticas, listas de exemplos) permanece em `AGENTS.md`.

### User Scenario 2: Obediência Determinística ao Mandato Dinâmico de Escrita
* **As a** redator literário gerando a narrativa de uma cena (seja padrão, interlúdio, dossiê, timeskip, prólogo, etc.),
* **I want** que as instruções de formatação de prosa venham diretamente do payload retornado pelo `lazy_turn.py prepare` (`step_3_writer_mandate`),
* **So that** a prosa se adapte contextualmente e deterministicamente ao modo e tipo de cena sem contradições entre documentações estáticas e código.
* **Acceptance Criteria**:
  - `rpg-narrative-engine/SKILL.md` e referências passam a instruir: *"Obedeça estritamente a `step_3_writer_mandate` retornado no JSON de preparação"*.
  - A documentação estática preserva apenas o racional (*por que* essa estrutura é usada) e os anti-padrões inegociáveis (anti-puppeteering, zero emojis, zero roteiro teatral).
  - O conteúdo de `council/writer.py` (`MODE_PROSE_MANDATES` e `STRUCTURAL_SCENE_MANDATES`) é a autoridade canônica soberana do estilo literário.

### User Scenario 3: Divisão Clara de Governança entre Showrunner e Módulo 3
* **As a** desenvolvedor ou agente consultando as regras de estado da campanha,
* **I want** que `rpg-showrunner` seja a única autoridade documentando a execução prática dos comandos de macro-trama (`lazy_turn.py plan`, `clock`, `arc`), enquanto o Módulo 3 (`references/3_campaign_crud_and_state.md`) documenta apenas a anatomia e schema das seções do `diario.md`,
* **So that** não existam blocos concorrentes de exemplos de comandos duplicados entre as skills.
* **Acceptance Criteria**:
  - As seções 4 e 6 de `references/3_campaign_crud_and_state.md` não contêm blocos redundantes de comandos CLI de `lazy_turn.py clock` e `lazy_turn.py plan`.
  - Módulo 3 descreve apenas o schema Markdown em `diario.md` (formato de relógios ativos, fila de cenas e histórico) e aponta expressamente a governança de uso para o `rpg-showrunner`.

### User Scenario 4: Desacoplamento da Escada de DC das Campanhas
* **As a** criador ou jogador de campanhas no RPGPRO,
* **I want** que a escada canônica universal de dificuldades (DC 10 Fácil, 15 Média, 20 Difícil, 25 Extrema) resida no ruleset universal do Framework (Grau 1),
* **So that** os arquivos `regras.md` de campanhas contenham apenas regras diegéticas locais (Grau 2), economia de recursos específicos e eventuais *overrides* declarados.
* **Acceptance Criteria**:
  - Os blocos genéricos repetidos de DC 10/15/20/25 são removidos de `campaigns/dinastia_cinzas/regras.md`, `campaigns/imperio_valiria/regras.md` e `campaigns/perpetuos_terra_incognita/regras.md`.
  - O template `templates/regras.template.md` é atualizado para indicar que a escada de DC padrão é herdada do motor universal, documentando apenas o formato para declaração de overrides diegéticos.
  - A autoridade canônica da tabela de DC permanece em `references/2_dice_engine_and_arbitration.md` e no código universal (`council/gm.py` / `council/helpers.py`).

---

## 3. Functional Requirements

### 3.1 Roteador Raiz Minimalista (`AGENTS.md`)
* **FR-01**: `AGENTS.md` deve ser reduzido para no máximo 15 linhas totais.
* **FR-02**: O conteúdo de `AGENTS.md` deve cobrir exclusivamente:
  1. Declaração do orquestrador e raiz do workspace.
  2. Hierarquia soberana simplificada de 3 Graus (Grau 1: Motor/Universal, Grau 2: Campanha/Diegese, Grau 3: Personagens/Psicologia).
  3. Roteamento de campanha: detecção da pasta em `campaigns/`.
  4. Roteamento de skills: `rpg-narrative-engine` para o loop de turnos; `rpg-showrunner` sob demanda para macro-trama.
  5. Invariante do loop de turno: `prepare` -> execução obedecendo `step_3_writer_mandate` -> `commit`.

### 3.2 Soberania do Payload Dinâmico de Prosa
* **FR-03**: Em `rpg-narrative-engine/SKILL.md` e `references/1_turn_discipline_and_prose.md`, as regras exaustivas de redação devem ser refatoradas para delegar a autoridade ao campo `step_3_writer_mandate` emitido por `lazy_turn.py prepare`.
* **FR-04**: O texto estático deve reter exclusivamente:
  1. A justificativa arquitetural (injeção determinística e sensível a contexto/cena).
  2. Os anti-padrões inegociáveis de alto nível: Anti-Puppeteering, Zero Emojis, Zero Formato Teatral (`Nome: Fala`), Gancho Dramático Acionável sem perguntas fora do personagem.
* **FR-05**: O arquivo `council/writer.py` permanece como a SSOT executável para mandatos de modo (`MODE_PROSE_MANDATES`) e de cena (`STRUCTURAL_SCENE_MANDATES`).

### 3.3 Separação de Responsabilidade no Módulo 3
* **FR-06**: `references/3_campaign_crud_and_state.md` deve ser limpo de todos os blocos exemplares de CLI para relógios (`lazy_turn.py clock`) e planejamento de fila de cenas (`lazy_turn.py plan`).
* **FR-07**: `references/3_campaign_crud_and_state.md` deve manter estritamente a especificação de schema Markdown para `ficha.md`, `diario.md`, `npcs.md`, `mundo.md` e `regras.md`.
* **FR-08**: A execução operacional e as diretrizes de quando e como utilizar relógios e fila de cenas devem conter link explícito apontando para `rpg-showrunner`.

### 3.4 Extração da Escada de DC para o Ruleset Universal
* **FR-09**: As seções `## 1. Escala de Classes de Dificuldade (DC)` redundantes devem ser removidas dos três arquivos de campanha:
  - `campaigns/dinastia_cinzas/regras.md`
  - `campaigns/imperio_valiria/regras.md`
  - `campaigns/perpetuos_terra_incognita/regras.md`
* **FR-10**: `templates/regras.template.md` deve ser atualizado para não forçar a duplicação dos 4 exemplos genéricos de DC, passando a conter nota de herança da escala canônica e seção opcional de overrides diegéticos.
* **FR-11**: `council/helpers.py` deve atualizar a geração de novas campanhas (`init-campaign`) para refletir a nova estrutura de `regras.md`, eliminando as chaves de template `{{EXEMPLO_DC_10}}` a `{{EXEMPLO_DC_25}}` ou adaptando-as para declaração exclusiva de exceções de cenário.

---

## 4. Success Criteria

* **SC-01 (Concisão do Roteador)**: O arquivo `AGENTS.md` possui contagem de linhas $\le 15$, eliminando completamente parágrafos de regras de redação de prosa.
* **SC-02 (Redução de Carga Neural)**: O total de linhas de regras de sistema persistentes carregadas em cada turno decai de 72 linhas para $\le 15$ linhas (redução $\ge 75\%$).
* **SC-03 (SSOT Dinâmico de Prosa)**: Nenhuma diretiva textual em `SKILL.md` contradiz ou replica exaustivamente os mandatos de cena de `council/writer.py`; o modelo reconhece `step_3_writer_mandate` como autoridade única de estilo de prosa.
* **SC-04 (Zero Comandos Duplicados)**: Não existem blocos repetidos de comandos `lazy_turn.py clock` e `lazy_turn.py plan` entre `references/3_campaign_crud_and_state.md` e `rpg-showrunner/SKILL.md`.
* **SC-05 (Higienização de Campanhas)**: Nenhum dos arquivos `regras.md` das 3 campanhas ativas repete a escada padrão DC 10/15/20/25; todos declaram apenas economia de recursos locais, regras diegéticas e eventuais overrides.
* **SC-06 (Conformidade dos Contratos de Teste)**: A suíte de testes de contratos (`tests/test_cli_contracts.py`) e os testes automatizados do repositório executam com 100% de sucesso.

---

## 5. Assumptions & Dependencies

* A CLI `lazy_turn.py prepare` já injeta nativamente o campo `step_3_writer_mandate` a cada turno de jogo, garantindo suporte imediato à transição para payload dinâmico.
* As regras de Grau 1 (Framework Universal) permanecem ancoradas em `references/2_dice_engine_and_arbitration.md` e no módulo de código `council/gm.py`.
* Nenhuma alteração é necessária na estrutura do banco SQLite `ai-memory` ou nos arquivos de estado vivo (`ficha.md` e `diario.md`).
