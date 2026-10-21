# Implementation Plan: P0 Runtime & CLI Fixes

**Feature**: `fix-cli-and-runtime-p0`  
**Status**: Ready for Implementation  
**Created**: 2026-10-21  

---

## 1. Plan Overview & Objectives

This implementation plan delivers the critical **P0** remediations identified during the architecture review. Its objective is to eliminate runtime tool failures, provide complete literary direction for all valid scene structures, establish unambiguous skill triggers, and remove environment-specific absolute paths.

### Core Deliverables:
1. **Showrunner CLI Synchronization**:
   - Align all code snippets and documentation in `.agents/skills/rpg-showrunner/SKILL.md` with `lazy_turn.py` parameter signatures (`plan`, `clock`, `arc`).
2. **Literary Mandates for Orphan Scene Types**:
   - Add specialized structural mandates for `prologue`, `epilogue`, and `post_credits` in `lazy_turn.py` (and `council/writer.py`).
   - Eliminate fallback to `standard` for all 10 canonical scene types.
3. **Showrunner Skill De-activation on Routine Turns**:
   - Reframe `rpg-showrunner/SKILL.md` to trigger on demand for macro-planning, arc turns, and clock arbitration, ending concurrent activation with the narrative engine.
4. **Relativization of Skill References**:
   - Clean all references in `rpg-narrative-engine/SKILL.md` to use relative links instead of machine-specific `file:///C:/Users/Konor/...` URIs.

---

## 2. Technical Context & Constitution Gates

* **Zero External Dependencies**: Standard library Python (`argparse`, `json`, `pathlib`) and standard Markdown.
* **Non-Destructive Execution**: No schema changes to existing campaign files (`diario.md`, `ficha.md`, etc.).
* **Zero CLI Breaking Changes**: The real CLI signature in `lazy_turn.py` remains the stable source of truth.

---

## 3. Work Breakdown Structure

### Phase 1: CLI Documentation Alignment (`rpg-showrunner/SKILL.md`)
- [ ] **Task 1.1**: Update `plan` documentation: replace `--add-scene` with `--add`, `--type` with `--scene-type`, remove `--trigger`, and update `--complete-scene <ID>` to `--complete <índice>`.
- [ ] **Task 1.2**: Update `clock` documentation: replace `--advance "<Nome>:1"` with `--advance <Nome> --steps 1`.
- [ ] **Task 1.3**: Update `arc` documentation: document `--resolve-clocks` as a boolean flag.
- [ ] **Task 1.4**: Update scene types taxonomy in Section 3 to state and describe all 10 canonical types.

### Phase 2: Engine Mandates Implementation (`lazy_turn.py` & `council/writer.py`)
- [ ] **Task 2.1**: Implement dedicated mandate dictionary for `prologue` in `lazy_turn.py`.
- [ ] **Task 2.2**: Implement dedicated mandate dictionary for `epilogue` in `lazy_turn.py`.
- [ ] **Task 2.3**: Implement dedicated mandate dictionary for `post_credits` in `lazy_turn.py`.
- [ ] **Task 2.4**: Ensure `council/writer.py` reflects matching editorial guidelines if referenced directly.

### Phase 3: Skill Trigger & Path Relativization
- [ ] **Task 3.1**: Update `.agents/skills/rpg-showrunner/SKILL.md` frontmatter and intro: remove automatic activation on every turn; set trigger to on-demand macro-planning.
- [ ] **Task 3.2**: Update `.agents/skills/rpg-narrative-engine/SKILL.md`: replace absolute paths `file:///C:/Users/Konor/Documents/RPGPRO/...` with relative paths (`references/...`).

### Phase 4: Verification & Regression Testing
- [ ] **Task 4.1**: Execute quickstart scenarios for `plan`, `clock`, and `arc`.
- [ ] **Task 4.2**: Verify JSON payload for `prepare` with `--scene-type prologue`, `epilogue`, and `post_credits`.
- [ ] **Task 4.3**: Run path and text scans to confirm zero hardcoded absolute paths and zero auto-activation triggers.

---

## 4. Acceptance Criteria Checklist

- [ ] All CLI examples in `rpg-showrunner/SKILL.md` match `lazy_turn.py` options.
- [ ] All 10 scene types return distinct, non-fallback mandates in `lazy_turn.py prepare`.
- [ ] `rpg-showrunner` is configured for on-demand invocation only.
- [ ] No `file:///C:/Users/Konor` URIs exist in skill files.
