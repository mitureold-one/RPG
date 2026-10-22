# Implementation Tasks: P2 Separação de Sistema e Motor

**Feature**: `separate-system-engine-p2`  
**Spec**: [spec.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/005-separate-system-engine-p2/spec.md)  
**Plan**: [plan.md](file:///c:/Users/Konor/Documents/RPGPRO/specs/005-separate-system-engine-p2/plan.md)  
**Status**: Completed  

---

## Phase 1: Setup & Pre-Flight Checks

- [X] T001 Verify baseline CLI and test suite passing in `tests/test_cli_contracts.py`

---

## Phase 2: Foundational Tasks (Ruleset Directory Infrastructure)

- [X] T002 Create ruleset package directory and initialization module in `rulesets/__init__.py`

---

## Phase 3: User Story 1 - Modular Ruleset Extraction & System Declaration (Priority: P1)

*Goal*: Decouple dice mechanics and resolution logic into `rulesets/d20_3gates.py`, declare `system: d20_3gates` in campaign manifests, and route resolution through the ruleset layer.  
*Independent Test Criteria*: `python -c "import rulesets.d20_3gates as r; res = r.roll_3_gates('Ação', dc=15); assert res['dc'] == 15"` executes cleanly; active campaign `regras.md` files contain `system: d20_3gates`.

- [X] T003 [P] [US1] Extract `roll_3_gates`, `extract_npc_contest_modifier`, `roll_contest`, and `DC_LADDER` from `council/gm.py` into standalone module `rulesets/d20_3gates.py`
- [X] T004 [US1] Refactor `council/gm.py` to import and re-export `roll_3_gates`, `extract_npc_contest_modifier`, and `roll_contest` from `rulesets.d20_3gates`, keeping character vitals parsing (`parse_cost_string`)
- [X] T005 [P] [US1] Update `templates/regras.template.md` to declare `system: d20_3gates` in the `yaml:mechanics` block
- [X] T006 [P] [US1] Update active campaigns (`campaigns/dinastia_cinzas/regras.md`, `campaigns/imperio_valiria/regras.md`, `campaigns/perpetuos_terra_incognita/regras.md`) to include `system: d20_3gates` in `yaml:mechanics`
- [X] T007 [US1] Implement helper functions `get_campaign_system(campaign_id)` and `load_ruleset(system_name)` in `council/helpers.py` to dynamically load the active ruleset
- [X] T008 [US1] Update `init_campaign_from_templates` in `council/helpers.py` and `lazy_turn.py` to route resolution through `load_ruleset`

---

## Phase 4: User Story 2 - Strict Schema Versioning & Loud Failure in `find_campaign` (Priority: P1)

*Goal*: Enforce `schema_version: 1` in all `diario.md` files and ensure `find_campaign` fails loudly with explicit exceptions whenever `diario.md` is missing, unversioned, or incompatible.  
*Independent Test Criteria*: Calling `find_campaign` on a campaign without `schema_version` raises `ValueError`, and on missing `diario.md` raises `FileNotFoundError`; all 3 active campaigns load cleanly with `schema_version == 1`.

- [X] T009 [US2] Define constant `CURRENT_SCHEMA_VERSION = 1` in `council/helpers.py`
- [X] T010 [P] [US2] Add YAML frontmatter declaring `schema_version: 1` to `templates/diario.template.md`
- [X] T011 [P] [US2] Add YAML frontmatter declaring `schema_version: 1` to `campaigns/dinastia_cinzas/diario.md`, `campaigns/imperio_valiria/diario.md`, and `campaigns/perpetuos_terra_incognita/diario.md`
- [X] T012 [US2] Refactor `find_campaign` in `council/helpers.py` to validate `diario.md` presence and `schema_version`, raising `FileNotFoundError` or `ValueError` on failure and returning enriched metadata (`schema_version` and `system`)
- [X] T013 [US2] Update command handlers in `lazy_turn.py` (`cmd_prepare`, `cmd_commit`, `cmd_review`, `cmd_clock`, `cmd_plan`, `cmd_arc`, `cmd_npc`) to catch schema exceptions and report user-friendly errors in standard and JSON modes

---

## Phase 5: User Story 3 - Agnostic CLI Help Sanitization (Priority: P2)

*Goal*: Eliminate all setting-specific and franchise-specific names from `lazy_turn.py` help strings, ensuring the universal CLI remains neutral.  
*Independent Test Criteria*: `lazy_turn.py --help` and all subparser helps contain zero occurrences of `Shinjuku`, `Kenjaku`, `Fleur`, `Cedric`, `Krum`, or `cyber_neo_tokyo`.

- [X] T014 [US3] Sanitize help strings in `lazy_turn.py:build_cli()` (replace `Fleur / Cedric, Krum` in `--focus`, `Plano Kenjaku:1` in `--clock-advance`, `O Colapso em Shinjuku` in `--scene-name`, `Tóquio, Distrito de Shinjuku` in `--location`, and `cyber_neo_tokyo` in `init-campaign` with generic TTRPG archetypes)

---

## Phase 6: Polish & Automated Contract Tests

- [X] T015 Add automated unit tests to `tests/test_cli_contracts.py` to enforce:
  - Direct import and execution of `rulesets.d20_3gates`
  - Loud failure (`ValueError` / `FileNotFoundError`) in `find_campaign` on unversioned or absent `diario.md`
  - Successful loading of all active campaigns with `schema_version == 1` and `system == "d20_3gates"`
  - Total absence of franchise/campaign-specific terms in `lazy_turn.py` help texts
- [X] T016 Execute the full test suite (`python -m unittest discover tests`) and verify all scenarios in `specs/005-separate-system-engine-p2/quickstart.md`

---

## Dependencies & Completion Order

```
Phase 1: Setup (T001)
   │
Phase 2: Foundational Ruleset Package (T002)
   │
   ├─────────────────────────────────────────────────┬─────────────────────────────────────────────────┐
   ▼                                                 ▼                                                 ▼
Phase 3: US1 Modular Ruleset (T003-T008)          Phase 4: US2 Schema Versioning (T009-T013)        Phase 5: US3 CLI Sanitization (T014)
   │                                                 │                                                 │
   └─────────────────────────────────────────────────┴─────────────────────────────────────────────────┘
                                                     │
                                                     ▼
                                 Phase 6: Polish & Contract Tests (T015-T016)
```

### Parallel Opportunities Identified
- T003 (extract `d20_3gates.py`), T005 (template regras), and T006 (active campaign regras) can be executed in parallel.
- T010 (template diario) and T011 (active campaign diarios) can be executed in parallel.
- US1, US2, and US3 are largely decoupled and can be implemented in parallel once foundational T002 is complete.

### MVP Scope Recommendation
The core architectural isolation of the engine is achieved with **User Story 1 (Modular Ruleset)** and **User Story 2 (Schema Enforcement)**. Completing all three stories brings RPGPRO to full P2 compliance.
