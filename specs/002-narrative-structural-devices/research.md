# Research & Technical Decisions: Narrative Structural Devices & Scene Modifiers

**Feature**: `narrative-structural-devices`  
**Phase**: Phase 0 (Research & Feasibility)  
**Status**: Completed  
**Date**: 2026-10-18  

---

## 1. Technical Context & Requirements

The goal is to provide official, structured support for specialized narrative formats (Interludes, Parallel Scenes, Timeskips, In-Universe Dossiers, Flashbacks, and Arc Boundary Framing) without:
1. Breaking existing standard turn mechanics (dice arbitration, vital deduction, SSOT integrity).
2. Introducing external dependencies or proprietary engines.
3. Forcing artificial encounters or leaking out-of-character (OOC) knowledge.

### Key Unknowns Investigated:
1. **Scene Type Parametrization**: How should scene modifiers be declared in `lazy_turn.py prepare` and `commit`?
2. **Actor & Presence Overrides**: How can cutscenes and interludes operate when the protagonist is physically absent, while preserving canonical headers?
3. **Timeskip Automation**: How should batch time jumps calculate calendar advancement, vital replenishment, and faction clock progression?
4. **Epistolary Dossier Formatting**: What typographic standards best guide the LLM Writer to deliver authentic classified reports or archival logs?

---

## 2. Research Findings & Decisions

### Decision 1: CLI Parametrization via `--scene-type`
* **Decision**: Add `--scene-type` to `lazy_turn.py prepare` with choices:
  `["standard", "interlude", "parallel", "timeskip", "dossier", "flashback", "prologue", "epilogue", "post_credits"]` (default: `"standard"`), accompanied by `--actors "<Lista de NPCs>"` to define local cutscene attendees.
* **Rationale**:
  - Fully backward compatible: omitting `--scene-type` preserves 100% of standard protagonist gameplay.
  - Allows the LLM prompt in `prepare` to inject dedicated specialist mandates for each narrative device.

---

### Decision 2: Protagonist Presence Exemption for Cutscenes
* **Decision**: When `scene_type in ("interlude", "parallel", "dossier")`:
  - `lazy_turn.py` does not require the protagonist's name in `Presentes`.
  - Mechanical rolls (`roll_3_gates`) are automatically disabled (`needs_roll = False`), as player skills are not being tested.
  - The `3_narrator_direction` instructs the model to stage an autonomous dialogue or scene driven solely by the Vontades and Fraquezas of the NPCs present.
* **Rationale**:
  - Completely solves the "Protagonist-Farol" dilemma without breaking audit rules.
  - `cmd_review` recognizes `scene_type` in the diário log and does not flag missing protagonist vitals.

---

### Decision 3: Batch Timeskip Engine (`--scene-type timeskip`)
* **Decision**: Expand `advance_time_str` in `lazy_turn.py` to parse multi-day and multi-month increments (e.g. `+7d`, `+14d`, `+1m`, `+2m`, `+1y`) in addition to minutes/hours (`+30m`, `+2h`).
  - During a timeskip commit, protagonist vitals automatically restore to maximum (full rest) unless specified otherwise.
  - Active narrative clocks can be batch-advanced via `--clock-advance "Relogio:N"`.
* **Rationale**:
  - Players can leap forward through downtime or journeys cleanly in one atomic command.

---

### Decision 4: In-Universe Dossier Typographic Framework
* **Decision**: In `MODE_PROSE_MANDATES` for `dossier`, inject strict ASCII/Markdown epistolary templates:
  - Header with issuing faction, security clearance, classification level, and subject.
  - Assessment sections (Threat Rating, Known Abilities, Strategic Directives).
  - Subjective bias warning: The document must reflect the issuing faction's limited intelligence and worldview.

---

## 3. Constitution & Guardrail Check

| Principle | Status | Evaluation |
| :--- | :--- | :--- |
| **YAGNI / Minimal Diff** | PASS | Adds a single clean parameter `--scene-type` and targeted prompt templates. |
| **Standard Library Only** | PASS | Uses standard Python `re`, `datetime`, and string formatters. |
| **SSOT Markdown Integrity** | PASS | All interlude summaries and timeskips persist directly in `diario.md`. |
| **Anti-Puppeteering** | PASS | Cutscenes feature NPCs only; timeskips summarize character growth established by the player. |
