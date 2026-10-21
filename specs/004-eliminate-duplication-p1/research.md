# Phase 0 Research & Technical Rationale: P1 Deduplication & Cognitive Load Reduction

**Feature**: `eliminate-duplication-p1`  
**Status**: Completed  
**Created**: 2026-10-21  

---

## 1. Architecture of the Minimalist Root Router (`AGENTS.md`)

### Decision
Condense `AGENTS.md` from 72 lines down to at most 15 lines of pure routing logic.

```markdown
# RPGPRO Sovereign Router

Você é o Orquestrador Central do RPGPRO. Opere de forma autônoma e determinística.

Precedência Soberana:
- Grau 1 (Universal): Framework RPGPRO (regras universais, dados de 3 portões, SSOT Markdown).
- Grau 2 (Diegese): Regras e mundo da campanha ativa (`campaigns/<id>/regras.md` e `mundo.md`).
- Grau 3 (Psicologia): Análise de pesos dos NPCs (`campaigns/<id>/npcs.md`).

Roteamento de Campanhas & Skills:
- Identifique a campanha ativa em `campaigns/` (assuma a única existente ou indicada).
- Turnos de Ação: Delegue para `rpg-narrative-engine` (`lazy_turn.py prepare` -> obedeça estritamente a `step_3_writer_mandate` -> `lazy_turn.py commit`).
- Macro-Trama & Ritmo: Delegue sob demanda para `rpg-showrunner` (`lazy_turn.py plan`, `clock`, `arc`).
- Diretrizes Inegociáveis: Zero emojis, anti-puppeteering absoluto e SSOT estrito em Markdown.
```

### Rationale
`AGENTS.md` is loaded into context in every interaction within the workspace. By stripping prose micro-rules, CLI templates, and exhaustive explanations of dice gates from this root prompt, we save over 75% of static token overhead on every turn. The agent still knows its identity, sovereignty ladder, campaign folder location, skill routing, and the fundamental three-step turn cycle.

### Alternatives Considered
- *Retaining a 30-line version with abbreviated prose rules*: Rejected. Any static prose rule in `AGENTS.md` risks contradicting scene-specific mandates (e.g., forbidding dialogues in a dossier or requiring first-line canonical headers in an off-screen interlude). The runtime payload is the proper carrier of prose instructions.

---

## 2. Dynamic Prose Mandates Payload as SSOT (`council/writer.py`)

### Decision
Establish `council/writer.py` (and the runtime JSON field `step_3_writer_mandate` returned by `lazy_turn.py prepare`) as the single, authoritative source of truth for literary prose direction.
- `SKILL.md` and `references/1_turn_discipline_and_prose.md` state: *"Obedeça estritamente a `step_3_writer_mandate` retornado no JSON de preparação"*.
- Static documentation preserves only the *why* (context-adaptive direction per mode and scene type) and the inviolable negative constraints / anti-patterns:
  1. **Anti-Puppeteering**: Never narrate player character actions, choices, or dialogue.
  2. **Zero Emojis**: Strictly no emojis in prose, code, or data.
  3. **Zero Script Formatting**: Classical direct discourse with em-dashes (`—`); never `[Nome]: Fala`.
  4. **Actionable Dramatic Hook**: Land the scene returning tactical agency to the protagonist without didactic fourth-wall questions (*"O que você faz?"*).

### Rationale
In an interactive fiction engine with 10 distinct scene types (`standard`, `interlude`, `dossier`, `timeskip`, `prologue`, `epilogue`, etc.) and 6 specialized operating modes (`gm`, `narrator`, `writer`, `reviewer`, `architect`, `director`), prose instructions cannot be static. Hardcoding prose requirements in static markdown files forces the LLM to reconcile contradictory guidelines. The deterministic payload injected by `prepare` eliminates ambiguity.

---

## 3. Demarcation of Responsibilities: Showrunner vs Módulo 3

### Decision
- **`rpg-showrunner/SKILL.md`**: Owns operational guidance, strategic advice, and actionable CLI examples for macro-planning, faction threat clocks, scene queues, and arc transitions (`lazy_turn.py plan`, `clock`, `arc`).
- **`references/3_campaign_crud_and_state.md` (Módulo 3)**: Owns exclusively the SSOT Markdown schema of the 5 campaign files, specifically the structural format of `### Relógios de Ameaça & Prazos`, `### Planejamento de Trama & Fila de Cenas`, and `### Marcos da Crônica` inside `diario.md`. All CLI execution examples are excised and replaced with explicit pointers to `rpg-showrunner`.

### Rationale
Having both Módulo 3 and `rpg-showrunner` document CLI flags caused the exact drift observed in P0 (where one document documented `--advance "<Nome>:1"` and the CLI accepted `--advance <Nome> --steps 1`). Separating structural schema from operational execution prevents drift and cuts token duplication.

---

## 4. Centralization of the Difficulty Class (DC) Scale

### Decision
Extract the canonical DC ladder (DC 10 Fácil, DC 15 Média, DC 20 Difícil, DC 25 Extrema) out of campaign-level `regras.md` files:
- The base DC ladder belongs to Grade 1 (Universal Framework), anchored in `references/2_dice_engine_and_arbitration.md` and `council/gm.py` (which defaults to DC 15 when omitted).
- Campaign `regras.md` files (Grade 2) declare only resource economies (HP, Stamina, Energy), diegetic world laws, and *optional overrides* if a specific campaign alters standard difficulty classes.
- Update `templates/regras.template.md` and `council/helpers.py` (`init-campaign`) to omit the generic 4-line DC ladder, replacing it with an override declaration section.

### Rationale
In a multi-campaign environment, duplicating universal rules across every campaign violates SSOT. If the engine changes DC resolution tiers, updating individual campaign files should not be necessary unless a campaign explicitly declares an override.
