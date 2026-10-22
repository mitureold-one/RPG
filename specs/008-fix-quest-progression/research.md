# Research & Technical Decisions: 008 — Remediação de Integridade (Missões e Progressão)

**Feature**: `fix-quest-progression`  
**Status**: Completed / Approved  
**Date**: 2026-10-22  
**Context**: Análise detalhada dos defeitos auditados no QA Review pós-commit `6cfac1c` (P0-1 a P3-17) e definição da estratégia de remediação.

---

## 1. P0-1: Ordem de Execução e Escopo de Variáveis no `cmd_commit`

### Contexto & Problema
Em `lazy_turn.py`, as linhas 1017–1057 (bloco 3b: processamento de `--quest-progress`, `--quest-complete` e `--quest-fail`) referenciam a variável `next_turn` (`current_turn=next_turn`), mas `next_turn = diario_ctx["last_turn_num"] + 1` só é calculada na linha 1061. Isso dispara `UnboundLocalError: cannot access local variable 'next_turn'` em 100% das chamadas com flags de missão, quebrando a transação após vitais e relógios já terem sido alterados.

### Decisão Técnica
- Mover a leitura de `diario_ctx = parse_diario_md(diario_path)` e o cálculo de `next_turn = diario_ctx["last_turn_num"] + 1` para **antes** do bloco 3b.
- Manter o processamento de missões e XP no bloco 3b antes da captura de `ficha_after = parse_ficha_md(ficha_path)` (linha 1072).
- **Rationale**: Ao processar level-ups no bloco 3b, os vitais expandidos em `ficha.md` são lidos imediatamente por `ficha_after`, fazendo com que o `vitals_snapshot` gravado na linha do turno em `diario.md` já reflita os novos limites de HP/Stamina/Energia, prevenindo inconsistências imediatas.
- **Alternativas Consideradas**:
  - *Calcular `next_turn` isoladamente duas vezes*: Rejeitado (YAGNI/duplicação desnecessária).
  - *Adiar a concessão de XP para depois do commit do turno*: Rejeitado (deixaria a linha do turno com vitais desatualizados e exigiria segundo salvamento de diário).

---

## 2. P0-2: Identidade Monotônica Imutável de Missões (`[Q{N}]`)

### Contexto & Problema
Atualmente, `format_quest_header` em `council/quests.py` emite apenas `* **[{TYPE}] {Title}**`. O parser reconstrói o ID sequencialmente pela ordem de aparição no arquivo (`Q1`, `Q2`...), e `upsert_quest_in_diario(action="add")` insere a nova missão no **topo** da seção. Consequência: cadastrar uma missão altera o ID de todas as existentes, causando desvio de alvo em chamadas subsequentes e transferindo o carimbo `XP Pago` para outra missão.

### Decisão Técnica
1. **Persistência Explícita no Cabeçalho**: `format_quest_header` passa a formatar obrigatoriamente `* **[{ID}] [{TYPE}] {Title}**` (ex: `* **[Q1] [MAIN] O Trono de Pedra-Negra**`).
2. **Cálculo Monotônico de ID**: Ao adicionar uma missão (`action == "add"`):
   - Extrai todos os números $N$ presentes nos IDs `Q{N}` já existentes.
   - Atribui o novo ID como $Q(\max(N) + 1)$ (ou $Q1$ se a lista for vazia).
   - IDs nunca são reutilizados mesmo se uma missão for removida ou abandonada.
3. **Inserção no Final do Bloco**: A nova missão é inserida antes do próximo cabeçalho `###` ou no final da seção `### Missões & Objetivos`, preservando a ordem cronológica.
4. **Parser Tolerante com Fallback**: O regex de `parse_quests_from_diario` extrai o ID explícito se presente (`exp_id`); se ausente (campanhas legadas), mantém fallback sequencial atribuindo `Q1`, `Q2`...
5. **Rationale**: Garante idempotência referencial total. O ID torna-se chave primária indelével no texto Markdown.

---

## 3. P1-3: Completude da Máquina de Estados e Persistência de Evidência

### Contexto & Problema
`VALID_QUEST_STATUSES` define `ABANDONED`, mas a CLI não possuía argumentos `--abandon` nem `--unblock`. Além disso, o parâmetro `evidence` em `upsert_quest_in_diario` era ignorado, descartando a justificativa fática ao concluir missões com 0/N objetivos.

### Decisão Técnica
1. **Novos Argumentos CLI em `lazy_turn.py quest`**:
   - `--unblock "<QID>"`: Reverte status de `BLOCKED` para `ACTIVE`.
   - `--abandon "<QID>"` com `--reason "..."`: Transiciona para `ABANDONED` e anexa a justificativa.
2. **Persistência de Evidência**:
   - Ao executar `quest --complete "<QID>" --evidence "..."`, registrar como sub-bullet da missão: `  * **Evidência:** {evidence}` ou como campo de cabeçalho estruturado se especificado.
3. **Rationale**: Fecha o ciclo de vida formal da especificação original sem código morto e atende a auditabilidade diegética.

---

## 4. P1-4 & P1-5: Dono Único de XP e Conexão de Eventos Mecânicos

### Contexto & Problema
`quests.py` possuía valores literais hardcoded (`150 if raw_type == "MAIN" else (60 if raw_type == "SIDE" else 50)`) divergindo da tabela canônica. Ademais, `clock_resolved` e `clock_breached` constavam em `XP_GRANT_TABLE`, mas não eram disparados no loop de jogo.

### Decisão Técnica
1. **Unificação em `rulesets/progression.py`**:
   - `DEFAULT_QUEST_REWARDS = {"MAIN": 150, "SIDE": 60, "PERSONAL": 50, "FACTION": 50}`.
   - `quests.py` importa e consome exclusivamente esses valores canônicos.
2. **Integração de Relógios e Concessão de XP**:
   - No `cmd_commit`, se um relógio de ameaça não vinculado a uma missão ativa atingir `RESOLVED`, conceder automaticamente `clock_resolved` (40 XP) e registrar no log/ledger.
   - Fornecer suporte no commit para flag `--clock-breached` ou reconhecimento de superação de ruptura com crédito de `clock_breached` (30 XP).
3. **Rationale**: Respeito irrestrito ao princípio de Single Source of Truth (SSOT).

---

## 5. P1-6 & P1-7: Ledger de Experiência no Diário e Rigor dos Lints

### Contexto & Problema
`XP_MISMATCH` apenas checava se `prog["xp"] < total_xp_paid`. Concessões feitas por `lazy_turn.py progress --award` não deixavam rastro duradouro no diário, tornando impossível uma auditoria bidirecional rigorosa. O lint `QUEST_REWARD_PAID_TWICE` verificava duplicidade textual de `XP Pago` na mesma linha, algo inalcançável via CLI padrão.

### Decisão Técnica
1. **Ledger de Experiência em `diario.md`**:
   - Adicionar subseção ou entradas canônicas sob `### Registro de Experiência` (ou como anotações auditáveis no histórico):
     `* **[XP] +{N} XP** ({origem}) | Turno {T}`
   - `progress --award` e concessões diretas passam a gravar atomicamente essa linha no diário.
2. **Refinamento de `XP_MISMATCH`**:
   - Calcular `total_auditavel = sum(xp_pago_missoes) + sum(xp_ledger_awards)`.
   - Se `total_auditavel > 0` e `ficha["progression"]["xp"] != total_auditavel`, alertar com severidade `HIGH` indicando a discrepância exata.
3. **Rigor de `QUEST_REWARD_PAID_TWICE`**:
   - Se uma tentativa de concluir missão já paga for detectada no commit ou se o cabeçalho contiver carimbos duplicados, emitir imediatamente `CRITICAL`.
4. **Rationale**: Transparência e rastreabilidade total da economia do jogo sem criar arquivos extras.

---

## 6. P2-8 a P2-14: Robustez Matemática, Substituição Escopada e Atomicidade

### Decisões Técnicas
1. **P2-8 (Overrides de Curva no Commit)**: Passar `base_step = get_base_step_from_overrides(get_campaign_overrides(campaign_id))` para `update_progression_in_ficha` no `cmd_commit`.
2. **P2-9 (Tolerância a Level-Up Fora de Turno em `VITALS_DESYNC`)**:
   - Quando um level-up ocorre via `progress --award` ou `--spend-*` fora de um turno, o reviewer deve verificar se a discrepância nos vitais máximos corresponde exatamente ao bônus de subida de nível em relação ao último snapshot registrado no diário.
3. **P2-10 (Placeholders de Missão no Template)**:
   - Adicionar substituição dos placeholders `{{NOME_MISSAO_PRINCIPAL}}`, `{{CONTRATANTE_OU_FACCAO}}`, `{{PRIMEIRO_OBJETIVO_DA_MISSAO}}`, `{{SEGUNDO_OBJETIVO_DA_MISSAO}}` em `council/helpers.py:init_campaign_from_templates`.
   - Incluir `[Q1]` explicitamente em `templates/diario.template.md`.
4. **P2-11 (Hint de Commit Limpo)**:
   - Formatar o hint sem colchetes e pipes quebrados: `--quest-progress Q1:1` e `--quest-complete Q1` em linhas ou blocos legíveis.
5. **P2-12 (Blindagem de Divisão/Loop em Curva)**:
   - Em `calculate_level_from_xp`, assegurar `base_step = max(1, base_step)`.
6. **P2-13 & P2-14 (Substituição Escopada e Escrita Única)**:
   - Em `council/quests.py`, eliminar escritas intermediárias em disco durante `upsert_quest_in_diario`. Ler o arquivo uma única vez, modificar a estrutura em memória com regex delimitado pelo cabeçalho da missão alvo e gravar uma única vez ao término.

---

## 7. P3-15 a P3-17: Portabilidade de Testes sob Sandbox de CI/Agente

### Contexto & Problema
`tempfile.mkdtemp()` utiliza o diretório temporário do sistema operacional (ex: `AppData/Local/Temp`), que pode ter permissões restritas em ambientes sandboxed.

### Decisão Técnica
- Criar um fixture utilitário nos testes que crie pastas temporárias sob `PROJECT_ROOT / ".tmp" / "test_scratch"` com tratamento resiliente de cleanup em `tearDown`.
- Adicionar testes de integração ponta a ponta exercitando diretamente os métodos de CLI (`cmd_commit`, `cmd_quest`, `cmd_progress`).
- **Rationale**: Garante execução 100% verde tanto no desktop local quanto em pipelines restritos de sandbox.
