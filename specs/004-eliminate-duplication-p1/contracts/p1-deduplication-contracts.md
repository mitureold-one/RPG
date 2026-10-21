# P1 Deduplication & Cognitive Load Reduction Contracts

**Feature**: `eliminate-duplication-p1`  
**Status**: Completed  
**Created**: 2026-10-21  

---

## 1. AGENTS.md Line Count & Content Contract

* **File Location**: `AGENTS.md` (root)
* **Maximum Line Count**: $\le 15$ non-empty lines.
* **Prohibited Content**:
  - Zero detailed CLI code blocks with flags (`--action`, `--stat`, `--dc`).
  - Zero prose style rules (no paragraphs on em-dashes, no forbidden tags, no 4 dramatic beats, no headers).
  - Zero duplication of dice gate math.
* **Mandatory Inclusions**:
  - Sovereignty hierarchy: Grau 1 (Universal), Grau 2 (Diegese), Grau 3 (Psicologia).
  - Campaign active routing.
  - Skill routing (`rpg-narrative-engine` and `rpg-showrunner`).
  - Three-step action loop: `prepare` -> obey `step_3_writer_mandate` -> `commit`.
  - Inviolable directives: Zero emojis, anti-puppeteering, Markdown SSOT.

---

## 2. Prose Mandates Delegation Contract

* **Runtime Contract**:
  - `lazy_turn.py prepare` emits `"step_3_writer_mandate"` containing `scene_type`, `why_this_structure`, `structure_and_tone`, and `dialogue_and_style`.
  - When `--scene-type <tipo>` is provided, the mandate returned must match `STRUCTURAL_SCENE_MANDATES[<tipo>]`.
* **Documentation Contract**:
  - `rpg-narrative-engine/SKILL.md` and `references/1_turn_discipline_and_prose.md` MUST explicitly cite `step_3_writer_mandate` as the runtime authority for text generation.
  - Negative constraints are defined at the framework level (Anti-Puppeteering, Zero Emojis, Zero Script Formatting `Nome: Fala`, Actionable Dramatic Hook).

---

## 3. Showrunner vs Module 3 Boundary Contract

* **`references/3_campaign_crud_and_state.md` Contract**:
  - Sections 4 and 6 MUST NOT contain executable CLI examples of `python lazy_turn.py clock` or `python lazy_turn.py plan`.
  - Sections 4 and 6 MUST contain Markdown schemas for how clocks, scene queues, and milestones are formatted in `diario.md`.
  - Sections 4 and 6 MUST include explicit reference links delegating operational usage to `rpg-showrunner`.
* **`rpg-showrunner/SKILL.md` Contract**:
  - Retains exclusive ownership of CLI command documentation for `plan`, `clock`, and `arc`.

---

## 4. DC Ladder Centralization Contract

* **Universal Framework (Grade 1)**:
  - Canonical ladder defined in `references/2_dice_engine_and_arbitration.md`: DC 10 (Fácil), DC 15 (Média), DC 20 (Difícil), DC 25 (Extrema).
  - Engine default in `council/gm.py` remains DC 15 when unspecified.
* **Campaign Rules (Grade 2)**:
  - The files `campaigns/dinastia_cinzas/regras.md`, `campaigns/imperio_valiria/regras.md`, and `campaigns/perpetuos_terra_incognita/regras.md` MUST NOT contain the 4-line bulleted list of standard DC examples (`* **DC 10...**, * **DC 15...**`, etc.).
  - Campaign files declare resource mechanics, diegetic rules, and state either "Nenhum override ativo — utiliza a escala universal padrão" or specific diegetic thresholds.
  - `templates/regras.template.md` and `council/helpers.py` (`init-campaign`) follow this contract for newly initialized campaigns.
