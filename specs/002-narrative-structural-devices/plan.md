# Implementation Plan: Narrative Structural Devices & Scene Modifiers

**Feature**: `narrative-structural-devices`  
**Status**: Ready for Implementation  
**Created**: 2026-10-18  

---

## 1. Plan Overview & Objectives

This plan details the implementation of narrative structural devices in `lazy_turn.py`, equipping GMs and narrators with dedicated scene modifiers (`interlude`, `timeskip`, `dossier`, `flashback`, `prologue`, `epilogue`, `post_credits`) to overcome protagonist-centric stagnation and enable cinematic, multi-layered storytelling.

### Core Deliverables:
1. **`--scene-type` and `--actors` in `lazy_turn.py prepare`**:
   - Dynamic prompt adaptation for interludes, dossiers, timeskips, and flashbacks.
   - Protagonist presence exemption when generating cutscenes and dossiers.
2. **Multi-Unit Time Jump Engine in `advance_time_str`**:
   - Parses `+Nd` (days), `+Nw` (weeks), `+Nm` (months), `+Ny` (years), updating the canonical calendar in `diario.md`.
3. **Automated Vital Rest & Tagging in `cmd_commit`**:
   - Adds `--scene-type` to tag turns in `diario.md` (e.g. `Turno N [INTERLÚDIO]: ...`).
   - Auto-replenishes vitals on extended timeskips.
4. **Typographic Mandates in `MODE_PROSE_MANDATES`**:
   - Epistolary classified dossier layout for `dossier`.
   - Autonomous NPC cutscene direction for `interlude` and `parallel`.
   - Evocative montage prose for `timeskip`.
5. **Documentation Updates**:
   - Synchronize `SKILL.md` and `1_turn_discipline_and_prose.md`.

---

## 2. Technical Context & Constitution Gates

* **Zero External Dependencies**: Python Standard Library only (`re`, `datetime`, `pathlib`, `json`, `sys`, `argparse`).
* **Backward Compatibility**: Standard turns (`--scene-type standard` or omitted) remain 100% unchanged.
* **SSOT Integrity**: All outputs format cleanly in human-readable Markdown in `campaigns/<id>/diario.md`.

---

## 3. Work Breakdown Structure

### Phase 1: Temporal Jump Engine
- [ ] **Task 1.1**: Enhance `advance_time_str` in `lazy_turn.py` to support `+Nd`, `+Nw`, `+Nm`, `+Ny` intervals with date parsing.

### Phase 2: CLI Extensions in `prepare` & `commit`
- [ ] **Task 2.1**: Add `--scene-type` and `--actors` flags to `prepare` and `commit` in `main()`.
- [ ] **Task 2.2**: Update `cmd_prepare` to customize `council_pipeline` based on `scene_type` (waiving protagonist check for cutscenes/dossiers).
- [ ] **Task 2.3**: Update `cmd_commit` to handle `--scene-type` turn tagging and timeskip vital replenishment.

### Phase 3: Typographic & Direction Mandates
- [ ] **Task 3.1**: Add specialized prompt directives for `dossier` (epistolary layout), `interlude` (autonomous third-person NPC dynamics), and `timeskip` (montage prose).

### Phase 4: Rules Synchronization & Verification
- [ ] **Task 4.1**: Update `SKILL.md` to document the new scene types and usage guidelines.
- [ ] **Task 4.2**: Update `1_turn_discipline_and_prose.md`.
- [ ] **Task 4.3**: Execute validation scenarios from `quickstart.md`.
