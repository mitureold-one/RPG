# Feature Specification: 008 — Remediação de Integridade: Sistema de Missões e Progressão (P0–P2)

**Feature Name**: `fix-quest-progression`  
**Status**: Ready for Planning  
**Created**: 2026-10-22  
**Target Backlog Phase**: P4-Remediation (Auditoria Pós-Commit `6cfac1c`)  
**Base Analisada**: Relatório QA pós-implementação da 007, `council/quests.py`, `rulesets/progression.py`, `council/ssot.py`, `council/reviewer.py`, `lazy_turn.py`, `templates/`, e `tests/`.

---

## 1. Executive Summary & Problem Statement

A auditoria pós-implementação da especificação 007 (commit `6cfac1c`) validou que as fundações de domínio (parser tolerante, fórmula quadrática de curva, isolamento de seções em `parse_ficha_md`, injeção aditiva no payload e retrocompatibilidade com campanhas existentes) estão sólidas. No entanto, o gate de aceite identificou **defeitos críticos de integração e lacunas normativas** que inviabilizam a aprovação da Fase 3 (Facções e Reputação):

1. **Quebra Funcional P0 no Commit**: A flag `--quest-complete` (caminho crítico de concessão de XP no loop de jogo) aborta em 100% das chamadas com `UnboundLocalError: cannot access local variable 'next_turn'`. A exceção ocorre após a gravação de vitais e relógios, deixando o SSOT em estado parcial e corrompendo a sessão.
2. **Identidade Posicional Instável de Missões (P0)**: Os IDs de missão (`Q1`, `Q2`) não são persistidos no cabeçalho Markdown e o `--add` insere novas missões no topo da seção calculando `Q{len+1}`. Isso causa descolamento imediato de identidade: cadastrar uma missão altera o índice de todas as outras, fazendo com que `--complete "Q2"` conclua a missão errada e grave carimbos de `XP Pago` no alvo incorreto.
3. **Requisitos Parciais (P1)**: Falta de suporte a `--unblock` e `--abandon`; descarte silencioso do parâmetro `--evidence`; coexistência de dois donos para o valor padrão de XP (divergência entre `XP_GRANT_TABLE` e textos hardcoded em `quests.py`); ausência de ledger de XP no diário (tornando `XP_MISMATCH` frágil e unidirecional); e inalcançabilidade prática do lint `QUEST_REWARD_PAID_TWICE`.
4. **Defeitos de Integração e Robustez (P2)**: Desconsideração de overrides da curva de XP no commit; falso positivo `VITALS_DESYNC` gerado por level-up fora de turno; criação de missões-fantasmas não interpoladas no `init-campaign`; hint de commit com sintaxe inválida de shell (`[--quest-progress ...]`); risco de laço infinito em `calculate_level_from_xp` se `base_step <= 0`; substituição de texto não escopada em `quests.py`; e escritas intermediárias múltiplas no diário.
5. **Higiene de Testes (P3)**: Falhas de permissão sob sandboxes de CI/agente decorrentes de `tempfile.mkdtemp()` fora do workspace e ausência de testes de integração direta nas funções de CLI (`cmd_commit`, `cmd_quest`, `cmd_progress`).

Esta especificação formaliza a resolução integral de todos os itens apontados no QA Review, blindando o motor para que a Fase 3 possa ser construída sobre uma base inabalável.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Conclusão Confiável de Missões via Commit sem Falhas de Escopo (P0-1)
* **As a** jogador ou Game Master finalizando um turno de crônica,
* **I want** executar `lazy_turn.py commit --campaign <id> --summary "..." --quest-complete "Q1"` com sucesso,
* **So that** os objetivos sejam atualizados, o XP seja creditado, o status da missão mude para `COMPLETED`, o turno seja arquivado e a auditoria pós-commit rode sem interrupção.
* **Acceptance Criteria**:
  - A execução de `cmd_commit` com `--quest-complete`, `--quest-progress` ou `--quest-fail` nunca levanta `UnboundLocalError`.
  - O cálculo do avanço de turno (`next_turn = diario_ctx["last_turn_num"] + 1`) ocorre antes do processamento de missões e XP.
  - A expansão de vitais decorrente de eventual subida de nível é refletida imediatamente no `vitals_snapshot` arquivado na linha do turno em `diario.md`.

### User Scenario 2: Identidade Monotônica e Imutável de Missões (P0-2)
* **As a** motor de jogo manipulando múltiplas missões em `diario.md`,
* **I want** que cada missão receba um identificador monotônico explícito gravado no próprio texto (ex.: `* **[Q1] [MAIN] Título**`),
* **So that** novas adições, remoções ou reordenações jamais alterem os identificadores das missões preexistentes nem desloquem o carimbo de `XP Pago`.
* **Acceptance Criteria**:
  - `format_quest_header` emite obrigatoriamente o prefixo `[Q{N}]` no cabeçalho Markdown de cada missão.
  - `parse_quests_from_diario` extrai o ID a partir do prefixo explícito `[Q{N}]` (com fallback sequencial apenas para campanhas legadas que omitam a tag).
  - O subcomando `quest --add` calcula o novo ID como $\max(\text{IDs existentes}) + 1$ e insere a nova missão no **final** do bloco de missões.
  - Inserções manuais ou reordenações de missões preservam a correspondência exata de cada `Q{N}` com seus objetivos, status e `XP Pago`.

### User Scenario 3: Fonte Única de Verdade de XP, Ledger Transparente e Lints Reais (P1-4, P1-5, P1-6, P1-7)
* **As a** auditor ou desenvolvedor do RPGPRO,
* **I want** que os valores padrão de XP sejam governados exclusivamente por `rulesets/progression.py`, que todo ganho de XP deixe um rastro de ledger em `diario.md`, e que os linters detectem tentativas duplicadas ou inconsistências reais,
* **So that** o motor respeite o princípio sagrado de "um único dono textual" e impeça fraudes ou descompassos no progresso do personagem.
* **Acceptance Criteria**:
  - `quests.py` não define valores hardcoded de XP divergentes da tabela; valores padrão para `MAIN` (150), `SIDE` (60) e `PERSONAL`/`FACTION` (50) vêm unificados de `rulesets/progression.py`.
  - O comando `progress --award` e o `commit` gravam uma entrada de ledger no diário sob `### Histórico de Turnos` ou seção de progresso: `* **Registro de Experiência:** +{N} XP ({motivo}) | Turno {T}`.
  - O lint `XP_MISMATCH` valida se o total de XP na ficha bate exatamente com a soma dos créditos rastreáveis (missões concluídas + ledger de concessões).
  - Uma tentativa de invocar `--quest-complete` em uma missão que já possui `XP Pago` emite o lint `QUEST_REWARD_PAID_TWICE` na auditoria pós-commit, além de abortar a duplicação.

### User Scenario 4: Suporte Completo à Máquina de Estados e Persistência de Evidência (P1-3)
* **As a** Game Master gerenciando o ciclo de vida de missões na mesa,
* **I want** poder desbloquear missões (`--unblock`), abandoná-las (`--abandon`) e registrar a evidência concreta de encerramento (`--evidence "..."`),
* **So that** todas as transições do modelo de dados sejam alcançáveis pela CLI e a conclusão de missões fique diegeticamente justificada.
* **Acceptance Criteria**:
  - A CLI suporta `quest --unblock "<ID>"` (transiciona `BLOCKED` $\rightarrow$ `ACTIVE`).
  - A CLI suporta `quest --abandon "<ID>" [--reason "..."]` (transiciona `ACTIVE`/`BLOCKED` $\rightarrow$ `ABANDONED`).
  - A flag `--evidence "..."` passada para `quest --complete` grava a evidência diretamente na linha da missão ou como sub-bullet informativo no diário: `  * **Evidência:** {texto}`.

### User Scenario 5: Resiliência de Overrides, Templates e Suíte sob Sandbox (P2-8 a P2-14, P3-15 a P3-17)
* **As a** mantenedor do framework executando testes em ambientes restritos (CI/Sandbox),
* **I want** que todos os testes executem sem erros de permissão, que o template não crie entidades fictícias no `init-campaign`, e que overrides e cálculos sejam matematicamente blindados,
* **So that** o sistema seja 100% confiável, portável e limpo.
* **Acceptance Criteria**:
  - `commit` respeita `xp_curve` configurada em `regras.md` passando `base_step` correto para `update_progression_in_ficha`.
  - `calculate_level_from_xp` valida `base_step = max(1, base_step)`, prevenindo laço infinito se um override fornecer zero ou negativo.
  - `templates/diario.template.md` não contém missões em estado ativo com placeholders textuais não substituídos pelo `init-campaign`.
  - O hint emitido no `prepare` usa sintaxe limpa de shell (`--quest-progress Q1:1 --quest-complete Q1` em placeholders legíveis, sem pipes ou colchetes quebrados).
  - A suíte de testes utiliza diretório temporário dentro do workspace gerenciado pelo RPGPRO (ex.: `.tmp/test_scratch/`), rodando 100% verde sem requerer elevação de privilégios.
  - Testes de integração direta exercitam `cmd_commit` com flags de missão, `cmd_quest` e `cmd_progress`.

---

## 3. Functional Requirements

### 3.1 Correção do Fluxo de Commit (P0-1)
* **FR-01**: Reordenar a execução de `cmd_commit` em `lazy_turn.py`:
  - O cálculo `next_turn = diario_ctx["last_turn_num"] + 1` deve ser executado antes do bloco `3b` (processamento de missões e concessão de XP).
  - O processamento de missões e XP deve ser executado antes da leitura `ficha_after = parse_ficha_md(ficha_path)` e da montagem do `vitals_snapshot`.
  - Garantir que se um level-up ocorrer no commit, os vitais expandidos sejam registrados no cabeçalho do turno no diário.

### 3.2 Persistência de Identidade Monotônica de Missões (P0-2)
* **FR-02**: Atualizar `format_quest_header` em `council/quests.py`:
  - Emitir obrigatoriamente `* **[{ID}] [{TYPE}] {Title}**` como prefixo da linha de missão.
* **FR-03**: Atualizar `parse_quests_from_diario` em `council/quests.py`:
  - Priorizar a leitura do ID explicitado no formato `[Q{N}]`.
  - Caso omitido (campanhas legadas), atribuir IDs sequenciais `Q1`, `Q2`...
* **FR-04**: Atualizar `upsert_quest_in_diario` em `council/quests.py`:
  - Ao adicionar uma nova missão (`action == "add"`):
    - Extrair todos os números $N$ dos IDs `Q{N}` existentes.
    - Atribuir o ID monotônico `Q{max(N) + 1}` (ou `Q1` se a lista for vazia).
    - Inserir a nova missão no **final** da seção `### Missões & Objetivos` (antes do próximo cabeçalho `###`), nunca no topo.
  - Garantir que edições e conclusões busquem a missão pelo seu ID explícito e substituam apenas o bloco exato daquela missão no texto.

### 3.3 Completude da Máquina de Estados e Evidência (P1-3)
* **FR-05**: Implementar suporte a `--unblock` em `lazy_turn.py` e `council/quests.py`:
  - Transicionar o status da missão de `BLOCKED` para `ACTIVE`.
* **FR-06**: Implementar suporte a `--abandon` em `lazy_turn.py` e `council/quests.py`:
  - Transicionar o status da missão para `ABANDONED` e registrar a razão opcional.
* **FR-07**: Persistir evidência textual em `upsert_quest_in_diario`:
  - Ao concluir missão via `action == "complete"` com o parâmetro `evidence` preenchido, registrar na missão a linha `  * **Evidência:** {evidence}` ou anexar no campo `Evidência: {texto}`.

### 3.4 Unificação de Dono do XP e Eliminação de Código Morto (P1-4, P1-5)
* **FR-08**: Centralizar a definição de valores padrão de recompensa de missões em `rulesets/progression.py`:
  - `MAIN`: 150 XP (`quest_main`)
  - `SIDE`: 60 XP (`quest_side`)
  - `PERSONAL`: 50 XP (`quest_personal`)
  - `FACTION`: 50 XP (`quest_personal` / base de facção)
* **FR-09**: Eliminar a divergência em `council/quests.py`:
  - Ao cadastrar missão sem `--reward` ou ao fazer fallback de parse, consumir os valores unificados de `rulesets/progression.py`.
* **FR-10**: Conectar os códigos de relógio e adversidade no loop de jogo:
  - No `commit`, se um relógio não vinculado for resolvido (`clock_advance` atingir status `RESOLVED` sem missão associada), creditar `clock_resolved` (40 XP).
  - Se um relógio romper (`CLOCK_BREACHED`) e a consequência for superada no turno, suportar flag ou auto-crédito de `clock_breached` (30 XP).

### 3.5 Ledger de XP e Auditoria Confiável (P1-6, P1-7)
* **FR-11**: Implementar Ledger de Experiência em `diario.md`:
  - O comando `progress --award` deve gravar um registro permanente no diário (sob uma subseção `### Registro de Experiência` ou como anotação no histórico de turnos).
  - A conclusão de missões e objetivos com crédito de XP deve constar de forma auditável no diário.
* **FR-12**: Aprimorar o linter `XP_MISMATCH` em `council/reviewer.py`:
  - Validar se o total de XP em `ficha.md` é coerente com a soma de todas as fontes auditáveis do diário (missões com `XP Pago` + ledger de awards).
* **FR-13**: Garantir que o linter `QUEST_REWARD_PAID_TWICE` dispare no reviewer:
  - Se um commit ou comando tentar pagar XP para uma missão que já contenha `XP Pago`, além de barrar o crédito, emitir issue com severidade `CRITICAL`.

### 3.6 Resiliência Matemática e Integração de Overrides (P2-8, P2-9, P2-12)
* **FR-14**: No `cmd_commit` em `lazy_turn.py`, extrair `base_step` dos overrides da campanha (`get_base_step_from_overrides(overrides)`) e repassar para `update_progression_in_ficha`.
* **FR-15**: Em `rulesets/progression.py`:
  - Blindar `calculate_level_from_xp` para forçar `base_step = max(1, base_step)`, evitando divisões por zero ou loops infinitos.
* **FR-16**: Prevenir falsos positivos de `VITALS_DESYNC` em level-ups fora de turno:
  - Ao rodar `lazy_turn.py progress --award` ou `--spend-*` que resulte em subida de nível e expansão de vitais, sincronizar a anotação correspondente no diário ou ensinar o reviewer a tolerar a diferença se `ficha.progression.level > ultimo_turno.level`.

### 3.7 Higienização de Templates, CLI Hints e Escrita Atômica (P2-10, P2-11, P2-13, P2-14)
* **FR-17**: Ajustar `templates/diario.template.md` e `init_campaign_from_templates`:
  - `init_campaign_from_templates` deve interpolar placeholders de missão (`{{NOME_MISSAO_PRINCIPAL}}`) ou o template deve trazer uma seção de missões vazia/comentada por default, evitando dados corrompidos na inicialização de novas campanhas.
* **FR-18**: Corrigir o hint de commit no `cmd_prepare`:
  - Substituir `[--quest-progress "Q1:1" | --quest-complete "Q1"]` por instruções válidas de linha de comando.
* **FR-19**: Escopar substituições de texto em `council/quests.py`:
  - Localizar a missão pelo seu cabeçalho completo com ID único e substituir apenas o bloco delimitado daquela missão, sem usar `text.replace` global.
* **FR-20**: Garantir atomicidade estrita em `upsert_quest_in_diario`:
  - Ler o texto de `diario.md` uma única vez no início, realizar todas as mutações na árvore de texto em memória e escrever no disco exatamente uma vez no final da operação.

### 3.8 Portabilidade de Testes sob Sandbox e Cobertura de CLI (P3-15, P3-16)
* **FR-21**: Criar helper de diretório temporário no workspace para a suíte de testes:
  - Usar pasta temporária local (ex.: `.tmp/tests_sandbox/`) com limpeza garantida no `tearDown`, resolvendo problemas de ACL em sandboxes restritos.
* **FR-22**: Criar testes de integração ponta a ponta em `tests/test_cli_contracts.py` ou `tests/test_quest_progression.py`:
  - Executar diretamente `cmd_quest`, `cmd_progress` e `cmd_commit` com flags `--quest-progress`, `--quest-complete`, `--quest-fail`, validando o fluxo real do usuário.

---

## 4. Key Entities & Data Schemas

### 4.1 Cabeçalho Canônico Monotônico da Missão (`diario.md`)
```markdown
### Missões & Objetivos
* **[Q1] [MAIN] O Trono de Pedra-Negra** | Fase: Investigação | Status: ACTIVE | Contratante: Conselho dos Lordes | Relógio: Conspiração | Recompensa: 150 XP | Último Progresso: Turno 12 | XP Pago: 0
  * [x] Interrogar o mensageiro do norte
  * [ ] Obter a lealdade da guarnição
  * [ ] Desmascarar o traidor na corte

* **[Q2] [SIDE] A Forja Ancestral** | Fase: Coleta | Status: ACTIVE | Contratante: Mestre Durn | Recompensa: 60 XP | Último Progresso: Turno 8
  * [x] Encontrar o minério estelar
  * [ ] Purificar as cinzas do crisol
```

### 4.2 Subcomando `quest` Completo
```bash
# Adicionar missão (recebe automaticamente o próximo ID monotônico Q{N} no final da lista)
python lazy_turn.py quest --campaign <id> --add "Título" --type main --objective "Passo 1"

# Bloquear, desbloquear e abandonar
python lazy_turn.py quest --campaign <id> --block "Q1" --reason "Caminho obstruído"
python lazy_turn.py quest --campaign <id> --unblock "Q1"
python lazy_turn.py quest --campaign <id> --abandon "Q1" --reason "Prioridades mudaram"

# Concluir com evidência diegética
python lazy_turn.py quest --campaign <id> --complete "Q1" --evidence "Carta confessa do traidor"
```

---

## 5. Non-Functional Requirements & Safety Invariants

* **Invariante de ID Imutável**: Um identificador `Q{N}` atribuído a uma missão é permanente e jamais pode ser alterado por adições de outras missões.
* **Invariante de Escrita Atômica**: Operações em `council/quests.py` e `council/ssot.py` devem realizar no máximo uma única gravação (`write_text`) por invocação.
* **Invariante de Sandbox Zero-Crash**: A suíte de testes deve rodar 100% verde tanto em ambientes elevados quanto em sandboxes sem permissão de escrita em diretórios temporários do sistema operacional (`C:\Users\...\AppData\Local\Temp`).

---

## 6. Success Criteria & Verification Suite

1. **Gate P0-1**: `python lazy_turn.py commit --campaign _qa_scratch --summary "teste" --quest-complete "Q1"` executa sem `UnboundLocalError`, conclui a missão, credita o XP e avança o turno no diário.
2. **Gate P0-2**: Em campanha com múltiplas missões, executar `quest --add` atribui `Q{N+1}` no final do arquivo; chamadas a `--complete` ou `--check` afetam com precisão cirúrgica a missão correspondente ao ID.
3. **Gate P1**: Comandos `--unblock` e `--abandon` funcionam na CLI; `--complete --evidence` grava a evidência no diário; valores de XP de missões pessoais/secundárias respeitam rigorosamente `rulesets/progression.py`.
4. **Gate P2**: O recálculo de nível no commit respeita a curva customizada de `regras.md`; campanhas inicializadas via `init-campaign` não trazem missões corrompidas com placeholders.
5. **Gate P3**: `python -m unittest discover -s tests` roda 100% verde sem erros de ACL no sandbox de execução.
