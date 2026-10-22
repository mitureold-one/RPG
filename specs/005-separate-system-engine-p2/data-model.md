# Phase 1 Data Model & Schemas: P2 Separação de Sistema e Motor

**Feature**: `separate-system-engine-p2`  
**Status**: Completed  
**Created**: 2026-10-21  
**Target Backlog Phase**: P2 (Engine & Ruleset Separation)

---

## 1. Schema Version Metadata in `diario.md`

### Definition & Location
Every `diario.md` file must declare `schema_version` at the top of the file using YAML frontmatter or HTML comment.

### Canonical Representation (YAML Frontmatter)
```markdown
---
schema_version: 1
---
# Diário da Crônica: {{TITULO_CAMPANHA}}

## Cena 1: {{NOME_CENA_INICIAL}}
...
```

### Parsing & Validation Rules
1. Regex detection:
   `r"^(?:---\s*\n.*?schema_version:\s*(\d+).*?\n---|(?:<!--\s*schema_version:\s*(\d+)\s*-->))"`
2. Type: Integer $\ge 1$.
3. Constraint: Declared `schema_version` must be $\le \text{CURRENT\_SCHEMA\_VERSION}$ (currently $1$).
4. Incompatible versions or missing metadata trigger an immediate loud failure (`ValueError`).

---

## 2. Campaign Mechanics Manifest in `regras.md`

### Definition & Location
The structured block in `regras.md` (under ````yaml:mechanics`) acts as the campaign mechanics manifest.

### Canonical Schema
```yaml:mechanics
system: d20_3gates
ruleset: d20_3gates
overrides:
  - id: optional_override_id
    effect: "Descrição do efeito diegético específico"
```

### Fields
| Field | Type | Required | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `system` | string | Yes | `"d20_3gates"` | Identifier of the active resolution system |
| `ruleset` | string | Optional | `system` value | Module name implementing the resolution ruleset |
| `overrides` | list | No | `[]` | List of campaign-specific mechanical exceptions |

---

## 3. Ruleset Output Data Model (`rulesets/d20_3gates.py`)

### 3.1 Single Action Roll Output
```json
{
  "natural": 14,
  "modifier": 2,
  "stat": "DES",
  "total": 16,
  "dc": 15,
  "variant": "normal",
  "tier": "Sucesso Pleno (Alcança o objetivo sem custos extras além do esforço normal)",
  "summary": "1d20 [14] + DES(+2) = 16 vs DC 15 -> Sucesso Pleno (...)"
}
```

### 3.2 Contest Roll Output (PC vs NPC or NPC vs NPC)
```json
{
  "is_contest": true,
  "is_npc_vs_npc": false,
  "p1": {
    "name": "Protagonista",
    "is_npc": false,
    "natural": 15,
    "stat": "FOR",
    "mod": 2,
    "total": 17,
    "roll_raw": "1d20 [15] + FOR(+2) = 17"
  },
  "p2": {
    "name": "Guarda Veterano",
    "is_npc": true,
    "natural": 12,
    "stat": "Composure",
    "mod": 1,
    "total": 13,
    "roll_raw": "1d20 [12] + Composure(+1) = 13"
  },
  "delta": 4,
  "tier": "Vitória Sólida do Protagonista",
  "outcome": "Protagonista prevalece sobre Guarda Veterano na disputa...",
  "cost_directive": "Avance o objetivo do protagonista...",
  "npc_reaction_mandate": "Guarda Veterano recua sob pressão...",
  "winner": "Protagonista",
  "summary": "[DISPUTA PC vs NPC] Protagonista: 17 vs Guarda Veterano: 13 -> Delta +4 -> Vitória Sólida"
}
```
