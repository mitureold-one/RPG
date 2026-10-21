# Research & Technical Decisions: Narrative State & Progression Engine

**Feature**: `narrative-state-progression`  
**Phase**: Phase 0 (Research & Feasibility)  
**Status**: Completed  
**Date**: 2026-10-18  

---

## 1. Technical Context & Unknowns

The core requirement is to prevent narrative stagnation and guarantee deterministic progression across three scales (Scene, Arc, World) without sacrificing the existing Markdown SSOT architecture (`campaigns/<id>/*.md`) or introducing external dependencies/database overhead.

### Key Unknowns Investigated:
1. **Clock Storage & Representation**: Where and how should narrative clocks (ticking countdowns) live in the Markdown SSOT so they are human-readable, easily parsed by regex, and synchronized with `diario.md`?
2. **Tri-Scale Modeling**: How to represent the Scene vs. Arc vs. World separation without breaking backward compatibility for existing campaigns like `jjk_sakigake`?
3. **Inertia Detection Heuristics**: How to reliably detect narrative stagnation (e.g. characters talking in circles across 2+ turns) without fragile NLP libraries?
4. **Integration with `lazy_turn.py`**: How to update `prepare` and `commit` so the LLM is deterministically held accountable for producing a state change in every turn.

---

## 2. Research Findings & Decisions

### Decision 1: SSOT Representation for Clocks & Arc State
* **Decision**: Store active narrative clocks and the current Arc definition directly in `diario.md` under standardized markdown headings, with long-term faction agendas documented in `mundo.md`.
* **Rationale**:
  - `diario.md` is already read and updated on every single turn during `prepare` and `commit`.
  - Storing clocks directly in `diario.md` (e.g., `###  Relógios de Ameaça & Facções`) guarantees that clock progression is co-located with the timeline and turn ledger.
  - Keeps the entire system zero-dependency and 100% human-editable.
* **Format**:
  ```markdown
  ###  Relógios de Ameaça & Prazos
  * **[Plano de Kenjaku / Shibuya]:** 4/6 (Gatilho: Ataque coordenado)
  * **[Conselho de Tóquio / Investigação]:** 2/4 (Gatilho: Mandado de prisão)
  ```
* **Alternatives Considered**:
  - *Separate `clocks.json` or `clocks.md`*: Rejected. Increases file proliferation and risks desynchronization with `diario.md`.
  - *Database/SQLite*: Rejected (Violates the SSOT Markdown core tenet).

---

### Decision 2: Tri-Scale Model Integration
* **Decision**: Structure the `council_pipeline` in `lazy_turn.py prepare` with explicit Tri-Scale payload blocks:
  1. **`world_scale`** (Arquiteto): Active Faction Clocks, time elapsed since last world event, imminent deadlines.
  2. **`arc_scale`** (Arquiteto/Narrador): Active Arc Name, Central Dramatic Question, Current Stage (`Preparação`, `Confrontação`, `Clímax`).
  3. **`scene_scale`** (Narrador/Escritor): Immediate scene tension, resistance type (social, physical, moral), and requirement of an explicit **Mudança de Estado**.
* **Rationale**:
  - The LLM receives dedicated prompts for each scale in the exact phase where that specialist operates.
  - Prevents the Narrador from tunnel-visioning only on the immediate room.
* **Alternatives Considered**:
  - *Free-form prompt instructions*: Rejected. Without structured fields in the prepare JSON, LLMs forget the macro layer after 2-3 turns.

---

### Decision 3: Deterministic Inertia Detection (Anti-Stagnation)
* **Decision**: Implement an algorithmic heuristic in `cmd_review` / `cmd_prepare` that analyzes the last 3 entries in `diario.md`:
  - Checks if the `--state_shift` / `Mudança de Estado` field was omitted or identical.
  - Checks if in-game time advanced by $\ge 4$ hours without any clock progression or location change.
  - Checks if any Narrative Clock has reached or exceeded its segment cap without triggering a rupture.
* **Outcome**: Emits a `NARRATIVE_STAGNATION` warning or `CLOCK_BREACHED` alert into the pre-turn audit, which escalates `is_critical_turn = True` and mandates a *Ruptura de Normalidade* in the prompt.
* **Alternatives Considered**:
  - *LLM semantic similarity check on summaries*: Rejected. High latency, non-deterministic, and prone to hallucinations. A simple metadata-driven audit is fast, free, and robust.

---

### Decision 4: CLI Interface Extensions in `lazy_turn.py`
* **Decision**:
  1. Add `lazy_turn.py clock`: CLI command to inspect, advance, or create clocks (`--advance`, `--set`, `--add`).
  2. Extend `lazy_turn.py commit`: Add optional flags `--state-shift "<Mudança ocorrida no turno>"` and `--clock-advance "<Nome:Passos>"`.
  3. Extend `lazy_turn.py prepare`: Auto-advance clocks proportionally when `--time` exceeds significant thresholds if configured, and always include `world_scale` and `arc_scale` in the payload.
* **Rationale**:
  - Seamlessly integrates with the existing developer/agent workflow.
  - Keeps backward compatibility: existing commands without `--state-shift` will default gracefully while prompting the user/agent.

---

## 3. Constitution & Guardrail Check

| Principle | Status | Evaluation |
| :--- | :--- | :--- |
| **YAGNI / Minimal Diff** | PASS | Reuses existing regex parsers in `lazy_turn.py`, builds on `diario.md`. Zero new files outside the spec/test suite. |
| **Zero External Dependencies** | PASS | Standard library only (`re`, `json`, `pathlib`, `sys`, `argparse`). |
| **Markdown SSOT Integrity** | PASS | All state remains human-readable plain text in `campaigns/<id>/*.md`. |
| **Anti-Puppeteering** | PASS | State shifts affect the world, NPCs, and environments; player internal agency remains untouched. |
