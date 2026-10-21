# Implementation Plan: P1 Deduplication & Cognitive Load Reduction

**Feature**: `eliminate-duplication-p1`  
**Status**: Ready for Implementation  
**Created**: 2026-10-21  
**Target Backlog Phase**: P1 (Architectural Review Remediation)

---

## 1. Plan Overview & Objectives

This implementation plan delivers the critical **P1** refactoring identified in the architectural review (`DECISOES_ARQUITETURA.md`). The primary objective is to drastically reduce neural context overhead and eliminate conflicting prompt rules across the RPGPRO ecosystem.

### Core Deliverables:
1. **Minimalist `AGENTS.md` Router**:
   - Condense the 72-line root rule file down to $\le 15$ lines.
   - Establish pure routing: campaign identification, skill dispatch, sovereignty hierarchy (Grades 1–3), and the 3-step action loop (`prepare` -> obey `step_3_writer_mandate` -> `commit`).
   - Remove all detailed prose and dice rules from the root rule.
2. **Prose Mandates SSOT Delegation**:
   - Establish `council/writer.py` and the runtime payload `step_3_writer_mandate` as the sole authority for literary direction.
   - Refactor `rpg-narrative-engine/SKILL.md` and `references/1_turn_discipline_and_prose.md` to instruct the model to obey the dynamic payload, keeping only negative constraints (Anti-Puppeteering, Zero Emojis, Zero Script Formatting `Nome: Fala`, Actionable Dramatic Hook).
3. **Showrunner vs Module 3 Demarcation**:
   - Remove redundant CLI command blocks (`lazy_turn.py clock` and `lazy_turn.py plan`) from `references/3_campaign_crud_and_state.md`.
   - Maintain exclusively the Markdown schema representation of `diario.md` sections in Module 3.
   - Ensure `rpg-showrunner/SKILL.md` is the sole owner of operational instructions for clocks, queue, and arcs.
4. **DC Ladder Centralization**:
   - Remove the duplicated DC 10/15/20/25 blocks from the 3 active campaigns (`dinastia_cinzas`, `imperio_valiria`, `perpetuos_terra_incognita`).
   - Update `templates/regras.template.md` and `council/helpers.py` (`init-campaign`) to reflect inheritance from the universal ruleset (Grade 1), leaving campaign files to declare diegetic rules, resource economies, and optional overrides.
5. **Contract Test Expansion**:
   - Add automated test assertions in `tests/test_cli_contracts.py` to enforce `AGENTS.md` line count ($\le 15$), zero CLI commands in Module 3, and zero generic DC blocks in campaign `regras.md` files.

---

## 2. Technical Context & Constitution Gates

* **Zero External Dependencies**: Pure Python standard library and standard Markdown.
* **Non-Destructive State Execution**: Existing player vitais, clocks, notes, and campaign diaries are fully preserved.
* **Deterministic Runtime Invariance**: `lazy_turn.py prepare` already outputs `step_3_writer_mandate`, ensuring zero breaking changes to the execution pipeline.

---

## 3. Work Breakdown Structure

### Phase 1: Minimalist Router Implementation (`AGENTS.md`)
- [ ] **Task 1.1**: Rewrite `AGENTS.md` to $\le 15$ lines focusing strictly on sovereignty precedence, campaign detection, skill routing, and the basic turn loop.
- [ ] **Task 1.2**: Remove all prose formatting, dialogue examples, and detailed CLI templates from `AGENTS.md`.

### Phase 2: Prose Mandates Delegation (`rpg-narrative-engine/SKILL.md` & `references/1_turn_discipline_and_prose.md`)
- [ ] **Task 2.1**: Update `rpg-narrative-engine/SKILL.md` to mandate adherence to `step_3_writer_mandate` from the JSON payload.
- [ ] **Task 2.2**: Refactor `references/1_turn_discipline_and_prose.md` to document the architectural rationale of dynamic mandates and preserve only high-level anti-patterns (Anti-Puppeteering, Zero Emojis, Zero Script Format, Actionable Dramatic Hook).

### Phase 3: Module 3 Schema Demarcation (`references/3_campaign_crud_and_state.md`)
- [ ] **Task 3.1**: Remove duplicated CLI command blocks for `lazy_turn.py clock` from Section 4 of `references/3_campaign_crud_and_state.md`.
- [ ] **Task 3.2**: Remove duplicated CLI command blocks for `lazy_turn.py plan` from Section 6 of `references/3_campaign_crud_and_state.md`.
- [ ] **Task 3.3**: Add explicit pointers in Sections 4 and 6 directing operational usage to `rpg-showrunner`.

### Phase 4: DC Ladder Extraction & Campaign Cleansing
- [ ] **Task 4.1**: Remove the 4-line standard DC ladder from `campaigns/dinastia_cinzas/regras.md`.
- [ ] **Task 4.2**: Remove the 4-line standard DC ladder from `campaigns/imperio_valiria/regras.md`.
- [ ] **Task 4.3**: Remove the 4-line standard DC ladder from `campaigns/perpetuos_terra_incognita/regras.md`.
- [ ] **Task 4.4**: Update `templates/regras.template.md` to omit generic DC examples and document the override format.
- [ ] **Task 4.5**: Update `council/helpers.py` (`init-campaign`) replacements to align with the new `regras.template.md`.

### Phase 5: Verification & Contract Test Suite
- [ ] **Task 5.1**: Add automated unit tests to `tests/test_cli_contracts.py` verifying:
  - `AGENTS.md` line count is $\le 15$.
  - `references/3_campaign_crud_and_state.md` contains no `lazy_turn.py clock` or `lazy_turn.py plan` execution blocks.
  - Active campaign `regras.md` files do not duplicate standard DC ladder definitions.
- [ ] **Task 5.2**: Execute the complete test suite (`python -m unittest tests/test_cli_contracts.py`) to confirm clean pass.

---

## 4. Acceptance Criteria Checklist

- [ ] `AGENTS.md` has $\le 15$ lines of non-empty content and zero prose micro-rules.
- [ ] `rpg-narrative-engine/SKILL.md` delegates literary style to `step_3_writer_mandate`.
- [ ] `references/3_campaign_crud_and_state.md` contains only Markdown schemas for `diario.md`, with zero redundant CLI blocks.
- [ ] No active campaign `regras.md` file repeats the universal DC 10/15/20/25 list.
- [ ] `templates/regras.template.md` and `council/helpers.py` reflect the refactored schema.
- [ ] All automated contract tests pass with 100% success.
