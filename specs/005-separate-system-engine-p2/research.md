# Phase 0 Research & Technical Rationale: P2 Separação de Sistema e Motor

**Feature**: `separate-system-engine-p2`  
**Status**: Completed  
**Created**: 2026-10-21  
**Target Backlog Phase**: P2 (Engine Modularization, Schema Enforcement & CLI Sanitization)

---

## 1. Modular Ruleset Extraction (`rulesets/d20_3gates.py`)

### Decision
Extract the mathematical resolution mechanics of the d20 3-Gates model from `council/gm.py` into a standalone ruleset module at `rulesets/d20_3gates.py` (with a clean package structure under `rulesets/`).
The extracted interface must provide:
- `roll_3_gates(label: str, variant: str = "normal", dc: int = 15, stat_name: str = "", stat_val: int = 10) -> dict`
- `extract_npc_contest_modifier(npc: dict, stat_requested: str = "") -> tuple`
- `roll_contest(pc_name: str, pc_stat_name: str, pc_stat_val: int, npc_name: str, npc_stat_name: str, npc_stat_mod: int, pc_variant: str = "normal", npc_variant: str = "normal", p1_is_npc: bool = False) -> dict`
- Standard difficulty scale constant `DC_LADDER = {"Fácil": 10, "Média": 15, "Difícil": 20, "Extrema": 25}`.

`council/gm.py` will serve as the transition facade and engine coordinator:
- Import or dynamically dispatch to `rulesets.d20_3gates`.
- Retain resource parsing logic (`parse_cost_string`) which belongs to the character sheet/vitals domain, not to dice mathematics.

### Rationale
In accordance with `DECISOES_ARQUITETURA.md` (Decision 2), the Core Engine (L1) governs Markdown SSOT persistence, lifecycle transitions, and turn audits. The actual dice mechanics (L1b) belong to a ruleset. By extracting `d20_3gates.py`, the engine can load alternative systems (e.g., 3d6, d100, Dice Pool, PBTA) simply by changing the system identifier declared in the campaign.

### Alternatives Considered
- *Keeping mechanics in `council/gm.py` and using `if system == 'd20'` branching*: Rejected. Causes monolithic growth and prevents third-party or custom rulesets from being added cleanly without modifying the core engine.
- *Full abstract class inheritance with ABC*: Rejected (YAGNI / Ponytail rule). In Python, duck typing with standard module functions (`roll_3_gates`, `roll_contest`) is cleaner, lighter, and requires zero boilerplate classes.

---

## 2. Campaign System Declaration (`system:` in Campaign Manifest)

### Decision
The campaign's mechanics manifest in `regras.md` (and template) must explicitly declare `system: d20_3gates`:
```yaml:mechanics
system: d20_3gates
ruleset: d20_3gates
overrides: []
```
In `council/helpers.py`, a helper `get_campaign_system(campaign_id: str) -> str` will parse the `regras.md` file of the campaign to read `system:`. If omitted in legacy files, it defaults safely to `"d20_3gates"`.

### Rationale
This creates a contract between the campaign and the engine. The engine inspects the manifest to know which ruleset to invoke during `lazy_turn.py prepare`.

---

## 3. Mandatory `schema_version` in `diario.md` & Fail-Loud in `find_campaign`

### Decision
1. **Schema Declaration in `diario.md`**:
   Every canonical `diario.md` must declare `schema_version` at the very beginning of the file, supporting standard YAML frontmatter:
   ```markdown
   ---
   schema_version: 1
   ---
   # Diário da Crônica: {{TITULO_CAMPANHA}}
   ```
   Or an HTML comment:
   ```markdown
   <!-- schema_version: 1 -->
   ```
2. **Current Supported Version**:
   Define `CURRENT_SCHEMA_VERSION = 1` in `council/helpers.py`.
3. **Fail-Loud in `find_campaign(campaign_id)`**:
   Refactor `find_campaign` in `council/helpers.py`:
   - If the campaign directory does not exist, return `None` (preserving standard discovery semantics).
   - If the directory exists but `diario.md` is missing: raise `FileNotFoundError(f"Campanha '{campaign_id}' corrompida: 'diario.md' não encontrado em {camp_dir}.")`.
   - If `diario.md` exists but lacks `schema_version`: raise `ValueError(f"Campanha '{campaign_id}' inválida: 'diario.md' não declara 'schema_version' (ex: 'schema_version: 1').")`.
   - If declared `schema_version > CURRENT_SCHEMA_VERSION`: raise `ValueError(f"Campanha '{campaign_id}' incompatível: schema_version {version} é superior à versão suportada pelo motor ({CURRENT_SCHEMA_VERSION}).")`.
   - Return dictionary enriched with `"schema_version": version` and `"system": system_name`.

### Rationale
Previously, `find_campaign` only checked `camp_dir.is_dir()`, silently returning paths even if files were missing or corrupted. This led to confusing mid-turn crashes deep in regex parsers. Failing loudly at discovery time provides instant feedback, surfaces corruption immediately, and protects player state.

### Alternatives Considered
- *Returning an error dict `{"error": ...}` instead of raising an exception*: Rejected for core helpers. Returning `None` or error dicts causes silent downstream `TypeError: 'NoneType' object is not subscriptable` bugs. Raising explicit exceptions allows CLI entrypoints to cleanly catch and format the failure (with appropriate exit codes and JSON error responses).

---

## 4. CLI Help Text Sanitization (`lazy_turn.py`)

### Decision
Systematically sanitize all help strings in `lazy_turn.py:build_cli()`:
- `p_prep --focus`: Change `(ex: 'Fleur' ou 'Cedric, Krum')` to `(ex: 'Vanguarda' ou 'Capitão, Batedor')`.
- `p_com --clock-advance`: Change `(ex: 'Plano Kenjaku:1' ou 'Ataque:2')` to `(ex: 'Invasão:1' ou 'Conspiração:2')`.
- `p_arc --scene-name`: Change `(ex: 'O Colapso em Shinjuku')` to `(ex: 'O Cerco da Fortaleza')`.
- `p_arc --location`: Change `(ex: 'Tóquio, Distrito de Shinjuku')` to `(ex: 'Fronteira Norte, Posto Avançado')`.
- `p_init --campaign`: Change `(ex: 'cyber_neo_tokyo')` to `(ex: 'fantasia_reinos')`.

### Rationale
The CLI is part of the universal engine framework (L1). Embedding specific franchise or campaign entities in command help text breaks the agnosticism of the tool and leaks private campaign fiction into public developer tooling.
