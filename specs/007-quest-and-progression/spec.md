# Feature Specification: 007 — Sistema de Missões e Sistema de Progressão (XP)

**Feature Name**: `quest-and-progression`  
**Status**: Ready for Planning  
**Created**: 2026-10-21  
**Updated**: 2026-10-22 (Adição da Avaliação e Requisitos de Interação com Relógios)  
**Target Backlog Phase**: P4 (Fase 1: Fundação e Concessão; Fase 2: Gasto e Rigor)

---

## 1. Executive Summary & Problem Statement

O ecossistema RPGPRO estabelece como diretriz soberana que a fidelidade e a integridade de uma crônica de RPG não devem depender da memória estocástica ou da complacência de Modelos de Linguagem:
> *"Uma regra, um único dono textual, um único ponto de enforcement no código. O que não possui enforcement é guideline e não deve fingir ser código."*

Embora as fases P0–P3 tenham blindado o CLI, eliminado duplicatas nas skills, desacoplado a mecânica matemática em `rulesets/` e instituído lints e testes de fronteira determinísticos, o motor opera com uma assimetria fundamental: **ele narra com excelência o presente da cena, mas não possui economia de progresso nem gramática de objetivos**.

### 1.1 O que o motor já cobre (Invariantes a Preservar)
* **Loop de Turno**: `lazy_turn.py prepare` → elaboração literária → `lazy_turn.py commit`.
* **SSOT em 5 Arquivos Markdown**: `diario.md`, `ficha.md`, `npcs.md`, `mundo.md`, `regras.md`.
* **Estruturas Narrativas**: Relógios de facção (`parse_clocks_from_diario`), arco dramático (`update_arc_in_diario`), marcos futuros (`parse_plot_from_diario`).
* **Ruleset Matemático Plugável**: `rulesets/` com overrides tipados em `regras.md`.
* **Auditoria Contínua**: 13 verificações de integridade e lints literários no `reviewer.py`.

### 1.2 Diagnóstico das Lacunas
1. **Ausência Absoluta de XP e Nível**: O código do motor possui zero ocorrências de experiência, nível ou avanço de escala. O cálculo de modificador `(valor - 10) // 2` lê valores estáticos; o protagonista nunca evolui mecanicamente.
2. **Missões como Texto Decorativo**:
   * Em `ficha.md`, a seção `Marcos de Evolução Pessoal` aceita texto livre via `--add-milestone` sem custo, prazo ou efeito mecânico.
   * Em `diario.md`, `Marcos Futuros do Arco` são strings livres onde o reviewer apenas emite um aviso heurístico fraco (`LOW`) por casamento aproximado de palavras. Não há contratante, estado, objetivo verificável, recompensa de XP nem consequência de falha.
3. **Poder Narrativo sem Lastro Mecânico**: O comando `--add-ability` grava habilidades sem pré-requisito, sem moeda de custo e sem validação, permitindo escalada arbitrária de poder.
4. **Vínculos e Reputação em Prosa**: Relações com facções são puramente textuais; o motor é incapaz de reagir a mudanças de lealdade.
5. **Descanso Trivial**: O comando `timeskip` restaura vitais ao máximo sem atrito, rolagens ou consequências de ferimentos.

### 1.3 Solução Proposta
A presente especificação introduz:
1. **Sistema de Missões e Objetivos** estruturado em `diario.md` com máquina de estados rigorosa (`ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`), vínculo a relógios de pressão e subcomando CLI `quest`.
2. **Sistema de Progressão (XP)** estruturado em `ficha.md`, blindado contra colisões de regex com vitais e atributos, com concessão determinística, curva configurável de nível e subcomando CLI `progress`.
3. **Integração Bidirecional com Relógios de Ameaça**: Regras estritas de sincronia de tensão, não-automatização de falha, auditoria de orfandade de arco e dedup de recompensas.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Gestão Determinística do Ciclo de Vida de Missões
* **As a** Game Master ou jogador orquestrando a campanha,
* **I want** cadastrar missões com tipo, objetivos pontuais, contratante, relógio vinculado e recompensa em XP dentro de `diario.md`,
* **So that** os objetivos guiem ativamente a pressão de cena do motor e o cumprimento gere progresso mensurável e auditável.
* **Acceptance Criteria**:
  - `python lazy_turn.py quest --list` exibe missões ativas, fases, objetivos pendentes/concluídos e recompensas.
  - O comando `python lazy_turn.py quest --add` insere uma nova missão formatada em `diario.md` sob a seção `### Missões & Objetivos`.
  - A checagem de objetivos individuais via `quest --check` atualiza o checkbox para `[x]` e registra o turno de progresso.
  - Concluir uma missão via `quest --complete` ou falhar via `quest --fail` transiciona o estado de forma auditada, gravando a evidência ou razão no diário.
  - Seções ausentes de missões em campanhas legadas retornam lista vazia sem causar quebra ou erro de execução.

### User Scenario 2: Concessão Idempotente de Experiência e Subida de Nível
* **As a** motor de arbitragem durante o `lazy_turn.py commit`,
* **I want** creditar XP automaticamente ao concluir objetivos ou missões com códigos de concessão auditáveis,
* **So that** o protagonista progrida de forma justa e nenhum crédito duplicado ocorra na crônica.
* **Acceptance Criteria**:
  - O XP é creditado via `commit` ou comando administrativo `progress --award`, sempre associado a uma razão determinística (ex.: `obj_main:40`, `quest_main:150`).
  - Ao concluir uma missão, a tag `XP Pago: <N>` é cravada na linha da missão em `diario.md`. Tentativas posteriores de creditar a mesma missão são no-op e disparam o lint `QUEST_REWARD_PAID_TWICE`.
  - Quando a soma acumulada de XP atinge ou supera o limiar da curva configurada, o motor incrementa o `Nível` e disponibiliza Pontos de Atributo e Pontos de Habilidade na ficha.
  - O ledger de XP é estritamente unidirecional e auditado por `reviewer.py` (`XP_MISMATCH`).

### User Scenario 3: Blindagem contra Colisões de Expressões Regulares em `ficha.md`
* **As a** desenvolvedor do RPGPRO,
* **I want** assegurar que os rótulos de XP, Nível e Pontos não sejam capturados incorretamente como vitais debitáveis nem como atributos de rolagem pelos parsers legados de `council/ssot.py`,
* **So that** o snapshot de vitais e a seleção automática de atributos operem de maneira 100% confiável.
* **Acceptance Criteria**:
  - Na Fase 1, o campo de experiência é gravado sob a nomenclatura `* **Experiência (XP):** <valor>` (sem razão `/`), impedindo que o regex `[A-ZÀ-Ú]{2,5}` case com atributo ou que `**Rótulo:** N / M` case com vital.
  - `ficha["vitals"]` não contém a chave `xp` nem `experiência`.
  - `ficha["stats"]` não contém a chave `xp`.
  - Na Fase 2, os parsers de `council/ssot.py` são escopados estritamente pelas seções `### Vitais & Recursos`, `### Atributos` e `### Progressão`.

### User Scenario 4: Injeção de Contexto Teleológico no Payload de Preparação
* **As a** modelo de escrita ou agente narrativo executando `lazy_turn.py prepare`,
* **I want** receber as missões ativas, prazos, relógios relacionados e status de progressão no JSON de preparação,
* **So that** a cena gerada crie atrito real direcionado aos objetivos pendentes e calibre a escala dos desafios conforme o nível do protagonista.
* **Acceptance Criteria**:
  - O payload gerado por `lazy_turn.py prepare` inclui `step_1_quest_context` com a lista de missões ativas, objetivos pendentes e mandato de pressão.
  - O payload inclui `step_2_engine_state.protagonist.progression` contendo nível, XP atual, próximo limiar e pontos disponíveis.
  - O teste de contrato de payload (`tests/test_boundary_contracts.py`) aceita aditivamente as novas chaves sem quebra de retrocompatibilidade.

### User Scenario 5: Interação Bidirecional entre Relógios de Ameaça e Missões
* **As a** Game Master ou motor de jogo arbitrando cenas sob contagem regressiva,
* **I want** que o avanço e ruptura de relógios gerem pressão direta nas missões vinculadas sem automações cegas e com prevenção de créditos duplicados,
* **So that** a tensão ambiental do mundo e a agência ativa do jogador se entrelacem de forma coerente e auditável.
* **Acceptance Criteria**:
  - Quando um relógio vinculado a uma missão ativa atinge $cur \ge max - 1$, o mandato do `prepare` alerta para o risco iminente de colapso da missão.
  - A ruptura do relógio (`CLOCK_BREACHED`) **não** altera o status da missão para `FAILED` silenciosamente; gera o lint `QUEST_OVERDUE` e exige que a falha ou transição de contenção seja registrada pelo GM com justificativa diegética.
  - Se um `commit` conclui uma missão (`--quest-complete`) e resolve simultaneamente o relógio nominalmente associado, o crédito de XP da missão prevalece e o bônus de `clock_resolved` é deduplicado (sem *double-dipping*).
  - O comando `lazy_turn.py arc --resolve-clocks` audita se existem missões ativas vinculadas aos relógios arquivados, emitindo aviso de pendência.

---

## 3. Functional Requirements

### 3.1 Modelo de Dados e Parsing de Missões (`council/quests.py`)
* **FR-01**: Criar o módulo `council/quests.py` encarregado de parsear e serializar a seção `### Missões & Objetivos` em `diario.md`.
* **FR-02**: Suportar os metadados canônicos de missão:
  - `ID`: Código único determinístico (ex.: `Q1`, `Q2` baseado na ordem ou hash curto).
  - `Título`: Nome descritivo da missão.
  - `Tipo`: `MAIN`, `SIDE`, `PERSONAL`, `FACTION`.
  - `Status`: `ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`.
  - `Fase`: Estágio corrente da missão (ex.: `Investigação`, `Infiltração`, `Confronto`).
  - `Contratante`: Entidade ou facção patrona (opcional).
  - `Relógio`: Nome do relógio de facção vinculado (opcional).
  - `Recompensa`: Texto descritivo e valor numérico de XP sugerido.
  - `Último Progresso`: Turno no qual ocorreu a última atualização de objetivo.
  - `XP Pago`: Marcador de idempotência com o valor numérico efetivamente concedido.
* **FR-03**: Suportar lista aninhada de objetivos em formato de checkboxes Markdown (`* [ ]` ou `* [x]`).
* **FR-04**: O parser deve ser resiliente e tolerante a campos omitidos; caso a seção não exista no diário, retornar lista vazia sem exceção.

### 3.2 Máquina de Estados e CLI de Missões (`quest`)
* **FR-05**: Implementar a máquina de estados de missões:
  - Transição `ACTIVE` → `COMPLETED`: disparada quando todos os objetivos são marcados como concluídos ou via comando explícito `--complete` com evidência textual.
  - Transição `ACTIVE` → `FAILED`: disparada via `--fail` com justificativa registrada no diário.
  - Transição `ACTIVE` → `BLOCKED` e `BLOCKED` → `ACTIVE`: disparada via `--block` e `--unblock`.
  - Transição `ACTIVE` → `ABANDONED`: disparada via `--abandon`.
  - Estados `COMPLETED` e `FAILED` são terminais; reabertura exige a flag `--reopen` acompanhada de justificativa auditada.
* **FR-06**: Integrar o subcomando `quest` à CLI do `lazy_turn.py`:
  - `lazy_turn.py quest --list [--json]`
  - `lazy_turn.py quest --add "<Título>" --type <main|side|personal|faction> [--objective "<texto>"] [--faction "<nome>"] [--clock "<nome>"] [--reward "<texto>"]`
  - `lazy_turn.py quest --objective "<ID>: <texto>"`
  - `lazy_turn.py quest --check "<ID>:<num_obj>"`
  - `lazy_turn.py quest --complete "<ID>" [--evidence "<texto>"]`
  - `lazy_turn.py quest --fail "<ID>" --reason "<texto>"`
  - `lazy_turn.py quest --reopen "<ID>" --reason "<texto>"`

### 3.3 Modelo de Dados e Parsing de Progressão (`ficha.md` e `council/ssot.py`)
* **FR-07**: Definir o bloco canônico de progressão na ficha do personagem sob a seção `### Progressão`:
  ```markdown
  ### Progressão
  * **Nível:** 1
  * **Experiência (XP):** 0
  * **Próximo Nível:** 250
  * **Pontos de Atributo:** 0
  * **Pontos de Habilidade:** 0
  ```
* **FR-08**: Atualizar `council/ssot.py` para isolar os parsers:
  - Fase 1: Gravação estrita como `* **Experiência (XP):** <valor>` (sem barra `/`) para não ativar o regex de vitais, nem o regex de atributos.
  - Fase 2: Escopar os extratores de vitais e atributos para ignorar blocos fora de `### Vitais & Recursos` e `### Atributos`.
* **FR-09**: Adicionar função `parse_progression_from_ficha` e `update_progression_in_ficha` com escrita atômica no SSOT.

### 3.4 Motor de Progressão e Curva de Nível (`rulesets/progression.py`)
* **FR-10**: Criar o módulo `rulesets/progression.py` contendo a tabela de concessão de XP determinística:
  - `obj_main`: 40 XP
  - `obj_side`: 15 XP
  - `quest_side`: 60 XP
  - `quest_main`: 150 XP
  - `quest_personal`: 50 XP
  - `clock_resolved`: 40 XP
  - `clock_breached`: 30 XP
  - `arc_milestone`: 80 XP
  - `discovery`: 25 XP
  - `adversity`: 20 XP
  - `turn`: 0 XP (sem XP por mera existência)
* **FR-11**: Implementar a fórmula padrão da curva de nível:
  $$\text{XP}_{\text{limiar}}(L) = 250 \times \frac{(L - 1) \times L}{2}$$
  - Nível 2: 250 XP
  - Nível 3: 750 XP
  - Nível 4: 1500 XP
  - Nível 5: 2500 XP
  - Nível 10: 11250 XP
* **FR-12**: Permitir sobrescrita do multiplicador base da curva via override tipado em `regras.md` (`type: xp_curve`, `target: level_threshold`).
* **FR-13**: Definir os bônus automáticos por avanço de nível:
  - +1 Ponto de Atributo (teto canônico: 20, configurável por override).
  - +2 HP máximo, +1 Stamina máxima, +1 Energia/Mana máxima.
  - +1 Ponto de Habilidade a cada 2 níveis pares (Nível 2, 4, 6...).

### 3.5 Integração no Loop do Motor (`prepare` & `commit`)
* **FR-14**: No comando `lazy_turn.py prepare`:
  - Injetar no payload o bloco `step_1_quest_context` com as missões ativas, objetivos abertos, relógios relacionados e mandato de atrito diegético.
  - Injetar em `step_2_engine_state.protagonist` o resumo de progressão (`level`, `xp`, `xp_next`, `stat_points`, `ability_points`).
* **FR-15**: No comando `lazy_turn.py commit`:
  - Suportar as flags `--quest-progress "<ID>:<num_obj>"`, `--quest-complete "<ID>"`, `--quest-fail "<ID>"`.
  - Processar a concessão de XP baseada na tabela e atualizar o acumulador na ficha.
  - Gravar `XP Pago: <valor>` na linha da missão correspondente no diário.
  - Recalcular o nível e os pontos disponíveis se o novo total ultrapassar o limiar de próximo nível.

### 3.6 Auditoria e Lints no Reviewer (`council/reviewer.py`)
* **FR-16**: Implementar lints específicos no auditor de crônicas:
  - `QUEST_WITHOUT_OBJECTIVES`: Missão cadastrada sem nenhum objetivo vinculado.
  - `QUEST_STALE`: Missão ativa sem nenhum progresso registrado há mais de $N$ turnos (padrão: 10 turnos).
  - `QUEST_CLOCK_LINK_BROKEN`: Missão apontando para um relógio inexistente na seção de relógios.
  - `QUEST_OVERDUE`: Relógio vinculado à missão atingiu capacidade máxima (rompido) e a missão permanece com status `ACTIVE` sem deliberação de falha ou contenção.
  - `QUEST_REWARD_PAID_TWICE`: Tentativa de creditar recompensa em missão que já contém a marca `XP Pago`.
  - `XP_MISMATCH`: Divergência entre a soma dos créditos históricos de XP no diário e o valor total acumulado na ficha.

### 3.7 CLI de Gasto e Evolução (`progress`)
* **FR-17**: Integrar o subcomando `progress` ao `lazy_turn.py`:
  - `lazy_turn.py progress --list [--json]`
  - `lazy_turn.py progress --spend-attr <STAT>` (valida pontos disponíveis e teto do atributo).
  - `lazy_turn.py progress --spend-ability "<Nome>: <efeito>" --training "<contexto diegético>"` (valida pontos disponíveis de habilidade).
  - `lazy_turn.py progress --award "<codigo_fonte>[:quantidade]"` (comando de uso administrativo/retroativo registrado no diário).

### 3.8 Templates e Retrocompatibilidade
* **FR-18**: Atualizar os templates de referência:
  - `templates/diario.template.md`: incluir seção `### Missões & Objetivos` com exemplo canônico.
  - `templates/ficha.template.md`: incluir seção `### Progressão` inicializada no nível 1.
* **FR-19**: Assegurar que campanhas já existentes sem essas seções continuem rodando comandos de turno sem falhas.

### 3.9 Interação Bidirecional com Relógios de Ameaça & Prazos
* **FR-20**: **Pressão de Tensão no Prepare**: Se uma missão ativa possuir vínculo com um relógio cujo estado seja crítico ($cur \ge max - 1$), o payload do `lazy_turn.py prepare` deve injetar um mandato enfático em `step_1_quest_context`: *"O relógio vinculado '{nome}' está a 1 passo da ruptura iminente. A cena deve refletir o risco crítico de falha da missão."*
* **FR-21**: **Não-Automatização de Falha na Ruptura**: A ruptura de um relógio (`CLOCK_BREACHED`) **não** deve transicionar automaticamente a missão vinculada para `FAILED`. Em vez disso, o reviewer emite o lint `QUEST_OVERDUE` e o motor exige que o encerramento por fracasso ou a redefinição de objetivos seja registrado explicitamente no `commit` via `--quest-fail` ou transição de fase com justificativa na prosa.
* **FR-22**: **Deduplicação e Prevenção de Double-Dipping de XP**: Caso um turno de `commit` conclua uma missão (`--quest-complete`) que resolva simultaneamente o relógio nominalmente vinculado a ela, o crédito de XP da missão prevalece, suprimindo o bônus isolado de `clock_resolved` e registrando no log que a recompensa do relógio já foi absorvida pela missão.
* **FR-23**: **Auditoria de Orfandade no Fechamento de Arco**: O comando `lazy_turn.py arc --resolve-clocks` deve verificar se existem missões ativas vinculadas aos relógios prestes a serem arquivados. Se encontradas, o comando deve alertar as missões afetadas, instruindo sua resolução ou re-vinculação a relógios do novo arco.
* **FR-24**: **Estrita Separação de Auto-Avanço**: O auto-avanço textual heurístico existente em `lazy_turn.py` para relógios ativos **nunca** deve ser aplicado a missões ou objetivos. Objetivos e missões somente avançam ou concluem mediante flags explícitas (`--quest-progress`, `--quest-complete`, `--quest-fail`, `quest --check`).
* **FR-25**: **Delimitação de Projetos Construtivos do Protagonista**: Projetos de longo prazo empreendidos pelo protagonista (ex.: forjar item, construir base, decifrar tomo) devem ser cadastrados como **Missões Pessoais** (`type: personal`) com objetivos em checkboxes, mantendo a seção `### Relógios de Ameaça & Prazos` reservada exclusivamente para forças opostas do mundo e contagens regressivas adversárias.

---

## 4. Key Entities, Data Schemas & State Machines

### 4.1 Esquema de Missões em `diario.md`
```markdown
### Missões & Objetivos
* **[MAIN] O Trono de Pedra-Negra** | Fase: Investigação | Status: ACTIVE | Contratante: Conselho dos Lordes | Relógio: Conspiração | Recompensa: 150 XP | Último Progresso: Turno 12
  * [x] Interrogar o mensageiro do norte
  * [ ] Obter a lealdade da guarnição
  * [ ] Desmascarar o traidor na corte
```

### 4.2 Esquema de Progressão em `ficha.md`
```markdown
### Progressão
* **Nível:** 2
* **Experiência (XP):** 410
* **Próximo Nível:** 500
* **Pontos de Atributo:** 1
* **Pontos de Habilidade:** 0
```

### 4.3 Máquina de Estados da Missão
```
                ┌──────────────┐
                │    ACTIVE    │◄──────────────┐
                └──────┬───────┘               │
         ┌─────────────┼─────────────┐         │
         │             │             │         │
         ▼             ▼             ▼         │
  ┌───────────┐ ┌───────────┐ ┌───────────┐    │ --reopen
  │ COMPLETED │ │  FAILED   │ │  BLOCKED  │    │ (auditado)
  └───────────┘ └───────────┘ └─────┬─────┘    │
        │             │             │          │
        │ terminal    │ terminal    └─── unblock ┘
        └─────────────┴────────────────────────┘
```

---

## 5. Non-Functional Requirements & Safety / Boundary Invariants

* **SSOT 5-Files Invariant**: Nenhuma nova entidade deve criar um 6º arquivo canônico. Missões residem em `diario.md`; progressão reside em `ficha.md`.
* **Zero Emojis**: O parser e os geradores de markdown não devem introduzir emojis nos marcadores ou relatórios.
* **Idempotência Estrita de XP**: Créditos de XP devem ser estritamente idempotentes; reexecutar `commit` ou reprocessar turnos não duplica valores.
* **Isolamento de Expressões Regulares**: Nenhuma chave de progressão pode colidir com o regex de atributos `[A-ZÀ-Ú]{2,5}` ou de vitais `**Rótulo:** N / M`.
* **Compatibilidade Retroativa Total**: Campanhas criadas antes da especificação 007 devem ser lidas com valores default vazios/nível 1 sem exigir script de migração obrigatório imediato.
* **Prevenção de Dupla Recompensa (Anti-Double-Dipping)**: O motor não pode pagar cumulativamente por missão e relógio se ambos representarem o mesmo nó de resolução mecânica na cena.

---

## 6. Phased Implementation Roadmap & Future Systems Ranking

### Fase 1: Fundação & Concessão (Escopo Atual)
* Criação de `council/quests.py` e `rulesets/progression.py`.
* Adição do subcomando `quest` na CLI.
* Concessão determinística de XP via `commit` e idempotência com tag `XP Pago`.
* Injeção de contexto em `lazy_turn.py prepare` (incluindo FR-20 para relógios críticos).
* Regras FR-21 a FR-25 de sincronização e dedup com relógios.
* Atualização de templates e testes de regressão de regex.

### Fase 2: Gasto, Rigor & Lints
* Subcomando `progress` (`--spend-attr`, `--spend-ability`).
* Aplicação de ganhos de nível (incremento de vitais máximos).
* Isolamento escopado por seção dos parsers em `council/ssot.py`.
* Implementação dos novos lints no `council/reviewer.py`.

### Fase 3: Sistemas Futuros Priorizados
1. **Reputação Numerada de Facções**: Conversão de texto livre em valor discreto reativo.
2. **Turno de Facções Off-Screen**: Evolução autônoma de relógios e agendas do mundo.
3. **Ferimentos, Condições e Descanso**: Eliminação da cura mágica e irrestrita do `timeskip`.
4. **Grafo Epistêmico de Informação**: Modelagem explícita de "quem sabe o quê" entre NPCs.

---

## 7. Success Criteria & Verification Suite

1. **Parser & CLI de Missões**: `lazy_turn.py quest --list --json` retorna representação estruturada válida das missões ativas e seus objetivos.
2. **Idempotência de XP & Dedup**: Concluir uma missão via `commit --quest-complete` credita o XP correspondente e estampa `XP Pago`. Se o relógio associado for resolvido junto, não há duplo crédito de XP.
3. **Regressão de Regex**: Teste unitário automatizado garante que `XP`, `Nível` e `Pontos` jamais ingressem no dicionário de vitais (`vitals`) nem no de atributos (`stats`).
4. **Sincronia com Relógios**: Teste unitário valida que relógio rompido gera `QUEST_OVERDUE` sem alterar silenciosamente o status da missão ativa.
5. **Retrocompatibilidade**: Execução de `prepare`, `commit` e `review` em campanha sem as seções novas opera sem erros.
6. **Suíte de Testes 100% Verde**: `python -m unittest discover -s tests` executado com sucesso e sem regressões contratuais.
