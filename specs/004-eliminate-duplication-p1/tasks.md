# Implementation Tasks: P1 Deduplication & Cognitive Load Reduction

**Feature**: `eliminate-duplication-p1`  
**Spec**: [spec.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/004-eliminate-duplication-p1/spec.md)  
**Plan**: [plan.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/004-eliminate-duplication-p1/plan.md)  
**Status**: Completed  

---

## Phase 1: Setup & Pre-Flight Checks

- [X] T001 Verify baseline CLI and test environment for `tests/test_cli_contracts.py` in `c:/Users/Konor/Documents/RPGPRO/tests/test_cli_contracts.py`

---

## Phase 2: Foundational Tasks (Ruleset & Template Infrastructure)

- [X] T002 [P] Update `templates/regras.template.md` in `c:/Users/Konor/Documents/RPGPRO/templates/regras.template.md` to omit generic DC 10/15/20/25 bullets and state inheritance from the universal Grade 1 ruleset
- [X] T003 [P] Update `council/helpers.py` in `c:/Users/Konor/Documents/RPGPRO/council/helpers.py` to remove `{{EXEMPLO_DC_10}}` through `{{EXEMPLO_DC_25}}` string replacements and align `init-campaign` with the refactored `regras.template.md`

---

## Phase 3: User Story 1 - Minimalist Root Router (Priority: P1)

*Goal*: Condense `AGENTS.md` to $\le 15$ lines as a pure router defining precedence, campaign detection, skill routing, and the basic turn loop.  
*Independent Test Criteria*: `(Get-Content AGENTS.md).Count -le 15` and zero occurrences of prose formatting keywords (`travessão`, `script teatral`, `Linha 1 Obrigatória`, `4 Batidas`).

- [X] T004 [US1] Rewrite `AGENTS.md` in `c:/Users/Konor/Documents/RPGPRO/AGENTS.md` to a strict $\le 15$-line router focusing strictly on sovereignty precedence, campaign detection, skill routing, and the basic turn loop (`prepare` -> obey `step_3_writer_mandate` -> `commit`)

---

## Phase 4: User Story 2 - Dynamic Prose Mandate as SSOT (Priority: P1)

*Goal*: Establish `council/writer.py` payload (`step_3_writer_mandate`) as the authoritative source of truth for text generation and refactor documentation to instruct obedience, explain the architectural rationale, and maintain high-level negative constraints.  
*Independent Test Criteria*: `lazy_turn.py prepare` outputs `step_3_writer_mandate`; `rpg-narrative-engine/SKILL.md` delegates literary style directly to the JSON payload.

- [X] T005 [P] [US2] Update `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-narrative-engine/SKILL.md` to instruct strict obedience to `step_3_writer_mandate` from the JSON payload in Section 2 (Redação)
- [X] T006 [P] [US2] Refactor `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-narrative-engine/references/1_turn_discipline_and_prose.md` to document the architectural rationale of dynamic scene mandates and preserve only high-level anti-patterns (Anti-Puppeteering, Zero Emojis, Zero Script Format, Actionable Dramatic Hook)
- [X] T007 [US2] Synchronize narrative engine skill updates to global directory in `C:/Users/Konor/.gemini/config/skills/rpg-narrative-engine/SKILL.md` and `C:/Users/Konor/.gemini/config/skills/rpg-narrative-engine/references/1_turn_discipline_and_prose.md`

---

## Phase 5: User Story 3 - Clean Demarcation: Showrunner vs Module 3 (Priority: P1)

*Goal*: Eliminate duplicated CLI command blocks in Module 3 (`references/3_campaign_crud_and_state.md`), preserving exclusively the Markdown schemas for `diario.md` and delegating operational usage to `rpg-showrunner`.  
*Independent Test Criteria*: Searching for `python lazy_turn.py clock` or `python lazy_turn.py plan` in `3_campaign_crud_and_state.md` yields zero hits.

- [X] T008 [US3] Remove redundant CLI command blocks for `lazy_turn.py clock` and `lazy_turn.py plan` from Sections 4 and 6 of `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-narrative-engine/references/3_campaign_crud_and_state.md`, preserving the Markdown schemas for threat clocks, scene queue, and milestones, and adding explicit pointers to `rpg-showrunner`
- [X] T009 [US3] Synchronize Module 3 changes to global reference in `C:/Users/Konor/.gemini/config/skills/rpg-narrative-engine/references/3_campaign_crud_and_state.md`

---

## Phase 6: User Story 4 - Centralized Difficulty Class (DC) Ladder (Priority: P1)

*Goal*: Remove generic DC 10/15/20/25 lists from the 3 active campaigns, leaving them to declare only diegetic rules, resource economies, and optional overrides.  
*Independent Test Criteria*: Searching for `"DC 10 (Ação Básica sob Pressão)"` across `campaigns/*/regras.md` yields zero occurrences.

- [X] T010 [P] [US4] Remove standard DC ladder from `c:/Users/Konor/Documents/RPGPRO/campaigns/dinastia_cinzas/regras.md` and declare universal ruleset inheritance
- [X] T011 [P] [US4] Remove standard DC ladder from `c:/Users/Konor/Documents/RPGPRO/campaigns/imperio_valiria/regras.md` and declare universal ruleset inheritance
- [X] T012 [P] [US4] Remove standard DC ladder from `c:/Users/Konor/Documents/RPGPRO/campaigns/perpetuos_terra_incognita/regras.md` and declare universal ruleset inheritance

---

## Phase 7: Polish & Automated Contract Tests

- [X] T013 Add automated unit tests to `c:/Users/Konor/Documents/RPGPRO/tests/test_cli_contracts.py` to enforce `AGENTS.md` line count ($\le 15$), absence of CLI blocks in Module 3, and absence of generic DC ladder in active campaigns
- [X] T014 Execute the complete test suite (`python -m unittest tests/test_cli_contracts.py`) and verify quickstart checks in `c:/Users/Konor/Documents/RPGPRO/specs/004-eliminate-duplication-p1/quickstart.md`

---

## Dependencies & Completion Order

```
Phase 1: Setup (T001)
   │
Phase 2: Foundational Templates & Helpers (T002, T003)
   │
   ├───────────────────────────┬───────────────────────────┬───────────────────────────┐
   ▼                           ▼                           ▼                           ▼
Phase 3: US1 Router (T004)  Phase 4: US2 Mandate (T005-T007) Phase 5: US3 Módulo 3 (T008-T009) Phase 6: US4 DC Ladder (T010-T012)
   │                           │                           │                           │
   └───────────────────────────┴───────────────────────────┴───────────────────────────┘
                                           │
                                           ▼
                       Phase 7: Polish & Automated Tests (T013, T014)
```

### Parallel Opportunities Identified
- T002 and T003 can run in parallel (template vs helper code).
- T005 and T006 can run in parallel (SKILL.md vs Module 1 prose reference).
- T010, T011, and T012 can run in parallel across the three campaign folders.
- US1, US2, US3, and US4 touch distinct files and can be implemented in any order once Phase 2 is complete.

### MVP Scope Recommendation
The core cognitive load reduction is realized immediately upon completing **Phase 3 (US1)** and **Phase 4 (US2)**. Completing all 4 User Stories achieves 100% elimination of architectural duplication.
