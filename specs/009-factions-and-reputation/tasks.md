# Implementation Tasks: 009 — Sistema de Facções, Reputação Numérica e Turno de Mundo Off-Screen

**Feature**: `factions-and-reputation`  
**Spec**: [spec.md](spec.md)  
**Plan**: [plan.md](plan.md)  
**Data Model**: [data-model.md](data-model.md)  
**Contracts**: [contracts/cli_contracts.md](contracts/cli_contracts.md)  
**Quickstart**: [quickstart.md](quickstart.md)  
**Status**: Ready for Implementation  

---

## Phase 1: Setup & Baseline Isolation

- [X] T001 Verify baseline test suite passes completely (36/36 OK) via `python -m unittest discover tests`
- [X] T002 [P] Configure test harness helper for faction tests in `tests/test_factions_reputation.py` using workspace directory `.tmp/test_scratch/` with inherited permissions (zero `tempfile.mkdtemp`)

---

## Phase 2: Foundational Tasks

- [X] T003 [P] Create `council/factions.py` defining domain data structures `Faction`, `FactionReputation`, and `FactionLedgerEntry` with type annotations
- [X] T004 [P] Implement reputation tier mapping constants (`REPUTATION_TIERS`, `TIER_DESCRIPTIONS`, `SOCIAL_DC_MODIFIERS`) and clamping helper `clamp_reputation(score: int) -> int` in `council/factions.py`
- [X] T005 [P] Implement legacy label converter in `council/factions.py` converting qualitative ratings (e.g. `Favorável / Respeitado` -> `+1`, `Sob Suspeita` -> `-1`, `Inimigo` -> `-2`) to numeric scores

---

## Phase 3: User Story 1 - Faction Management & CLI (Priority: P1)

*Goal*: Parse and register factions in `mundo.md` under `## 4. Facções, Forças Ativas & Alianças` with Power (1..5), Scale, and linked clocks, exposing via CLI `faction --list` and `faction --add`.  
*Independent Test Criteria*: Running `lazy_turn.py faction --campaign <id> --add "Ordem X" --power 4 --scale regional` adds the structured markdown line in `mundo.md`, and `faction --list --json` outputs valid JSON containing all faction fields.

- [X] T006 [P] [US1] Implement `parse_factions_from_mundo(mundo_path: Path) -> list[dict]` in `council/factions.py` extracting `tag`, `name`, `power`, `scale`, `clock`, `rivals`, and description
- [X] T007 [P] [US1] Implement `upsert_faction_in_mundo(mundo_path: Path, ...)` in `council/factions.py` inserting or updating faction blocks with single atomic disk write
- [X] T008 [US1] Add `faction` subparser in `lazy_turn.py:build_cli()` supporting `--list`, `--json`, `--add`, `--power`, `--scale`, `--clock`, `--desc`
- [X] T009 [US1] Implement `cmd_faction` handler in `lazy_turn.py` connecting `--list` and `--add` to `council/factions.py`
- [X] T010 [US1] Add unit tests in `tests/test_factions_reputation.py` validating `mundo.md` parsing, tag generation, atomic insertion, and legacy tolerance

---

## Phase 4: User Story 2 - Numeric Reputation, Favors & Debts in Ficha (Priority: P1)

*Goal*: Store and manipulate protagonist reputation (-3 to +3), favors ($\ge 0$), and debts ($\ge 0$) under `### Vínculos, Laços & Matriz Relacional` in `ficha.md`, recording audit entries in `diario.md`.  
*Independent Test Criteria*: Running `lazy_turn.py faction --campaign <id> --rep "Ordem X:+2"` updates `ficha.md` to `+2 (Aliado)` and logs an entry with turn number and reason under `### Registro de Reputação & Facções` in `diario.md`.

- [X] T011 [P] [US2] Implement `parse_reputation_from_ficha(ficha_path: Path) -> dict[str, dict]` in `council/factions.py` parsing structured bullets and legacy uniline format
- [X] T012 [P] [US2] Implement `update_reputation_in_ficha(ficha_path: Path, faction_name: str, score_delta: int, favors_delta: int, debts_delta: int) -> dict` in `council/factions.py` with strict clamping `[-3, +3]` and non-negative favors/debts
- [X] T013 [P] [US2] Implement `parse_faction_ledger_from_diario(diario_path: Path) -> list[dict]` and `append_faction_ledger_entry(diario_path: Path, ...)` in `council/factions.py`
- [X] T014 [US2] Wire CLI flags `--rep`, `--reason`, `--favor`, `--debt` in `lazy_turn.py cmd_faction`
- [X] T015 [US2] Add unit tests in `tests/test_factions_reputation.py` asserting reputation clamping, favor/debt increments, and ledger persistence in `diario.md`

---

## Phase 5: User Story 3 - Quest Contract Automation in Commit (Priority: P1)

*Goal*: Automatically reward +1 reputation and +1 favor upon completing a quest with a contractor, or penalize -1 reputation and +1 debt upon quest failure during `lazy_turn.py commit`.  
*Independent Test Criteria*: Executing `lazy_turn.py commit --campaign <id> --summary "..." --quest-complete "Q1"` on a quest with `Contratante: Facção A` increases reputation by +1, increments favors by +1, and records an auditable ledger line in `diario.md`.

- [X] T016 [US3] Add `--faction-rep`, `--faction-favor`, and `--faction-debt` flags to `commit` subparser in `lazy_turn.py:build_cli()`
- [X] T017 [US3] In `lazy_turn.py cmd_commit`: process manual faction mutations passed via `--faction-rep`, `--faction-favor`, and `--faction-debt`
- [X] T018 [US3] In `lazy_turn.py cmd_commit`: hook into `quest_complete` processing to detect `Contratante:` in completed quest, auto-applying `+1` reputation and `+1` favor with ledger entry
- [X] T019 [US3] In `lazy_turn.py cmd_commit`: hook into `quest_fail` processing to detect `Contratante:` in failed quest, auto-applying `-1` reputation and `+1` debt with ledger entry
- [X] T020 [US3] Add integration tests in `tests/test_factions_reputation.py` validating automated contract rewards and failure penalties on `cmd_commit`

---

## Phase 6: User Story 4 - Faction Context in Prepare (Priority: P2)

*Goal*: Inject `step_1_faction_context` into `lazy_turn.py prepare` JSON payload with reputation scores, social DC modifiers, and NPC attitude directives.  
*Independent Test Criteria*: Executing `lazy_turn.py prepare --campaign <id> --action "Negociar"` with an NPC belonging to a hostile faction returns `social_dc_mod: 3`, `suggested_variant: "disadvantage"`, and explicit writer directives in `step_1_faction_context`.

- [X] T021 [P] [US4] Implement `resolve_scene_factions(campaign_info: dict, scene_npcs: list[str], location: str) -> list[dict]` in `council/factions.py`
- [X] T022 [US4] Update `lazy_turn.py cmd_prepare` to inject `step_1_faction_context` into the returned JSON payload
- [X] T023 [US4] Add snapshot and assertion tests in `tests/test_factions_reputation.py` verifying `step_1_faction_context` structure, DC modifiers, and writer directives
- [X] T024 [P] [US5] Implement `simulate_faction_tick(campaign_info: dict) -> dict` in `council/factions.py` advancing active clocks for factions based on Power (1..5)
- [X] T025 [US5] Wire `lazy_turn.py cmd_faction` with `--tick` to execute `simulate_faction_tick` and return formatted summary / JSON
- [X] T026 [US5] Add integration tests in `tests/test_factions_reputation.py` confirming tick advancement, power scaling, and breached clock notifications

---

## Phase 8: User Story 6 - Deterministic Reviewer Lints (Priority: P1)

*Goal*: Implement deterministic integrity checks in `council/reviewer.py` detecting unknown factions, orphaned NPCs, attitude desyncs, and reputation ledger mismatches.  
*Independent Test Criteria*: `lazy_turn.py review` cleanly reports CLEAN when consistent, and flags `FACTION_UNKNOWN`, `FACTION_ORPHANED_NPC`, `FACTION_ATTITUDE_DESYNC`, and `FACTION_REP_MISMATCH` with exact severities when provoked.

- [X] T027 [P] [US6] Implement `check_factions_integrity(campaign_id, info)` in `council/reviewer.py` with lints:
  - `FACTION_UNKNOWN` (`HIGH`): Reputation on ficha with no declaration in `mundo.md`
  - `FACTION_ORPHANED_NPC` (`MEDIUM`): NPC in `npcs.md` affiliated with non-existent faction
  - `FACTION_ATTITUDE_DESYNC` (`HIGH`): NPC friendly to hero with -2 (Hostile) or -3 (Hunted) reputation without psychological exception
  - `FACTION_REP_MISMATCH` (`HIGH`): Ficha reputation score differs from sum of ledger mutations in `diario.md`
- [X] T028 [US6] Add unit tests in `tests/test_factions_reputation.py` provoking each lint condition and verifying exact type and severity emissions

---

## Phase 9: Polish & Cross-Cutting Verification Gate

*Goal*: Execute full 8-step verification gate and guarantee 100% test passing across the complete RPGPRO test suite.  
*Independent Test Criteria*: All 8 steps of `quickstart.md` succeed without manual fixes; `python -m unittest discover tests` runs 100% green; regression review on `dinastia_cinzas`, `imperio_valiria`, and `perpetuos_terra_incognita` reports zero new issues.

- [X] T029 Add CLI interface contract tests in `tests/test_cli_contracts.py` exercising `cmd_faction` (`--list`, `--add`, `--rep`, `--favor`, `--debt`, `--tick`)
- [X] T030 Execute the 8-step verification gate from `specs/009-factions-and-reputation/quickstart.md` on temporary campaign `_qa_factions`
- [X] T031 Run regression test suite `python -m unittest discover tests` asserting 100% passing tests without permission errors
- [X] T032 Run `lazy_turn.py review` on all three canonical campaigns ensuring zero regressions
- [X] T033 Clean up all temporary files and verify workspace git status is clean
