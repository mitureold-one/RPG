# Implementation Tasks: Narrative State & Progression Engine

**Feature**: `narrative-state-progression`  
**Spec**: [spec.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/001-narrative-state-progression/spec.md)  
**Plan**: [plan.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/001-narrative-state-progression/plan.md)  
**Status**: Completed  

---

## Phase 1: Setup & Environment

- [X] T001 Verify existing SSOT files and ensure regression baseline for `lazy_turn.py` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 2: Foundational (SSOT Parsing & Regex Engines)

- [X] T002 Implement regex parsers `parse_clocks_from_diario(diario_path)` and `parse_arc_from_diario(diario_path)` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T003 Implement `upsert_clock_in_diario(diario_path, name, current, max_steps, trigger, status)` for atomic updates to `diario.md` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 3: User Story 2 - Pacing Pressure via Ticking Clocks (Priority: P1)

*Goal*: Enable players and GMs to define, track, and deterministically advance segmented threat clocks and deadlines via the CLI.  
*Test Criteria*: Running `lazy_turn.py clock --campaign <id> --add/advance/list` correctly creates, advances, and reports clocks in `diario.md`.

- [X] T004 [US2] Implement CLI handler `cmd_clock(campaign_id, list_clocks, add_name, max_steps, trigger, advance_name, advance_steps, resolve_name, as_json)` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T005 [US2] Register the `clock` subcommand in `main()` argparse with all flags in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T006 [US2] Validate Scenario A and B from `quickstart.md` using `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 4: User Story 1 & 4 - Tri-Scale Progression & 5-Step Narrative Cycle (Priority: P1)

*Goal*: Inject World Scale (clocks/deadlines) and Arc Scale (dramatic question/stage) into `lazy_turn.py prepare` and enforce the 5-step narrative cycle in prose mandates.  
*Test Criteria*: `lazy_turn.py prepare` returns `world_scale` and `arc_scale` in JSON, and prose rules mandate a tangible state shift.

- [X] T007 [P] [US4] Update `cmd_prepare` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` to extract and populate `world_scale` (active and breached clocks) and `arc_scale` inside `council_pipeline["1_architect_canon"]`
- [X] T008 [P] [US1] Update `MODE_PROSE_MANDATES["gm"]` and `["narrator"]` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` to mandate the 5-Step Cycle (Situação Ativa $\to$ Resistência $\to$ Escolha $\to$ Impacto $\to$ Novo Estado) and delivery of an explicit state shift
- [X] T009 [US1] Update `council_pipeline["4_writer_prose"]` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` to instruct Batidas 3 & 4 to produce an irreversible change in the scene/world

---

## Phase 5: User Story 3 - Off-Screen World Agendas & Anti-Inertia Auditor (Priority: P2)

*Goal*: Automate clock advancement through `commit`, record state shifts, and detect stagnant narratives or breached deadlines.  
*Test Criteria*: `commit` records `Mudança de Estado` and ticks clocks; `review` flags `NARRATIVE_STAGNATION` and `CLOCK_BREACHED`.

- [X] T010 [US3] Extend `cmd_commit` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` to accept `--state-shift` and `--clock-advance`, persisting them into the turn block in `diario.md`
- [X] T011 [US3] Implement `CLOCK_BREACHED` audit check in `cmd_review` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` when any clock reaches `current >= max`
- [X] T012 [US3] Implement `NARRATIVE_STAGNATION` audit check in `cmd_review` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` scanning the last 2-3 turns for empty/identical state shifts
- [X] T013 [US3] Connect `CLOCK_BREACHED` and `NARRATIVE_STAGNATION` alerts to trigger `is_critical_turn = True` in `cmd_prepare` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 6: Polish, Rules Synchronization & Verification

- [X] T014 [P] Update `C:/Users/Konor/.gemini/config/skills/rpg-narrative-engine/SKILL.md` to document the Tri-Scale Engine, the 5-Step Cycle, and Narrative Clocks
- [X] T015 [P] Update `C:/Users/Konor/.gemini/config/skills/rpg-narrative-engine/references/1_turn_discipline_and_prose.md` with guidelines on state shifts and anti-stagnation
- [X] T016 Execute all validation scenarios from `c:/Users/Konor/Documents/RPGPRO/specs/001-narrative-state-progression/quickstart.md` and verify zero regressions

---

## Dependencies & Execution Order

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational: Regex & Parsers)
    │
    ▼
Phase 3 (US2: Ticking Clocks CLI)
    │
    ▼
Phase 4 (US1 & US4: Tri-Scale & Prose Mandates)
    │
    ▼
Phase 5 (US3: Commit Flags & Anti-Inertia Review)
    │
    ▼
Phase 6 (Polish & Documentation)
```
