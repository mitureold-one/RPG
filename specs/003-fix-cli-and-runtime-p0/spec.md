# Feature Specification: P0 Runtime & CLI Fixes

**Feature Name**: `fix-cli-and-runtime-p0`  
**Status**: Draft  
**Created**: 2026-10-21  
**Target Backlog Phase**: P0 (Architectural Review Remediation)

---

## 1. Executive Summary & Problem Statement

A recent comprehensive architectural review revealed critical runtime discrepancies and synchronization debts in the RPGPRO ecosystem that directly impair runtime execution and inflate neural context:

1. **CLI Documentation Mismatch in `rpg-showrunner`**: The skill documentation references non-existent command-line flags (`--add-scene`, `--type`, `--trigger`, `--complete-scene <ID>`, `--advance "<Nome>:1"`, `--resolve-clocks "<lista>"`). When the model follows the documentation, `argparse` aborts execution in the middle of a gaming turn.
2. **Orphan Scene Types**: The `--scene-type` argument in `lazy_turn.py` allows 10 choices, but `council/writer.py` only implements mandates for 7 types. The choices `prologue`, `epilogue`, and `post_credits` fall back to the default `standard` mandate, defeating their specialized literary purpose.
3. **Showrunner Over-Activation**: `rpg-showrunner/SKILL.md` declares automatic activation on every turn ("Ativa-se automaticamente"), which loads unnecessary context, creates competing authority over turn execution, and drains token bandwidth.
4. **Hardcoded Machine Links**: `rpg-narrative-engine/SKILL.md` contains absolute Windows paths (`file:///C:/Users/Konor/...`), breaking skill portability across environments.

This P0 feature resolves all immediate breakages and runtime friction, ensuring deterministic tool calls, comprehensive scene formatting, and localized references.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Executing Macro-Planning Commands Without CLI Failures
* **As a** Game Master agent consulting the Showrunner guidelines,
* **I want** documented CLI commands for `plan`, `clock`, and `arc` to match the exact arguments accepted by `lazy_turn.py`,
* **So that** execution never aborts due to unrecognized or malformed flags.
* **Acceptance Criteria**:
  - `lazy_turn.py plan --campaign <id> --add "<Título>" --scene-type <tipo> [--beat "<detalhes>"]` runs without error.
  - `lazy_turn.py plan --campaign <id> --complete <index>` runs without error.
  - `lazy_turn.py clock --campaign <id> --advance "<Nome>" --steps <int>` runs without error.
  - `lazy_turn.py arc --campaign <id> --advance-act --target-act <N> [--resolve-clocks]` runs without error.
  - No documented command produces an `argparse` unrecognized arguments error.

### User Scenario 2: Invoking Arc Framing Scenes (Prologue, Epilogue, Post-Credits)
* **As a** player or GM transitioning between major campaign arcs,
* **I want** to execute `prepare` with `--scene-type prologue`, `--scene-type epilogue`, or `--scene-type post_credits`,
* **So that** the writer receives explicit literary mandates tailored to arc exposition, aftermath resolution, or cliffhangers rather than a generic standard micro-action mandate.
* **Acceptance Criteria**:
  - `prepare` with `--scene-type prologue` outputs a literary mandate emphasizing mythic exposition, foreshadowing, and world staging before the protagonist's active journey.
  - `prepare` with `--scene-type epilogue` outputs a literary mandate emphasizing societal fallout, long-term personal consequences, and emotional closure following arc climax.
  - `prepare` with `--scene-type post_credits` outputs a literary mandate emphasizing punchy, cinematic cliffhangers and emergent threats.
  - None of these three scene types fallback silently to `standard`.

### User Scenario 3: Clean Turn-by-Turn Context Without Showrunner Clutter
* **As a** Game Master orchestrating regular player turns,
* **I want** the Showrunner skill to remain idle during standard turns,
* **So that** token overhead is minimized and there is zero conflict of authority over turn arbitration.
* **Acceptance Criteria**:
  - The skill description and frontmatter for `rpg-showrunner` explicitly trigger on demand (planning, pacing audit, arc transition, or threat clocks), not automatically on every turn.
  - The turn loop is governed exclusively by the narrative engine.

### User Scenario 4: Cross-Environment Skill Portability
* **As a** developer or agent operating the RPGPRO project in different workspaces or operating systems,
* **I want** all references inside `SKILL.md` to use relative paths,
* **So that** documentation and sub-modules link correctly without depending on a specific local user directory (`C:/Users/Konor/...`).
* **Acceptance Criteria**:
  - Zero occurrences of `file:///C:/Users/Konor/` exist in `rpg-narrative-engine/SKILL.md` or `rpg-showrunner/SKILL.md`.
  - All reference links resolve relative to the skill folder (`references/...`).

---

## 3. Functional Requirements

### 3.1 Showrunner CLI Alignment
* **FR-01**: `rpg-showrunner/SKILL.md` must update all CLI examples to strictly match `lazy_turn.py` parameter signatures:
  - Replace `--add-scene` with `--add` and optional `--beat`.
  - Replace `--type` with `--scene-type`.
  - Remove references to non-existent `--trigger` flag.
  - Replace `--complete-scene <ID>` with `--complete <índice-inteiro>`.
  - Replace `--advance "<Nome>:1"` with `--advance <Nome> --steps 1`.
  - Document `--resolve-clocks` as a boolean flag rather than taking a string argument.

### 3.2 Writer Mandates for Orphan Scene Types
* **FR-02**: `council/writer.py` must define distinct structural mandates in `mandates_by_type` for:
  - `prologue`: Framing ancient lore, faction chessboards, or impending omens prior to protagonist involvement.
  - `epilogue`: Framing macro-societal consequences, quiet aftermath, and long-term character destiny after climax.
  - `post_credits`: Punchy, cinematic hook revealing a hidden actor or emerging crisis.
* **FR-03**: All 10 choices registered in `lazy_turn.py` for `--scene-type` (`standard`, `interlude`, `parallel`, `timeskip`, `montage`, `dossier`, `flashback`, `prologue`, `epilogue`, `post_credits`) must have a corresponding non-fallback entry in `mandates_by_type`.

### 3.3 Skill Activation Disjunction
* **FR-04**: The frontmatter description and introductory text of `rpg-showrunner/SKILL.md` must be modified:
  - Remove "Ativa-se automaticamente para governar a fila de cenas...".
  - Replace with on-demand activation triggered by explicit user intent (planning scenes, advancing campaign arcs, auditing narrative pacing, or managing faction clocks).

### 3.4 Skill Reference Path Relativization
* **FR-05**: In `rpg-narrative-engine/SKILL.md`, replace absolute URIs pointing to `file:///C:/Users/Konor/Documents/RPGPRO/.agents/skills/rpg-narrative-engine/references/...` with clean relative paths (`references/...`).

---

## 4. Success Criteria

* **SC-01 (Zero CLI Errors)**: 100% of CLI code blocks documented in `rpg-showrunner/SKILL.md` execute successfully against `lazy_turn.py` without argument parsing errors.
* **SC-02 (Full Scene Type Coverage)**: Every one of the 10 supported `--scene-type` values produces a specialized literary directive containing distinct narrative guidance.
* **SC-03 (Context Isolation)**: The Showrunner skill definition does not claim automatic activation on regular turns.
* **SC-04 (Zero Hardcoded Paths)**: A workspace search for `C:/Users/Konor` inside `.agents/skills` returns zero hits.

---

## 5. Assumptions & Dependencies

* The core CLI structure in `lazy_turn.py` is the Single Source of Truth for tool execution.
* The 10 scene types in `lazy_turn.py` remain the canonical list of narrative structural devices.
* No changes to database schemas or Markdown SSOT formats are required for this P0 phase.
