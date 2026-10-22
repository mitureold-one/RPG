# Implementation Tasks: P3 Transformação de Regra em Verificação

**Feature**: `rule-verification-p3`  
**Spec**: [spec.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/006-rule-verification-p3/spec.md)  
**Plan**: [plan.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/006-rule-verification-p3/plan.md)  
**Status**: Completed  

---

## Phase 1: Setup & Pre-Flight Checks

- [X] T001 Verify baseline CLI and existing contract test suite passing via `python -m unittest discover tests`

---

## Phase 2: Foundational Tasks

- [X] T002 Implement modular regex constants and helper signature `check_prose_lints(text: str, context_label: str)` in `council/reviewer.py`

---

## Phase 3: User Story 1 - Prose Lints in Chronicle Reviewer (Priority: P1)

*Goal*: Enforce strict literary quality rules in `lazy_turn.py review` by automatically flagging emojis, theatrical script format (`[Nome]:`), and clichéd fourth-wall closing questions ("O que você faz?").  
*Independent Test Criteria*: Executing `check_prose_lints` or `cmd_review` on text containing emojis, `[Nome]:`, or "O que você faz?" produces `EMOJI_DETECTED`, `SCRIPT_FORMAT_DETECTED`, and `FOURTH_WALL_QUESTION` issues; clean literary prose with em-dashes (`—`) produces zero lint issues.

- [X] T003 [P] [US1] Implement Unicode emoji detection regex covering standard pictorial ranges (`\U0001F300-\U0001FAFF`, `\u2600-\u27BF`) and emit `EMOJI_DETECTED` issues in `council/reviewer.py`
- [X] T004 [P] [US1] Implement multiline regex detecting theatrical dialogue format (`r"^\s*\[[A-Za-zÀ-ÖØ-öø-ÿ\s]{2,30}\]\s*:"` and `r"^\s*[A-ZÀ-ÖØ-ß][A-Za-zÀ-ÖØ-öø-ÿ\s]{1,25}\s*:\s*[\"“']"`) and emit `SCRIPT_FORMAT_DETECTED` issues in `council/reviewer.py`
- [X] T005 [P] [US1] Implement case-insensitive regex detecting clichéd fourth-wall closing questions ("O que você faz?", "Qual sua ação?") and emit `FOURTH_WALL_QUESTION` issues in `council/reviewer.py`
- [X] T006 [US1] Integrate `check_prose_lints` into the main audit loop of `cmd_review` in `council/reviewer.py` to scan `last_turn_summary` and recent turns in `diario.md`
- [X] T007 [US1] Add unit tests in `tests/test_cli_contracts.py` validating positive detection and negative non-interference of all three prose lints

---

## Phase 4: User Story 2 - Typed Machine-Readable Overrides in `regras.md` (Priority: P1)

*Goal*: Structure the `overrides:` block in `regras.md` into typed, machine-readable specifications (`id`, `type`, `target`, `value`, `condition`), parse them in SSOT, and surface them in `lazy_turn.py prepare`.  
*Independent Test Criteria*: All 3 active campaigns and the template contain structured `overrides:`; `lazy_turn.py prepare --no-roll --json` outputs structured dictionaries under `step_1_gm_arbitration.overrides`.

- [X] T008 [US2] Implement structured YAML parser in `council/helpers.py` (or `council/ssot.py`) to parse `overrides:` as a list of typed objects with fields `id`, `type`, `target`, `value`, `condition`
- [X] T009 [US2] Update `cmd_prepare` in `lazy_turn.py` to inject the parsed typed overrides under `prep_payload["step_1_gm_arbitration"]["overrides"]`
- [X] T010 [P] [US2] Update canonical template `templates/regras.template.md` with the typed `overrides` schema
- [X] T011 [P] [US2] Update active campaigns (`campaigns/dinastia_cinzas/regras.md`, `campaigns/imperio_valiria/regras.md`, `campaigns/perpetuos_terra_incognita/regras.md`) with typed `overrides` specifications
- [X] T012 [US2] Add unit tests in `tests/test_cli_contracts.py` asserting that overrides are parsed into typed dictionaries and exposed in the preparation payload

---

## Phase 5: User Story 3 - Boundary Testing Suite (Priority: P1)

*Goal*: Build automated boundary tests ensuring zero diegetic noun leakage in universal skills, 100% CLI vs documentation contract alignment, and payload snapshot immutability for `prepare`.  
*Independent Test Criteria*: `tests/test_boundary_contracts.py` runs as part of `python -m unittest discover tests` and passes with 100% success.

- [X] T013 [P] [US3] Create `tests/test_boundary_contracts.py` with dynamic noun leakage test extracting protagonists and NPCs from all campaigns and asserting 0% occurrences in all skill files
- [X] T014 [P] [US3] Implement documentation contract test in `tests/test_boundary_contracts.py` verifying that every `python lazy_turn.py ...` command in `README.md`, `DECISOES_ARQUITETURA.md`, and skills parses cleanly against `build_cli()`
- [X] T015 [P] [US3] Implement payload snapshot test in `tests/test_boundary_contracts.py` verifying that `lazy_turn.cmd_prepare` output matches the frozen JSON contract schema for top-level steps and mandatory fields
- [X] T016 [US3] Verify seamless discovery and execution of both `test_cli_contracts.py` and `test_boundary_contracts.py` via `python -m unittest discover tests`

---

## Phase 6: Polish & Verification

- [X] T017 Execute all end-to-end verification scenarios defined in `specs/006-rule-verification-p3/quickstart.md`
- [X] T018 Update `DECISOES_ARQUITETURA.md` marking the P3 roadmap phase as completed and verified

---

## Dependencies & Completion Order

```
Phase 1: Setup (T001)
   │
Phase 2: Foundational Regex Helpers (T002)
   │
   ├─────────────────────────────────────────────────┬─────────────────────────────────────────────────┐
   ▼                                                 ▼                                                 ▼
Phase 3: US1 Prose Lints (T003-T007)              Phase 4: US2 Typed Overrides (T008-T012)          Phase 5: US3 Boundary Tests (T013-T016)
   │                                                 │                                                 │
   └─────────────────────────────────────────────────┴─────────────────────────────────────────────────┘
                                                     │
                                                     ▼
                                 Phase 6: Polish & Verification (T017-T018)
```

### Parallel Opportunities Identified
- Within US1: T003 (emoji regex), T004 (script regex), and T005 (fourth wall regex) can be written and tested in parallel.
- Within US2: T010 (template) and T011 (active campaigns) can be updated in parallel.
- Within US3: T013 (leakage test), T014 (CLI doc contract), and T015 (snapshot test) can be authored in parallel.
- Across stories: US1 (prose lints), US2 (overrides), and US3 (boundary tests) are orthogonal and can be worked on concurrently once foundational T002 is in place.

### MVP Scope Recommendation
Implementing **User Story 1 (Prose Lints)** and **User Story 2 (Typed Overrides)** immediately stops prose degradation and disambiguates campaign mechanics. Completing **User Story 3 (Boundary Tests)** provides the permanent CI safety net protecting RPGPRO against regressions.
