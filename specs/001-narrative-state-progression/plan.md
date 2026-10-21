# Implementation Plan: Narrative State & Progression Engine

**Feature**: `narrative-state-progression`  
**Status**: Ready for Implementation  
**Created**: 2026-10-18  

---

## 1. Plan Overview & Objectives

This plan details the technical implementation required to transition the RPG Narrative Engine from a scene-only, prose-aesthetic loop into an active **Tri-Scale Narrative Engine** with deterministic state progression, ticking clocks, and anti-inertia gates.

### Core Deliverables:
1. **Clock Subsystem in `lazy_turn.py`**: Parser and CLI subcommand (`lazy_turn.py clock`) to manage, advance, and resolve segmented threat clocks in `diario.md`.
2. **Tri-Scale Context in `cmd_prepare`**: Injects `world_scale` (clocks/deadlines) and `arc_scale` (active conflict/question) into the prompt returned to the LLM.
3. **State-Progression Turn Cycle in `MODE_PROSE_MANDATES`**: Formalizes the 5-step cycle in the prompt mandates (Situação Ativa $\to$ Resistência $\to$ Escolha $\to$ Impacto $\to$ Novo Estado) and requires Batidas 3 & 4 to deliver an irreversible delta.
4. **Enhanced `cmd_commit`**: Adds `--state-shift` and `--clock-advance` flags, persisting changes to `diario.md`.
5. **Anti-Inertia Auditor in `cmd_review`**: Algorithmic detector for `NARRATIVE_STAGNATION` (unresolved state across consecutive turns) and `CLOCK_BREACHED`.
6. **Documentation & Rules Synchronization**: Updates to `SKILL.md` and `1_turn_discipline_and_prose.md`.

---

## 2. Technical Context & Constitution Gates

* **Zero External Dependencies**: Python Standard Library only (`re`, `pathlib`, `json`, `sys`, `argparse`).
* **SSOT Integrity**: All state persists in human-readable Markdown (`campaigns/<id>/diario.md`).
* **Campaign-Agnostic**: Logic contains no hardcoded character or franchise names.
* **Backward Compatibility**: Campaigns without clocks or arc definitions will continue to function seamlessly with sensible fallbacks.

---

## 3. Work Breakdown Structure (Phases & Tasks)

### Phase 1: SSOT Parsing & Clock Management
- [ ] **Task 1.1**: Implement `parse_clocks_from_diario(diario_path)` in `lazy_turn.py` to extract `[Nome]: X/Y (Gatilho: ...)` and arc definitions.
- [ ] **Task 1.2**: Implement `upsert_clock_in_diario(diario_path, name, current, max_steps, trigger, resolve)` to edit or insert clocks atomically.
- [ ] **Task 1.3**: Implement CLI subcommand `cmd_clock` with `--list`, `--add`, `--advance`, `--resolve` options.

### Phase 2: Tri-Scale Integration in `cmd_prepare`
- [ ] **Task 2.1**: Update `cmd_prepare` to parse active clocks and arc info, populating `council_pipeline["1_architect_canon"]["world_scale"]` and `["arc_scale"]`.
- [ ] **Task 2.2**: Integrate `CLOCK_BREACHED` and `NARRATIVE_STAGNATION` into the critical turn calculation (`is_critical_turn = True`).
- [ ] **Task 2.3**: Update `MODE_PROSE_MANDATES` for GM and Narrador to enforce the 5-step cycle and state-shift delivery.

### Phase 3: Progression Commit & Anti-Inertia Review
- [ ] **Task 3.1**: Update `cmd_commit` to accept `--state-shift` and `--clock-advance`, writing them into the turn block in `diario.md`.
- [ ] **Task 3.2**: Update `cmd_review` to scan the last 3 turns in `diario.md` for stagnant state shifts or unaddressed breached clocks.

### Phase 4: Rules & Engine Documentation
- [ ] **Task 4.1**: Update `SKILL.md` with guidelines on the Tri-Scale Engine and Narrative Clocks.
- [ ] **Task 4.2**: Update `1_turn_discipline_and_prose.md` with the 5-Step Narrative Cycle.

---

## 4. Verification & Testing

* **Unit/Integration Scenarios**: Execute all scenarios defined in [`quickstart.md`](file:///c:/Users/Konor/Documents/RPGPRO/specs/001-narrative-state-progression/quickstart.md).
* **Regression Testing**: Verify existing commands (`lazy_turn.py prepare --campaign jjk_sakigake`, `lazy_turn.py review --campaign jjk_sakigake`) remain 100% operational without errors.
