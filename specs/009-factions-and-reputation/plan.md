# Implementation Plan: 009 — Sistema de Facções, Reputação Numérica e Turno de Mundo Off-Screen

**Feature**: `factions-and-reputation`  
**Status**: Ready for Tasks / Implementation  
**Created**: 2026-10-22  
**Target Backlog Phase**: P5 (Fase 3 do Roadmap RPGPRO: Ecologia Política, Vínculos Numéricos e Dinâmica Off-Screen)  
**Base Analisada**: `specs/009-factions-and-reputation/spec.md`, `specs/009-factions-and-reputation/research.md`, `specs/009-factions-and-reputation/data-model.md`, `specs/009-factions-and-reputation/contracts/cli_contracts.md`.

---

## 1. Plan Overview & Objectives

Este plano detalha a implementação técnica da **Fase 3 do RPGPRO**, transformando as facções descritas em `mundo.md` em entidades ativas dotadas de agência mecânica, Poder e projetos autônomos. A reputação qualitativa e estática do protagonista é substituída por uma escala discreta simétrica de 7 escalões (-3 a +3), lastreada em saldos auditáveis de Favores e Débitos, integrada diretamente ao loop de turnos (`prepare` e `commit`), às missões contratadas e ao subsistema de auditoria contínua (`council/reviewer.py`).

### Objetivos Centrais:
1. **Módulo de Domínio (`council/factions.py`)**:
   - Implementar parsers e manipuladores para facções em `mundo.md` e reputação/favores em `ficha.md`.
   - Garantir compatibilidade retroativa e enriquecimento progressivo de campanhas legadas.
   - Padrão atômico de escrita única por chamada de arquivo.
2. **Subcomando CLI `lazy_turn.py faction`**:
   - Fornecer consulta legível e JSON (`--list`, `--json`), cadastro (`--add`), ajuste de reputação (`--rep`), favores (`--favor`), débitos (`--debt`) e simulação do turno off-screen (`--tick`).
3. **Automação Reativa de Contratos no `commit`**:
   - Integrar `--quest-complete` e `--quest-fail` para bonificar (+1 rep / +1 favor) ou penalizar (-1 rep / +1 débito) o herói perante a facção contratante da missão.
   - Suporte a flags explícitas `--faction-rep`, `--faction-favor`, `--faction-debt` no commit.
4. **Contexto Político no `prepare`**:
   - Injetar `step_1_faction_context` no payload JSON com reputações relevantes, bônus/penalidades situacionais de DC para testes sociais e diretrizes de interpretação para NPCs.
5. **Turno de Facções Off-Screen (`faction --tick`)**:
   - Simular o avanço de projetos autônomos e relógios narrativos ativos das facções com base em seu atributo de Poder (1 a 5).
6. **Lints Determinísticos no Revisor (`council/reviewer.py`)**:
   - Criar linters determinísticos `FACTION_UNKNOWN`, `FACTION_ORPHANED_NPC`, `FACTION_ATTITUDE_DESYNC` e `FACTION_REP_MISMATCH`.
7. **Suíte de Testes Automatizada & Portabilidade sob Sandbox**:
   - Adicionar suíte dedicada `tests/test_factions_reputation.py` e testes de contrato em `tests/test_cli_contracts.py`.
   - Garantir 100% de execução verde no sandbox sem elevação de privilégios.

---

## 2. Technical Context & Constitution Gates

* **Invariante dos 5 Arquivos SSOT**:
  - `mundo.md`: Dono textual da existência de facções, atributos e dinâmicas inter-facções.
  - `ficha.md`: Dono textual da reputação, favores e débitos do protagonista.
  - `npcs.md`: Dono textual das afiliações individuais dos personagens secundários.
  - `diario.md`: Dono textual do ledger auditável de reputação e relógios de facção.
  - `regras.md`: Dono textual das regras e overrides do sistema mecânico.
* **Ponytail Standard Library First**:
  - Implementação 100% pura em Python Standard Library (`re`, `pathlib`, `json`, `argparse`, `shutil`, `unittest`). Zero novas dependências de terceiros.
* **Padrão de Escrita Atômica Única (Single-Write Pattern)**:
  - Todas as mutações em arquivos realizam leitura única em memória, validação/computação e gravação única atômica ao final.
* **Sandbox Zero-Crash**:
  - Uso exclusivo do diretório `.tmp/test_scratch/` com permissão herdada (zero chamadas a `tempfile.mkdtemp`).
* **Zero Emojis e Anti-Puppeteering**:
  - Saídas limpas, sem emojis, preservando a agência de NPCs e protagonista.

---

## 3. Work Breakdown Structure

### Módulo 1: Domínio de Facções e Parsers em `mundo.md` (`council/factions.py`)
- [ ] **Task 1.1**: Criar `council/factions.py` com dataclasses/estruturas tipadas para `Faction`, `FactionReputation` e `FactionLedgerEntry`.
- [ ] **Task 1.2**: Implementar `parse_factions_from_mundo(mundo_path: Path)` extraindo tags `[TAG]`, nome, poder (1..5), escala, relógio vinculado e rivais, tolerando formatos legados sem tag.
- [ ] **Task 1.3**: Implementar `upsert_faction_in_mundo(mundo_path: Path, ...)` com inserção estruturada sob `## 4. Facções, Forças Ativas & Alianças` garantindo escrita única.

### Módulo 2: Reputação, Favores e Débitos em `ficha.md`
- [ ] **Task 2.1**: Implementar `parse_reputation_from_ficha(ficha_path: Path)` com suporte tanto a sub-bullets estruturados quanto à linha única legada `* **Reputação com Facções:** ...`.
- [ ] **Task 2.2**: Implementar mapeador dos 7 escalões canônicos com clamping estrito em `[-3, +3]`.
- [ ] **Task 2.3**: Implementar `update_reputation_in_ficha(ficha_path: Path, faction_name: str, score_delta: int = 0, favors_delta: int = 0, debts_delta: int = 0)`.

### Módulo 3: Ledger no Diário e Automação Reativa de Contratos
- [ ] **Task 3.1**: Implementar `parse_faction_ledger_from_diario(diario_path: Path)` e `append_faction_ledger_entry(diario_path: Path, ...)`.
- [ ] **Task 3.2**: No `lazy_turn.py cmd_commit`:
  - Processar flags `--faction-rep`, `--faction-favor`, `--faction-debt`.
  - Ao concluir missão contratada (`--quest-complete`), aplicar automaticamente `+1` reputação e `+1` favor com o contratante, gravando no ledger.
  - Ao falhar missão contratada (`--quest-fail`), aplicar penalidade de `-1` reputação e `+1` débito.

### Módulo 4: Subcomando CLI `lazy_turn.py faction` e Turno Off-Screen
- [ ] **Task 4.1**: Adicionar subparser `faction` em `build_cli()` com `--list`, `--json`, `--add`, `--power`, `--scale`, `--clock`, `--desc`, `--rep`, `--reason`, `--favor`, `--debt`, `--tick`.
- [ ] **Task 4.2**: Implementar `cmd_faction(...)` em `lazy_turn.py` com formatação legível e exportação JSON.
- [ ] **Task 4.3**: Implementar a lógica do turno off-screen (`--tick`) avançando relógios de facções ativas com base em seu Poder e emitindo relatório factual.

### Módulo 5: Injeção de Contexto Político no `prepare`
- [ ] **Task 5.1**: Em `lazy_turn.py cmd_prepare`, inspecionar NPCs em cena e local para identificar facções relevantes.
- [ ] **Task 5.2**: Injetar `step_1_faction_context` no payload JSON contendo score, tier, modificadores de DC em testes sociais e diretrizes de interpretação.

### Módulo 6: Lints Determinísticos no Revisor & Testes
- [ ] **Task 6.1**: Implementar no `council/reviewer.py`:
  - `FACTION_UNKNOWN` (`HIGH`): Ficha lista reputação com facção inexistente em `mundo.md`.
  - `FACTION_ORPHANED_NPC` (`MEDIUM`): NPC afiliado a facção inexistente.
  - `FACTION_ATTITUDE_DESYNC` (`HIGH`): NPC com atitude amigável para protagonista com reputação `-2` ou `-3` sem justificativa psicológica.
  - `FACTION_REP_MISMATCH` (`HIGH`): Total de reputação na ficha diverge da soma do histórico do diário.
- [ ] **Task 6.2**: Criar suíte de testes `tests/test_factions_reputation.py` cobrindo o ciclo de vida completo de facções, clamping de reputação, favores, avanço de missões, turno off-screen e lints.
- [ ] **Task 6.3**: Adicionar testes de contratos em `tests/test_cli_contracts.py` garantindo que o subcomando `faction` seja testado diretamente na interface de CLI.
- [ ] **Task 6.4**: Executar suíte completa assegurando 100% de aprovação e zero regressões nas 3 campanhas reais.
