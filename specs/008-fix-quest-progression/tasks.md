# Implementation Tasks: 008 — Remediação de Integridade: Sistema de Missões e Progressão (P0–P2)

**Feature**: `fix-quest-progression`  
**Spec**: [spec.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/008-fix-quest-progression/spec.md)  
**Plan**: [plan.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/008-fix-quest-progression/plan.md)  
**Status**: Completed  

---

## Phase 1: Setup & Sandbox Workspace Isolation

- [X] T001 Configure workspace-isolated test scratch directory helper in `tests/test_quest_progression.py` and `tests/test_cli_contracts.py` using `.tmp/test_scratch/` to avoid OS ACL permission failures in sandbox
- [X] T002 [P] Verify current test suite baseline passes with 100% success (27/27) via `python -m unittest discover tests`

---

## Phase 2: Foundational Tasks

- [X] T003 [P] Centralize canonical default quest rewards `DEFAULT_QUEST_REWARDS = {"MAIN": 150, "SIDE": 60, "PERSONAL": 50, "FACTION": 50}` in `rulesets/progression.py`
- [X] T004 [P] Update `calculate_level_from_xp` in `rulesets/progression.py` to enforce `base_step = max(1, base_step)` preventing infinite loops on zero or negative step overrides

---

## Phase 3: User Story 1 - Commit Execution Order & Scope Safety (Priority: P0)

*Goal*: Eliminate `UnboundLocalError` in `lazy_turn.py commit` by calculating `next_turn` before quest processing and ensuring vitals snapshot immediately reflects level-ups.  
*Independent Test Criteria*: Executing `python lazy_turn.py commit --campaign <id> --summary "..." --quest-complete "Q1"` finishes with exit code 0, marks quest `COMPLETED`, awards XP, stamps `XP Pago: 150`, advances turn number, and writes updated vitals snapshot without exceptions.

- [X] T005 [US1] Reorder `cmd_commit` in `lazy_turn.py` to parse `diario_ctx` and compute `next_turn = diario_ctx["last_turn_num"] + 1` before executing quest progression block 3b
- [X] T006 [US1] Ensure `ficha_after = parse_ficha_md(ficha_path)` in `lazy_turn.py` is read after quest/XP processing so `vitals_snapshot` in `diario.md` reflects level-up expansions (+2 HP, +1 Stamina, +1 Energia)
- [X] T007 [US1] Add integration test in `tests/test_cli_contracts.py` validating that `cmd_commit` with `--quest-complete`, `--quest-progress`, and `--quest-fail` runs to completion without `UnboundLocalError`

---

## Phase 4: User Story 2 - Monotonic & Immutable Quest Identity `[Q{N}]` (Priority: P0)

*Goal*: Ensure every quest has an immutable monotonic ID `[Q{N}]` persisted directly in the Markdown header, inserted at the bottom of the section, so additions and reorderings never detach quest identities or XP stamps.  
*Independent Test Criteria*: Adding a quest via `quest --add` assigns $Q(\max(N) + 1)$, appends to the end of the quest section, writes `* **[Q{N}] [{TYPE}] {Title}**`, and subsequent `--complete` or `--check` targets the exact requested ID without shifting indexes.

- [X] T008 [US2] Update `format_quest_header` in `council/quests.py` to format mandatory prefix `* **[{ID}] [{TYPE}] {Title}**`
- [X] T009 [US2] Update `parse_quests_from_diario` in `council/quests.py` to extract explicit `[Q{N}]` from `exp_id` pattern, maintaining sequential fallback `Q1`, `Q2`... only when explicit tag is absent
- [X] T010 [US2] Refactor `upsert_quest_in_diario` (`action == "add"`) in `council/quests.py` to calculate `new_id = f"Q{max(existing_ids) + 1}"` (or `Q1` if empty) and append new quest block at the end of the quest section before next `###` header
- [X] T011 [US2] Refactor quest lookup in `upsert_quest_in_diario` in `council/quests.py` to target the exact quest by its explicit ID `[Q{N}]` using scoped block replacement instead of global text replace
- [X] T012 [US2] Add unit and integration tests in `tests/test_quest_progression.py` verifying monotonic ID generation, end-of-section insertion, and target stability when multiple quests exist

---

## Phase 5: User Story 3 - Single Source of Truth for XP, Ledger & Strict Lints (Priority: P1)

*Goal*: Unify all quest reward defaults to read from `rulesets/progression.py`, record an audit trail in `diario.md` for awards, make `XP_MISMATCH` verify exact reconciliation, and trigger `CRITICAL` severity on `QUEST_REWARD_PAID_TWICE`.  
*Independent Test Criteria*: `quests.py` has no divergent hardcoded XP values; `progress --award` appends `* **[XP] +{N} XP** ({motivo}) | Turno {T}` under `### Registro de Experiência` in `diario.md`; `review` flags `XP_MISMATCH` if total ficha XP differs from auditable sources; attempting duplicate quest payout emits `QUEST_REWARD_PAID_TWICE` critical issue.

- [X] T013 [P] [US3] Import `DEFAULT_QUEST_REWARDS` in `council/quests.py` and replace all literal hardcoded fallback XP values with canonical constants
- [X] T014 [P] [US3] Wire unlinked clock resolution in `lazy_turn.py cmd_commit` to grant `clock_resolved` (40 XP) from `rulesets/progression.py` when an active clock reaches `RESOLVED` without a linked quest
- [X] T015 [US3] Implement experience ledger recorder in `council/quests.py` / `lazy_turn.py progress --award` writing `* **[XP] +{N} XP** ({motivo}) | Turno {T}` under `### Registro de Experiência` in `diario.md`
- [X] T016 [US3] Refactor `XP_MISMATCH` in `council/reviewer.py` to sum all `XP Pago` from quests plus entries in `### Registro de Experiência`, emitting `HIGH` if ficha total differs from auditable sum
- [X] T017 [US3] Update `QUEST_REWARD_PAID_TWICE` in `council/reviewer.py` and `lazy_turn.py cmd_commit` to block repeated payments and emit a `CRITICAL` audit issue upon duplicate payout attempts
- [X] T018 [US3] Add unit tests in `tests/test_quest_progression.py` verifying SSOT reward lookups, ledger logging, exact `XP_MISMATCH` reconciliation, and `QUEST_REWARD_PAID_TWICE` critical linting

---

## Phase 6: User Story 4 - State Machine Completeness & Evidence Logging (Priority: P1)

*Goal*: Complete the quest state machine in CLI by implementing `--unblock` and `--abandon`, and persist textual evidence on completion.  
*Independent Test Criteria*: Running `lazy_turn.py quest --unblock "Q1"` transitions `BLOCKED` $\rightarrow$ `ACTIVE`; running `quest --abandon "Q1" --reason "..."` transitions to `ABANDONED`; running `quest --complete "Q1" --evidence "..."` appends `  * **Evidência:** ...` to `diario.md`.

- [X] T019 [P] [US4] Implement `--unblock` action in `council/quests.py` and `lazy_turn.py cmd_quest` transitioning quest status from `BLOCKED` to `ACTIVE`
- [X] T020 [P] [US4] Implement `--abandon` action in `council/quests.py` and `lazy_turn.py cmd_quest` transitioning quest status to `ABANDONED` and appending reason
- [X] T021 [US4] Persist `--evidence` parameter in `upsert_quest_in_diario` in `council/quests.py` when completing a quest, writing `  * **Evidência:** {evidence}` under the quest header
- [X] T022 [US4] Add unit tests in `tests/test_quest_progression.py` asserting `--unblock`, `--abandon`, and `--evidence` behaviors

---

## Phase 7: User Story 5 - Overrides, Mathematical Robustness, Scoped Blocks & Sandbox (Priority: P2)

*Goal*: Pass campaign overrides to XP curve calculations, tolerate out-of-turn level-up in `VITALS_DESYNC`, eliminate un-interpolated template placeholders, clean commit hints, and ensure strict single-write atomic file operations.  
*Independent Test Criteria*: Commit applies `base_step` from campaign overrides; `init-campaign` interpolates all quest template placeholders; prepare hint shows clean shell syntax; `upsert_quest_in_diario` performs strictly one file write per call; reviewer ignores false-positive vitals desync when level matches expansion.

- [X] T023 [P] [US5] Pass `base_step = get_base_step_from_overrides(get_campaign_overrides(campaign_id))` to `update_progression_in_ficha` in `lazy_turn.py cmd_commit`
- [X] T024 [P] [US5] Teach `VITALS_DESYNC` in `council/reviewer.py` to tolerate differences when protagonist level in `ficha.md` is greater than turn snapshot level and vitais delta matches exact level-up bonuses
- [X] T025 [P] [US5] Add mission placeholder replacements (`{{NOME_MISSAO_PRINCIPAL}}`, `{{CONTRATANTE_OU_FACCAO}}`, `{{PRIMEIRO_OBJETIVO_DA_MISSAO}}`, `{{SEGUNDO_OBJETIVO_DA_MISSAO}}`) in `council/helpers.py:init_campaign_from_templates`
- [X] T026 [P] [US5] Add `[Q1]` explicit tag to default quest in `templates/diario.template.md`
- [X] T027 [P] [US5] Clean commit hint formatting in `lazy_turn.py cmd_prepare` removing brackets and pipes (`--quest-progress Q1:1 --quest-complete Q1`)
- [X] T028 [US5] Refactor `upsert_quest_in_diario` in `council/quests.py` to eliminate intermediate disk writes, ensuring strictly one read at entry and one atomic write at exit
- [X] T029 [US5] Add unit and integration tests in `tests/test_quest_progression.py` and `tests/test_cli_contracts.py` covering overrides, template initialization, single-write integrity, and vitals tolerance

---

## Phase 8: Polish & Cross-Cutting Verification Gate

*Goal*: Execute full 8-step QA verification gate and prove 100% clean operations across all active campaigns.  
*Independent Test Criteria*: All 8 steps of `quickstart.md` pass cleanly; regression review on `dinastia_cinzas`, `imperio_valiria`, and `perpetuos_terra_incognita` reports zero new issues.

- [X] T030 Execute complete 8-step verification gate from `specs/008-fix-quest-progression/quickstart.md`
- [X] T031 Run regression test suite `python -m unittest discover tests` asserting 100% passing tests (36/36)
- [X] T032 Run `lazy_turn.py review` on all three active campaigns to ensure zero regressions
- [X] T033 Remove all temporary test campaigns and artifacts created during verification

---

## Phase 9: Final QA Remediations (P1-4, P1-7, P3-15, P3-16, P3-17)

*Goal*: Close all residual QA review findings so Feature 008 is 100% sealed without pending P1/P3 items.

- [X] T034 [P1-4] Connect `clock_resolved` (+40 XP) to `lazy_turn.py clock --resolve` and `lazy_turn.py commit --clock-resolve`, and `arc_milestone` (+80 XP) to `lazy_turn.py arc --milestone`, logging awards in `diario.md` ledger and documenting `XP_GRANT_TABLE`
- [X] T035 [P1-7] Persist duplicate quest payout alert directly into `diario.md` committed turn text and verify `council/reviewer.py` fires `QUEST_REWARD_PAID_TWICE` (CRITICAL)
- [X] T036 [P3-15] Eradicate `tempfile.mkdtemp` and `tempfile.TemporaryDirectory` completely, adopting workspace `.tmp/test_scratch/` with inherited permissions to run green under restricted sandboxes without elevation
- [X] T037 [P3-16] Add direct integration tests in `tests/test_cli_contracts.py` for `cmd_quest` and `cmd_progress`
- [X] T038 [P3-17] Synchronize architectural decisions in `DECISOES_ARQUITETURA.md` and spec documentation with accurate test counts (36 tests) and execution realities

---

## Dependencies & Completion Order

```text
Phase 1 (Setup/Sandbox) ──► Phase 2 (Foundational/Rewards SSOT)
                                     │
      ┌──────────────────────────────┴──────────────────────────────┐
      ▼                                                             ▼
Phase 3: US1 (Commit Order P0-1)                           Phase 4: US2 (Monotonic IDs P0-2)
      │                                                             │
      └──────────────────────────────┬──────────────────────────────┘
                                     ▼
                      Phase 5: US3 (Ledger & SSOT P1)
                                     │
                                     ▼
                      Phase 6: US4 (State Machine P1)
                                     │
                                     ▼
                      Phase 7: US5 (Robustness & Templates P2)
                                     │
                                     ▼
                      Phase 8: Polish & 8-Step Verification Gate
```

---

## Parallel Execution Opportunities

* **Parallel 1 (Phase 1 & 2)**: T002, T003, T004 can run concurrently.
* **Parallel 2 (Phase 5 & 6)**: T013, T014 (SSOT XP) and T019, T020 (State Machine flags) touch different functions and can be authored in parallel.
* **Parallel 3 (Phase 7)**: T023, T024, T025, T026, T027 touch independent files (`helpers.py`, `reviewer.py`, `templates/diario.template.md`, `lazy_turn.py prepare`) and can be implemented concurrently.
