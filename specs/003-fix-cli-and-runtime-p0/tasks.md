# Implementation Tasks: P0 Runtime & CLI Fixes

**Feature**: `fix-cli-and-runtime-p0`  
**Spec**: [spec.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/003-fix-cli-and-runtime-p0/spec.md)  
**Plan**: [plan.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/003-fix-cli-and-runtime-p0/plan.md)  
**Status**: Completed  

---

## Phase 1: Setup & Pre-Flight Checks

- [X] T001 Verify baseline CLI and test environment for `lazy_turn.py` against quickstart criteria in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`

---

## Phase 2: Foundational Tasks (Shared Engine Mandates)

- [X] T002 [P] Implement dedicated mandate dictionary for `prologue` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T003 [P] Implement dedicated mandate dictionary for `epilogue` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T004 [P] Implement dedicated mandate dictionary for `post_credits` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py`
- [X] T005 [P] Mirror scene type mandates for `prologue`, `epilogue`, and `post_credits` in `c:/Users/Konor/Documents/RPGPRO/council/writer.py`

---

## Phase 3: User Story 1 - Showrunner CLI Documentation Alignment (Priority: P1)

*Goal*: Eliminate argparse runtime aborts by updating all documented CLI commands in `rpg-showrunner` to match `lazy_turn.py`.  
*Independent Test Criteria*: All CLI commands copied verbatim from `rpg-showrunner/SKILL.md` run successfully in PowerShell against `lazy_turn.py` without argument errors.

- [X] T006 [P] [US1] Fix `plan` CLI documentation: replace `--add-scene` with `--add`, `--type` with `--scene-type`, remove `--trigger`, and change `--complete-scene <ID>` to `--complete <índice>` in `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-showrunner/SKILL.md`
- [X] T007 [P] [US1] Fix `clock` CLI documentation: change `--advance "<Nome>:1"` to `--advance <Nome> --steps 1` in `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-showrunner/SKILL.md`
- [X] T008 [P] [US1] Fix `arc` CLI documentation: document `--resolve-clocks` as a boolean flag rather than taking string values in `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-showrunner/SKILL.md`
- [X] T009 [P] [US1] Update Section 3 scene taxonomy in `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-showrunner/SKILL.md` to list and describe all 10 canonical scene types
- [X] T010 [US1] Synchronize global skill copy in `C:/Users/Konor/.gemini/config/skills/rpg-showrunner/SKILL.md` with workspace changes

---

## Phase 4: User Story 2 - Arc Framing Scenes Coverage (Priority: P1)

*Goal*: Provide distinct literary direction for `prologue`, `epilogue`, and `post_credits` in `lazy_turn.py prepare`.  
*Independent Test Criteria*: `python lazy_turn.py prepare --campaign imperio_valiria --action "Abertura" --scene-type prologue` returns `"scene_type": "prologue"` with dedicated mythic framing instructions in `step_3_writer_mandate`.

- [X] T011 [US2] Update `cmd_prepare` in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` to ensure `mandates_by_type.get(scene_type)` resolves without fallback for all 10 canonical scene types
- [X] T012 [US2] Verify `commit_hint` generation in `c:/Users/Konor/Documents/RPGPRO/lazy_turn.py` correctly includes `--scene-type` for prologue, epilogue, and post_credits

---

## Phase 5: User Story 3 - Clean Turn-by-Turn Context (Priority: P1)

*Goal*: Prevent the Showrunner skill from auto-activating during routine game turns to eliminate context bloat and authority conflict.  
*Independent Test Criteria*: Searching for `"Ativa-se automaticamente"` in `.agents/skills/rpg-showrunner/SKILL.md` returns zero hits.

- [X] T013 [US3] Modify YAML frontmatter description and introductory text to state that `rpg-showrunner` activates on demand for macro-planning, arc transitions, and clock audits in `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-showrunner/SKILL.md`
- [X] T014 [US3] Synchronize global skill trigger in `C:/Users/Konor/.gemini/config/skills/rpg-showrunner/SKILL.md`

---

## Phase 6: User Story 4 - Cross-Environment Portability (Priority: P2)

*Goal*: Ensure all links inside `rpg-narrative-engine/SKILL.md` are relative and portable across platforms and machines.  
*Independent Test Criteria*: Searching for `"file:///C:/Users/Konor"` inside `.agents/skills` returns zero occurrences.

- [X] T015 [US4] Replace all absolute URIs (`file:///C:/Users/Konor/...`) with relative Markdown links (`references/...`) in `c:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-narrative-engine/SKILL.md`
- [X] T016 [US4] Synchronize relative links in `C:/Users/Konor/.gemini/config/skills/rpg-narrative-engine/SKILL.md`

---

## Phase 7: Polish & Comprehensive Verification

- [X] T017 Execute validation test suite from `c:/Users/Konor/Documents/RPGPRO/specs/003-fix-cli-and-runtime-p0/quickstart.md` covering `plan`, `clock`, `arc`, and scene mandates
- [X] T018 Run automated grep assertions verifying zero broken paths and zero auto-activation triggers across all skill folders
