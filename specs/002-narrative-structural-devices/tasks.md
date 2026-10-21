# Implementation Tasks: Narrative Structural Devices & Scene Modifiers

**Feature**: `narrative-structural-devices`  
**Spec**: [spec.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/002-narrative-structural-devices/spec.md)  
**Plan**: [plan.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/002-narrative-structural-devices/plan.md)  
**Status**: Ready for Execution  

---

## Phase 1: Setup & Environment

- [X] T001 Verify baseline and test environment for `lazy_turn.py` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 2: Foundational (Temporal Jump Engine)

- [X] T002 Enhance `advance_time_str` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` to parse and advance dates by multi-day (`+Nd`), multi-week (`+Nw`), multi-month (`+Nm`), and multi-year (`+Ny`) intervals

---

## Phase 3: User Story 1 - Interludes & Parallel Scenes (Priority: P1)

*Goal*: Enable temporary perspective cuts to off-screen antagonists and factions without requiring protagonist presence.  
*Test Criteria*: `lazy_turn.py prepare --scene-type interlude --actors "Kenjaku, Mahito"` generates a cutscene payload without requiring protagonist rolls or presence.

- [X] T003 [US1] Add `--scene-type` and `--actors` arguments to `lazy_turn.py prepare` and `commit` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T004 [US1] Update `cmd_prepare` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` to waive protagonist checks and disable player dice rolls when `scene_type in ("interlude", "parallel")`
- [X] T005 [US1] Add autonomous third-person NPC direction mandates for `interlude` and `parallel` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 4: User Story 2 - Timeskips & Montages (Priority: P1)

*Goal*: Advance the game calendar by days or months in a single command, automatically replenishing vitals and updating threat clocks.  
*Test Criteria*: `lazy_turn.py commit --scene-type timeskip --time "+60d"` advances the calendar 60 days, tags the turn, and restores vitals.

- [X] T006 [US2] Update `cmd_commit` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` to support `--scene-type timeskip` with automatic vital replenishment to full
- [X] T007 [US2] Add montage prose and pacing mandates for `timeskip` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 5: User Stories 3, 4 & 5 - Special Dossiers, Flashbacks & Arc Framing (Priority: P2)

*Goal*: Support epistolary classified dossiers, retrospective flashbacks, and prologue/epilogue/stinger framing.  
*Test Criteria*: `lazy_turn.py prepare --scene-type dossier` injects epistolary report formatting into the writer mandate.

- [X] T008 [P] [US3] Add epistolary document layout mandates (classification, threat assessment, bias) for `dossier` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T009 [P] [US4] Add temporal retrospective and emotional grounding directives for `flashback` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T010 [US5] Add saga boundary directives for `prologue`, `epilogue`, and `post_credits` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T011 [US1] Update `cmd_commit` to tag turn headers with scene type (e.g. `[INTERLÚDIO]`, `[SALTO TEMPORAL]`, `[DOSSIÊ]`) in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 6: Polish, Rules Synchronization & Verification

- [X] T012 [P] Update `C:/Users/Konor/.gemini/config/skills/rpg-narrative-engine/SKILL.md` to document the new scene types and CLI usage
- [X] T013 [P] Update `C:/Users/Konor/.gemini/config/skills/rpg-narrative-engine/references/1_turn_discipline_and_prose.md` with guidelines on scene modifiers
- [X] T014 Execute all validation scenarios from `c:/Users/Konor/Documents/RPGPRO/specs/002-narrative-structural-devices/quickstart.md`

---

## Dependencies & Execution Order

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Temporal Jump Engine)
    │
    ▼
Phase 3 (US1: Interludes CLI & Direction)
    │
    ▼
Phase 4 (US2: Timeskips & Montages)
    │
    ▼
Phase 5 (US3, US4, US5: Dossiers, Flashbacks, Framing)
    │
    ▼
Phase 6 (Polish & Documentation)
```

### Parallel Opportunities:
- **T008** (Dossier layout) and **T009** (Flashback directives) can be implemented concurrently.
- **T012** and **T013** (documentation updates) can be executed concurrently with Phase 5 validation.
