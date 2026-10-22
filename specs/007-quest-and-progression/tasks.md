# Implementation Tasks: 007 — Sistema de Missões e Sistema de Progressão (XP)

**Feature**: `quest-and-progression`  
**Spec**: [spec.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/007-quest-and-progression/spec.md)  
**Plan**: [plan.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/007-quest-and-progression/plan.md)  
**Status**: Completed  

---

## Phase 1: Setup & Pre-Flight Checks

- [X] T001 Verify baseline CLI and current test suite passing with 100% success via `python -m unittest discover tests`

---

## Phase 2: Foundational Tasks

- [X] T002 Implement foundational regex constants and data structures for quests and progression in `council/quests.py` and `rulesets/progression.py`

---

## Phase 3: User Story 1 - Quest Lifecycle & CLI Management (Priority: P1)

*Goal*: Enable deterministic creation, updating, state transitions, and querying of quests and checkboxes in `diario.md` via `lazy_turn.py quest`.  
*Independent Test Criteria*: Executing `python lazy_turn.py quest --campaign <id> --add ...`, `--check ...`, and `--list --json` creates parseable entries in `diario.md` with status `ACTIVE`, toggles `[ ]` to `[x]`, and returns structured JSON; empty/missing quest section returns `[]` without error.

- [X] T003 [P] [US1] Implement `parse_quests_from_diario(diario_path: Path) -> list` in `council/quests.py` extracting headers (`ID`, `type`, `status`, `phase`, `contractor`, `clock`, `reward`, `last_progress`, `xp_paid`) and nested bullet checkboxes (`* [ ]` / `* [x]`)
- [X] T004 [P] [US1] Implement atomic writer `upsert_quest_in_diario(diario_path: Path, ...)` in `council/quests.py` supporting quest creation, objective appending, checkbox toggling, and state transitions (`ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`, `--reopen`)
- [X] T005 [US1] Implement CLI function `cmd_quest(campaign_id: str, ...)` and argparse subparser `quest` in `lazy_turn.py` with flags `--list`, `--json`, `--add`, `--type`, `--objective`, `--check`, `--complete`, `--fail`, `--block`, `--reopen`
- [X] T006 [US1] Add unit tests in `tests/test_quest_progression.py` verifying quest parsing, atomic upserting, checkbox toggling, and CLI subcommands

---

## Phase 4: User Story 2 - Idempotent Progression & XP Engine (Priority: P1)

*Goal*: Calculate level thresholds, grant XP deterministically on completed objectives/quests, and ensure strict idempotency via `XP Pago: <valor>` markers.  
*Independent Test Criteria*: Running `lazy_turn.py commit --quest-complete <ID>` awards the defined XP once, stamps `XP Pago` in `diario.md`, and updates `ficha.md`; repeating the commit is a no-op that does not duplicate XP.

- [X] T007 [P] [US2] Implement progression rules and level threshold formula $T(L) = 250 \times (L - 1) \times L / 2$ with campaign overrides support in `rulesets/progression.py`
- [X] T008 [P] [US2] Implement deterministic grant table `XP_GRANT_TABLE` and resolution helper `evaluate_xp_gain(source_code: str, amount: int = None, overrides: list = None) -> int` in `rulesets/progression.py`
- [X] T009 [US2] Implement atomic reader `parse_progression_from_ficha(ficha_path: Path) -> dict` and writer `update_progression_in_ficha(ficha_path: Path, xp_add: int = 0, ...) -> dict` in `council/ssot.py`
- [X] T010 [US2] Add flags `--quest-progress`, `--quest-complete`, `--quest-fail` to `cmd_commit` in `lazy_turn.py` to award XP on completion, stamp `XP Pago: <valor>` in `diario.md`, and update progression in `ficha.md`
- [X] T011 [US2] Add unit tests in `tests/test_quest_progression.py` asserting exact XP calculation, level-up calculation, and strict idempotency of `XP Pago`

---

## Phase 5: User Story 3 - Regex Collision Shielding in `ficha.md` (Priority: P1)

*Goal*: Guarantee that XP, level, and points never collide with the legacy attribute regex `[A-ZÀ-Ú]{2,5}` or vitais regex `**Rótulo:** N / M`.  
*Independent Test Criteria*: `parse_ficha_md(ficha_path)["vitals"]` does not contain `xp` or `experiência`; `parse_ficha_md(ficha_path)["stats"]` does not contain `xp`; debiting vitais via `--cost` never alters XP.

- [X] T012 [P] [US3] Enforce canonical progression formatting `* **Experiência (XP):** <valor>` (strictly without slash `/`) in `council/ssot.py` and `templates/ficha.template.md`
- [X] T013 [US3] Scope vitais and stats parser functions in `council/ssot.py` to read strictly within their markdown section boundaries (`### Vitais & Recursos`, `### Atributos`)
- [X] T014 [US3] Add dedicated regression test in `tests/test_quest_progression.py` verifying that `ficha["vitals"]` and `ficha["stats"]` remain free of progression keys across multiple parse/write cycles

---

## Phase 6: User Story 4 - Teleological Context & Preparation Payload (Priority: P1)

*Goal*: Inject active quests, pending objectives, and protagonist level/progression into `lazy_turn.py prepare` so scenes exert purposeful pressure.  
*Independent Test Criteria*: Executing `python lazy_turn.py prepare --campaign <id> --no-roll --json` outputs `step_1_quest_context` and `step_2_engine_state.protagonist.progression` conforming to interface contracts without breaking payload snapshot tests.

- [X] T015 [US4] Update `cmd_prepare` in `lazy_turn.py` to inject `step_1_quest_context` with active quests, open objectives, contractors, and pressure mandates
- [X] T016 [US4] Update `cmd_prepare` in `lazy_turn.py` to inject `step_2_engine_state.protagonist.progression` containing level, XP, next threshold, and scale guidance
- [X] T017 [US4] Update `tests/test_boundary_contracts.py` to validate that new progression and quest payload keys pass snapshot integrity checks additively

---

## Phase 7: User Story 5 - Threat Clocks & Quest Integration (Priority: P1)

*Goal*: Synchronize linked threat clocks with quest tension: warn on critical clocks, emit `QUEST_OVERDUE` on breach without silent quest failure, and deduplicate XP.  
*Independent Test Criteria*: A quest linked to a clock at $cur \ge max - 1$ emits critical urgency in `prepare`; a breached clock triggers `QUEST_OVERDUE` in `review` while keeping quest `ACTIVE`; resolving a quest and its linked clock simultaneously grants only quest XP.

- [X] T018 [P] [US5] Add critical clock detection in `lazy_turn.py prepare` when a linked clock is at $cur \ge max - 1$, injecting an urgent mandate into `step_1_quest_context`
- [X] T019 [P] [US5] Implement `QUEST_OVERDUE` and `QUEST_CLOCK_LINK_BROKEN` lints in `council/reviewer.py` to flag breached clocks and broken linkages without altering quest status automatically
- [X] T020 [US5] Implement XP deduplication in `lazy_turn.py commit` when `--quest-complete` coincides with the resolution of its nominally linked clock
- [X] T021 [US5] Update `lazy_turn.py arc --resolve-clocks` to audit active quests linked to archived clocks and output pending quest warnings
- [X] T022 [US5] Add unit tests in `tests/test_quest_progression.py` verifying critical clock warning in prepare, `QUEST_OVERDUE` lint emission, and XP dedup logic

---

## Phase 8: User Story 6 - Progression CLI & Reviewer Audit Lints (Priority: P2)

*Goal*: Provide character build advancement via `lazy_turn.py progress` and complete reviewer audit coverage for quests and XP.  
*Independent Test Criteria*: Running `lazy_turn.py progress --spend-attr` increments stat up to ceiling; `--spend-ability` consumes ability point with `--training` validation; reviewer flags `QUEST_WITHOUT_OBJECTIVES`, `QUEST_STALE`, `QUEST_REWARD_PAID_TWICE`, and `XP_MISMATCH`.

- [X] T023 [P] [US6] Implement CLI function `cmd_progress(campaign_id: str, ...)` and subparser `progress` in `lazy_turn.py` supporting `--list`, `--json`, `--spend-attr`, `--spend-ability`, `--training`, and `--award`
- [X] T024 [P] [US6] Implement stat spending logic in `council/ssot.py` verifying available attribute points, respecting the 20 stat ceiling, and updating vitais bonuses on level-up
- [X] T025 [P] [US6] Implement ability spending logic in `council/ssot.py` consuming ability points and validating presence of diegetic training evidence
- [X] T026 [US6] Implement reviewer integrity checks `QUEST_WITHOUT_OBJECTIVES`, `QUEST_STALE`, `QUEST_REWARD_PAID_TWICE`, and `XP_MISMATCH` in `council/reviewer.py`
- [X] T027 [US6] Add unit tests in `tests/test_quest_progression.py` validating stat/ability point consumption and all new reviewer quest lints

---

## Phase 9: Polish, Templates & End-to-End Verification

- [X] T028 [P] Update canonical templates `templates/diario.template.md` (add `### Missões & Objetivos`) and `templates/ficha.template.md` (add `### Progressão`)
- [X] T029 Execute all runnable end-to-end verification scenarios defined in `specs/007-quest-and-progression/quickstart.md`
- [X] T030 Execute full test suite `python -m unittest discover tests` and verify 100% green execution

---

## Dependencies & Completion Order

```
Phase 1: Setup (T001)
   │
Phase 2: Foundational Structures (T002)
   │
   ├─────────────────────────────────────────────────┬─────────────────────────────────────────────────┐
   ▼                                                 ▼                                                 ▼
Phase 3: US1 Quest Lifecycle (T003-T006)          Phase 4: US2 Idempotent XP Engine (T007-T011)     Phase 5: US3 Regex Shielding (T012-T014)
   │                                                 │                                                 │
   └─────────────────────────────────────────────────┼─────────────────────────────────────────────────┘
                                                     │
                           ┌─────────────────────────┴─────────────────────────┐
                           ▼                                                   ▼
                Phase 6: US4 Payload (T015-T017)                   Phase 7: US5 Clocks (T018-T022)
                           │                                                   │
                           └─────────────────────────┬─────────────────────────┘
                                                     │
                                                     ▼
                                      Phase 8: US6 Progression CLI & Lints (T023-T027)
                                                     │
                                                     ▼
                                      Phase 9: Polish & Verification (T028-T030)
```
