# Implementation Plan: P2 Separação de Sistema e Motor

**Feature**: `separate-system-engine-p2`  
**Status**: Ready for Implementation  
**Created**: 2026-10-21  
**Target Backlog Phase**: P2 (Engine & Ruleset Separation, Schema Enforcement & CLI Sanitization)

---

## 1. Plan Overview & Objectives

This implementation plan delivers the **P2** decoupling milestones from `DECISOES_ARQUITETURA.md` and the user specification:
1. **Extraction of Ruleset Layer (`rulesets/d20_3gates.py`)**: Extract dice mechanics, advantage/disadvantage handling, modifiers, and contest resolution from `council/gm.py` into a pluggable ruleset module.
2. **Campaign System Declaration**: Add `system: d20_3gates` to campaign mechanics manifests and provide a ruleset loader in the engine.
3. **Mandatory `schema_version` & Loud Validation in `find_campaign`**: Guarantee that all active campaigns and templates declare `schema_version: 1` in `diario.md`, and enhance `find_campaign` to fail loudly when schema versioning is missing or corrupted.
4. **CLI String Sanitization**: Remove all setting-specific and campaign-specific examples from `lazy_turn.py` help strings.
5. **Contract Test Suite Expansion**: Expand `tests/test_cli_contracts.py` to verify schema validation enforcement, ruleset extraction, and zero setting leaks in help strings.

---

## 2. Technical Context & Constitution Gates

* **Standard Library Only**: No external packages required (`pathlib`, `re`, `random`, `unittest`, `argparse`).
* **Non-Destructive State Transition**: Existing campaign data in `dinastia_cinzas`, `imperio_valiria`, and `perpetuos_terra_incognita` is upgraded cleanly without altering story history, clocks, or vitals.
* **Fail-Fast Safety**: Schema verification prevents invalid campaigns from proceeding to the turn execution loop.

---

## 3. Work Breakdown Structure

### Phase 1: Ruleset Extraction (`rulesets/d20_3gates.py`)
- [ ] **Task 1.1**: Create `rulesets/` package directory with `rulesets/__init__.py`.
- [ ] **Task 1.2**: Extract `roll_3_gates`, `extract_npc_contest_modifier`, `roll_contest`, and `DC_LADDER` into `rulesets/d20_3gates.py`.
- [ ] **Task 1.3**: Update `council/gm.py` to import and re-export the extracted functions from `rulesets.d20_3gates` to maintain backwards compatibility for existing callers.
- [ ] **Task 1.4**: Implement `load_ruleset(system_name)` in `council/helpers.py` (or `rulesets/__init__.py`) to support dynamic dispatch.

### Phase 2: Campaign System Declaration (`system:` in Manifests)
- [ ] **Task 2.1**: Update `templates/regras.template.md` to declare `system: d20_3gates` in `yaml:mechanics`.
- [ ] **Task 2.2**: Update active campaigns (`campaigns/dinastia_cinzas/regras.md`, `campaigns/imperio_valiria/regras.md`, `campaigns/perpetuos_terra_incognita/regras.md`) to include `system: d20_3gates`.
- [ ] **Task 2.3**: Implement helper function `get_campaign_system(campaign_id)` in `council/helpers.py`.
- [ ] **Task 2.4**: Update `init_campaign_from_templates` in `council/helpers.py` to ensure newly initialized campaigns write `system: d20_3gates`.

### Phase 3: Schema Versioning & Fail-Loud in `find_campaign`
- [ ] **Task 3.1**: Define `CURRENT_SCHEMA_VERSION = 1` in `council/helpers.py`.
- [ ] **Task 3.2**: Add YAML frontmatter with `schema_version: 1` to `templates/diario.template.md`.
- [ ] **Task 3.3**: Add YAML frontmatter with `schema_version: 1` to `campaigns/dinastia_cinzas/diario.md`, `campaigns/imperio_valiria/diario.md`, and `campaigns/perpetuos_terra_incognita/diario.md`.
- [ ] **Task 3.4**: Refactor `find_campaign` in `council/helpers.py` to validate `diario.md` presence and `schema_version`, raising `FileNotFoundError` or `ValueError` on invalid or missing schema.
- [ ] **Task 3.5**: Update CLI command handlers in `lazy_turn.py` to properly catch and format schema validation errors in human and JSON modes.

### Phase 4: CLI Sanitization (`lazy_turn.py`)
- [ ] **Task 4.1**: Sanitize `--focus` help string in `lazy_turn.py:build_cli()` (replace Fleur / Cedric with generic archetype examples).
- [ ] **Task 4.2**: Sanitize `--clock-advance` help string (replace Plano Kenjaku with generic clock example).
- [ ] **Task 4.3**: Sanitize `--scene-name` and `--location` help strings (replace Shinjuku with generic TTRPG scenes).
- [ ] **Task 4.4**: Sanitize `init-campaign` `--campaign` help string (replace cyber_neo_tokyo with generic ID example).

### Phase 5: Verification & Contract Tests
- [ ] **Task 5.1**: Add automated test cases in `tests/test_cli_contracts.py`:
  - Verify `rulesets/d20_3gates.py` exists and is directly importable.
  - Verify `find_campaign` raises `ValueError` or `FileNotFoundError` when `diario.md` lacks `schema_version` or is absent.
  - Verify all 3 active campaigns load cleanly with `schema_version: 1`.
  - Verify `lazy_turn.py --help` texts contain zero campaign-specific terms (`Shinjuku`, `Kenjaku`, `Fleur`, `Cedric`, `cyber_neo_tokyo`).
- [ ] **Task 5.2**: Run the full test suite (`python -m unittest discover tests`) to confirm all tests pass.

---

## 4. Acceptance Criteria Checklist

- [ ] `rulesets/d20_3gates.py` is standalone and fully functional.
- [ ] `system: d20_3gates` is declared across all campaign manifests and templates.
- [ ] `schema_version: 1` is declared in all `diario.md` files.
- [ ] `find_campaign` fails loudly when `schema_version` is missing, malformed, or exceeds supported version.
- [ ] `lazy_turn.py --help` text is 100% agnostic to individual campaigns and franchises.
- [ ] All automated contract tests pass with zero failures.
