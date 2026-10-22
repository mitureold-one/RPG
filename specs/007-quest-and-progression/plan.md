# Implementation Plan: 007 — Sistema de Missões e Sistema de Progressão (XP)

**Feature**: `quest-and-progression`  
**Status**: Ready for Tasks / Implementation  
**Created**: 2026-10-22  
**Target Backlog Phase**: P4 (Fase 1: Fundação & Concessão; Fase 2: Gasto & Rigor)

---

## 1. Plan Overview & Objectives

Este plano de implementação formaliza as entregas da especificação [`spec.md`](file:///c:/Users/Konor/Documents/RPGPRO/specs/007-quest-and-progression/spec.md) com base nas decisões arquiteturais aprovadas em [`research.md`](file:///c:/Users/Konor/Documents/RPGPRO/specs/007-quest-and-progression/research.md), no modelo de dados de [`data-model.md`](file:///c:/Users/Konor/Documents/RPGPRO/specs/007-quest-and-progression/data-model.md) e nos contratos de interface de [`contracts/quest-and-progression-contracts.md`](file:///c:/Users/Konor/Documents/RPGPRO/specs/007-quest-and-progression/contracts/quest-and-progression-contracts.md).

### Objetivos Centrais
1. **Sistema de Missões (`council/quests.py`)**:
   - Parse e gravação atômica da seção `### Missões & Objetivos` em `diario.md`.
   - Máquina de estados (`ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`) e subcomando `lazy_turn.py quest`.
   - Sincronização com relógios narrativos de ameaça (alerta de urgência crítica no `prepare`, geração de `QUEST_OVERDUE` na ruptura e dedup de XP).
2. **Sistema de Progressão (`rulesets/progression.py` & `council/ssot.py`)**:
   - Parse e gravação atômica da seção `### Progressão` em `ficha.md` com nomenclatura imune a colisões de regex.
   - Motor de cálculo de XP determinístico com curva quadrática e suporte a overrides de campanha.
   - Crédito idempotente com carimbo `XP Pago: <valor>` em `diario.md` e subcomando `lazy_turn.py progress`.
3. **Integração no Motor e Auditoria**:
   - Injeção de contexto teleológico em `lazy_turn.py prepare` (`step_1_quest_context` e calibragem de escala).
   - Flags `--quest-progress`, `--quest-complete`, `--quest-fail` no `lazy_turn.py commit`.
   - Lints determinísticos de integridade em `council/reviewer.py`.
   - Atualização dos templates canônicos e expansão da suíte de testes.

---

## 2. Technical Context & Constitution Gates

* **Invariante dos 5 Arquivos SSOT**: Nenhuma entidade nova cria arquivos adicionais. Missões residem em `diario.md`; progressão reside em `ficha.md`.
* **Biblioteca Padrão Exclusiva (Ponytail Standard Library First)**: Todo o parsing, serialização atômica, cálculo matemático e CLI utilizam exclusivamente módulos padrão do Python (`re`, `json`, `pathlib`, `argparse`, `unittest`). Nenhuma dependência externa.
* **Isolamento de Expressões Regulares**: O formato `* **Experiência (XP):** <valor>` impede que `XP` seja capturado por `[A-ZÀ-Ú]{2,5}` (atributos) ou `N / M` (vitais).
* **Zero Emojis e Anti-Puppeteering**: Todos os outputs e geradores de markdown mantêm conformidade estrita com as diretrizes do RPGPRO.
* **Retrocompatibilidade**: Campanhas sem as novas seções operam normalmente sem exceções ou necessidade de migração forçada.

---

## 3. Work Breakdown Structure

### Fase 1: Fundação & Concessão (Escopo P4.1)

#### Módulo 1: Parsing e Ciclo de Vida de Missões (`council/quests.py`)
- [ ] **Task 1.1**: Criar `council/quests.py` com funções puras de parsing:
  - `parse_quests_from_diario(diario_path: Path) -> List[dict]`
  - Extração resiliente de cabeçalho da missão (ID, tipo, status, fase, contratante, relógio, recompensa, último progresso, XP pago) e lista aninhada de sub-bullets com checkbox (`[ ]` / `[x]`).
- [ ] **Task 1.2**: Implementar função de atualização atômica:
  - `upsert_quest_in_diario(diario_path: Path, ...)` para criar missões, adicionar objetivos, alternar checkboxes e transicionar status.
- [ ] **Task 1.3**: Implementar CLI `cmd_quest` e subcomando `quest` em `lazy_turn.py`:
  - Suportar `--list`, `--json`, `--add`, `--objective`, `--check`, `--complete`, `--fail`, `--block`, `--reopen`.

#### Módulo 2: Motor de Progressão e Curva de XP (`rulesets/progression.py` & `council/ssot.py`)
- [ ] **Task 2.1**: Criar `rulesets/progression.py`:
  - Tabela canônica de concessão de XP (`XP_GRANT_TABLE`).
  - Função de cálculo da curva: `calculate_level_threshold(level: int, base_step: int = 250) -> int`.
  - Função de resolução de ganho: `evaluate_xp_gain(source_code: str, amount: int = None, overrides: list = None) -> int`.
  - Função de recálculo de nível e saldo de pontos: `calculate_progression_state(current_xp: int, ...) -> dict`.
- [ ] **Task 2.2**: Atualizar `council/ssot.py`:
  - Implementar `parse_progression_from_ficha(ficha_path: Path) -> dict`.
  - Implementar `update_progression_in_ficha(ficha_path: Path, xp_add: int = 0, ...) -> dict`.
  - Adicionar testes de isolamento de regex garantindo que vitais e atributos ignorem a seção `### Progressão`.

#### Módulo 3: Integração no Loop de Turno (`lazy_turn.py`)
- [ ] **Task 3.1**: Integrar no `lazy_turn.py prepare`:
  - Ler missões ativas e injetar `step_1_quest_context`.
  - Verificar relógios vinculados críticos ($cur \ge max - 1$) e injetar mandato de risco iminente de falha da missão.
  - Injetar em `step_2_engine_state.protagonist.progression` o nível e status de build do personagem.
- [ ] **Task 3.2**: Integrar no `lazy_turn.py commit`:
  - Adicionar argumentos `--quest-progress`, `--quest-complete`, `--quest-fail`.
  - Processar conclusão de objetivos/missões e aplicar crédito de XP na ficha.
  - Gravar `XP Pago: <valor>` na linha da missão para assegurar idempotência estrita.
  - Aplicar deduplicação de XP entre missão concluída e relógio resolvido no mesmo turno.

#### Módulo 4: Templates e Testes da Fase 1
- [ ] **Task 4.1**: Atualizar templates canônicos:
  - `templates/diario.template.md` (adicionar `### Missões & Objetivos`).
  - `templates/ficha.template.md` (adicionar `### Progressão`).
- [ ] **Task 4.2**: Criar suíte de testes unitários `tests/test_quest_progression.py`:
  - Teste de parse e upsert de missões.
  - Teste de concessão e idempotência de XP (`XP Pago`).
  - Teste de não-colisão com vitais e atributos.
  - Teste de retrocompatibilidade com campanhas existentes sem as seções.

---

### Fase 2: Gasto, Rigor & Lints (Escopo P4.2)

#### Módulo 5: Subcomando de Gasto (`progress`) e Ganhos de Nível
- [ ] **Task 5.1**: Implementar subcomando `progress` em `lazy_turn.py`:
  - Suportar `--list`, `--json`, `--spend-attr`, `--spend-ability`, `--award`.
- [ ] **Task 5.2**: Aplicar ganhos de nível mecânicos em `ficha.md`:
  - Incrementar vitais máximos na ficha (+2 HP, +1 Stamina, +1 Energia/PE).
  - Validar teto de atributos (padrão 20) ao gastar pontos.
  - Exigir flag `--training` ao gastar pontos de habilidade.

#### Módulo 6: Auditoria e Novos Lints no Reviewer (`council/reviewer.py`)
- [ ] **Task 6.1**: Implementar verificadores de integridade de missões:
  - `QUEST_WITHOUT_OBJECTIVES`
  - `QUEST_STALE` (missão sem avanço há mais de 10 turnos)
  - `QUEST_CLOCK_LINK_BROKEN` (apontamento para relógio inexistente)
  - `QUEST_OVERDUE` (relógio rompido com missão ativa)
  - `QUEST_REWARD_PAID_TWICE` (tentativa de duplo pagamento de XP)
  - `XP_MISMATCH` (inconsistência entre histórico do diário e ficha)
- [ ] **Task 6.2**: Integrar verificação de orfandade de missões no comando `lazy_turn.py arc --resolve-clocks`.

---

## 4. Acceptance Criteria Checklist

- [ ] Subcomando `quest --list --json` retorna a árvore completa de missões e objetivos parseados.
- [ ] Subcomando `quest --add` e `quest --check` operam atomicamente em `diario.md`.
- [ ] `commit --quest-complete` credita XP na ficha e estampa `XP Pago: <valor>` no diário de forma idempotente.
- [ ] Relógio rompido vinculado a uma missão dispara `QUEST_OVERDUE` no reviewer sem alterar o status da missão silenciosamente.
- [ ] O payload emitido por `lazy_turn.py prepare` contém `step_1_quest_context` e dados de progressão calibrados.
- [ ] Expressões regulares de vitais e atributos permanecem 100% isoladas de XP e nível.
- [ ] Subcomando `progress --spend-attr` e `--spend-ability` desconta pontos e valida evidência diegética.
- [ ] Suíte de testes automatizados (`tests/test_quest_progression.py` e testes existentes) 100% verde.
