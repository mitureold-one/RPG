# Implementation Plan: 008 — Remediação de Integridade: Sistema de Missões e Progressão (P0–P2)

**Feature**: `fix-quest-progression`  
**Status**: Ready for Tasks / Implementation  
**Created**: 2026-10-22  
**Target Backlog Phase**: P4-Remediation (Pós-Commit `6cfac1c`)  
**Base Analisada**: Relatório QA da especificação 007, `council/quests.py`, `rulesets/progression.py`, `council/ssot.py`, `council/reviewer.py`, `lazy_turn.py`, `templates/`, e `tests/`.

---

## 1. Plan Overview & Objectives

Este plano de implementação estabelece as correções técnicas para sanar todos os apontamentos do QA Review (2 P0s, 5 P1s, 7 P2s e 3 P3s) decorrentes da implementação inicial das Fases 1 e 2 da especificação 007. A remediação consolida o motor de missões e progressão, garantindo confiabilidade absoluta antes do início da Fase 3 (Facções e Reputação).

### Objetivos Centrais:
1. **P0-1 (Commit Seguro & Escopo de `next_turn`)**:
   - Reordenar a atribuição de `next_turn` no `cmd_commit` de `lazy_turn.py` antes de processar `--quest-progress`, `--quest-complete` e `--quest-fail`.
   - Garantir que `vitals_snapshot` arquivado na linha do turno reflita imediatamente qualquer level-up ocorrido no commit.
2. **P0-2 (Identidade Monotônica Imutável `[Q{N}]`)**:
   - Persistir explicitamente o identificador `[Q{N}]` no cabeçalho formatado em `format_quest_header`.
   - Calcular novos IDs como $\max(N) + 1$ e inserir missões no final do bloco em `upsert_quest_in_diario`.
   - Garantir parse tolerante com fallback sequencial para campanhas legadas.
3. **P1-3 a P1-7 (Ciclo de Vida, SSOT de XP, Ledger e Lints)**:
   - Implementar `--unblock`, `--abandon` e persistência de `--evidence`.
   - Centralizar valores padrão de XP exclusivamente em `rulesets/progression.py` e eliminar divergências literais em `quests.py`.
   - Implementar ledger de auditoria em `diario.md` para concessões avulsas de XP.
   - Aprimorar o linter `XP_MISMATCH` para reconciliação exata e fazer `QUEST_REWARD_PAID_TWICE` emitir severidade `CRITICAL`.
4. **P2-8 a P2-14 (Rigor Matemático, Overrides e Substituição Escopada)**:
   - Aplicar `base_step` de overrides no commit; blindar `calculate_level_from_xp` com `max(1, base_step)`.
   - Tolerar subida de nível fora de turno em `VITALS_DESYNC`.
   - Higienizar templates (`init_campaign_from_templates`) evitando placeholders não interpolados e limpar sintaxe do hint de commit.
   - Escopar substituições de blocos em `quests.py` e garantir estritamente uma única gravação de arquivo em disco por operação.
5. **P3-15 a P3-17 (Higiene da Suíte e Portabilidade sob Sandbox)**:
   - Configurar diretório temporário local no workspace (`.tmp/test_scratch/`) para execução imune a restrições de permissão de ACL do sistema operacional.
   - Adicionar testes de integração ponta a ponta exercitando diretamente `cmd_commit`, `cmd_quest` e `cmd_progress`.

---

## 2. Technical Context & Constitution Gates

* **Invariante dos 5 Arquivos SSOT**: Nenhuma entidade nova gera arquivos adicionais. Missões, evidências e ledger de XP residem em `diario.md`; progressão e vitais residem em `ficha.md`.
* **Biblioteca Padrão Exclusiva (Ponytail Standard Library First)**: Todo o código opera estritamente com `re`, `json`, `pathlib`, `argparse`, `unittest` e `shutil`. Zero novas dependências externas.
* **Escrita Atômica (Single-Write Pattern)**: Operações de atualização em arquivos SSOT leem uma única vez, modificam a representação em memória e escrevem uma única vez no disco ao final.
* **Zero Emojis e Anti-Puppeteering**: Conformidade estrita com as diretrizes do RPGPRO Core Sovereign Router em todas as mensagens de console, templates e saídas Markdown.

---

## 3. Work Breakdown Structure

### Módulo 1: Correção do Fluxo de Commit (P0-1)
- [ ] **Task 1.1**: Reordenar `cmd_commit` em `lazy_turn.py`:
  - Mover `diario_ctx = parse_diario_md(diario_path)` e `next_turn = diario_ctx["last_turn_num"] + 1` para antes do bloco 3b.
  - Assegurar que `ficha_after = parse_ficha_md(ficha_path)` capture vitais já expandidos após processamento de level-up.
- [ ] **Task 1.2**: Tratar duplicidade de pagamento no commit:
  - Se `--quest-complete` for chamado para uma missão já carimbada com `XP Pago`, bloquear o crédito e adicionar issue ou alerta crítico.

### Módulo 2: Identidade Monotônica Imutável de Missões (P0-2)
- [ ] **Task 2.1**: Atualizar `format_quest_header` em `council/quests.py`:
  - Incluir obrigatoriamente `* **[{ID}] [{TYPE}] {Title}**`.
- [ ] **Task 2.2**: Atualizar `parse_quests_from_diario` em `council/quests.py`:
  - Extrair o ID monotônico `[Q{N}]` priorizando a tag explícita, mantendo fallback ordenado para textos sem tag.
- [ ] **Task 2.3**: Atualizar `upsert_quest_in_diario` (`action == "add"`):
  - Calcular próximo ID como $\max(N) + 1$.
  - Inserir a nova missão no final da seção de missões (antes do próximo `###` ou fim do arquivo).
  - Garantir que ações de edição (`check`, `complete`, `fail`) localizem a missão pelo seu cabeçalho com ID único.

### Módulo 3: Ciclo de Vida Completo, Evidência e CLI (P1-3)
- [ ] **Task 3.1**: Suportar `--unblock` em `council/quests.py` e `lazy_turn.py`:
  - Transicionar missão de `BLOCKED` para `ACTIVE`.
- [ ] **Task 3.2**: Suportar `--abandon` em `council/quests.py` e `lazy_turn.py`:
  - Transicionar missão para `ABANDONED` e registrar justificativa diegética opcional.
- [ ] **Task 3.3**: Persistir `--evidence` em `upsert_quest_in_diario`:
  - Anexar a evidência na conclusão de missão como sub-bullet `  * **Evidência:** {evidence}`.

### Módulo 4: SSOT de Economia de XP e Eliminação de Código Morto (P1-4, P1-5)
- [ ] **Task 4.1**: Centralizar recompensas de missões em `rulesets/progression.py`:
  - Definir `DEFAULT_QUEST_REWARDS = {"MAIN": 150, "SIDE": 60, "PERSONAL": 50, "FACTION": 50}`.
  - Consumir em `council/quests.py`, eliminando fallbacks literais duplicados.
- [ ] **Task 4.2**: Integrar resolução de relógios no commit:
  - Conceder `clock_resolved` (40 XP) ao resolver relógio não vinculado a missão.
  - Suportar flag ou reconhecimento de `clock_breached` (30 XP).

### Módulo 5: Ledger de Experiência e Linter de Rigor (P1-6, P1-7)
- [ ] **Task 5.1**: Implementar Ledger de Experiência em `diario.md`:
  - `lazy_turn.py progress --award` grava entrada estruturada `* **[XP] +{N} XP** ({motivo}) | Turno {T}` em `diario.md`.
- [ ] **Task 5.2**: Aprimorar linter `XP_MISMATCH` em `council/reviewer.py`:
  - Reconciliar total da ficha com a soma exata de missões com `XP Pago` + ledger de awards.
- [ ] **Task 5.3**: Endurecer `QUEST_REWARD_PAID_TWICE` em `council/reviewer.py`:
  - Emitir severidade `CRITICAL` se detectada tentativa de pagamento duplicado ou cabeçalho anômalo.

### Módulo 6: Robustez Matemática, Overrides e Substituição Escopada (P2-8, P2-9, P2-12 a P2-14)
- [ ] **Task 6.1**: Passar `base_step` de overrides no commit para `update_progression_in_ficha`.
- [ ] **Task 6.2**: Blindar `calculate_level_from_xp` em `rulesets/progression.py` com `base_step = max(1, base_step)`.
- [ ] **Task 6.3**: Ajustar `VITALS_DESYNC` em `council/reviewer.py` para tolerar level-up fora de turno quando a diferença corresponder ao incremento de vitais do nível.
- [ ] **Task 6.4**: Refatorar `upsert_quest_in_diario` em `council/quests.py`:
  - Substituição escopada apenas no bloco da missão alvo.
  - Eliminar leituras/escritas intermediárias em disco (garantir estritamente uma única gravação atômica).

### Módulo 7: Higienização de Templates e CLI Hints (P2-10, P2-11)
- [ ] **Task 7.1**: Adicionar substituição de placeholders de missões (`{{NOME_MISSAO_PRINCIPAL}}`, etc.) em `council/helpers.py:init_campaign_from_templates`.
- [ ] **Task 7.2**: Adicionar prefixo `[Q1]` em `templates/diario.template.md`.
- [ ] **Task 7.3**: Higienizar hint de commit em `lazy_turn.py cmd_prepare` (remover `[` e `|` inválidos no shell).

### Módulo 8: Higiene da Suíte e Testes sob Sandbox (P3-15 a P3-17)
- [ ] **Task 8.1**: Atualizar suíte de testes para utilizar pasta temporária sob `.tmp/test_scratch/` no workspace, evitando falhas de permissão de `tempfile.mkdtemp()`.
- [ ] **Task 8.2**: Criar testes de integração direta para `cmd_commit`, `cmd_quest` e `cmd_progress`.
- [ ] **Task 8.3**: Executar gate completo de 8 passos e verificar aprovação 100% verde.

---

## 4. Verification & Gate Criteria

O plano é considerado concluído quando os 8 passos do `quickstart.md` forem executados com sucesso:
1. `python -m unittest discover tests` roda sem exceções em sandbox.
2. `quest --add` gera `Q1` e `Q2` monotônicos no final da seção sem alterar IDs existentes.
3. `quest --check` altera checkbox e atualiza progresso.
4. `commit --quest-complete` executa sem `UnboundLocalError`, credita XP e grava `XP Pago`.
5. Idempotência é garantida e tentativas duplicadas disparam aviso/lint crítico.
6. Subcomandos `--unblock`, `--abandon` e `--evidence` operam perfeitamente.
7. Subcomando `progress --award` grava ledger em `diario.md` e `XP_MISMATCH` valida conciliação.
8. Auditoria de integridade nas 3 campanhas reais permanece sem regressões.
