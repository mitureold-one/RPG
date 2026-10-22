# Interface Contracts: P2 Separação de Sistema e Motor

**Feature**: `separate-system-engine-p2`  
**Status**: Active  
**Created**: 2026-10-21  
**Target Backlog Phase**: P2 (Engine & Ruleset Separation)

---

## 1. Ruleset Interface Contract (`rulesets/<system>.py`)

Any ruleset implementation must adhere to the following function contract:

### 1.1 Action Resolution Function
```python
def roll_3_gates(
    label: str,
    variant: str = "normal",
    dc: int = 15,
    stat_name: str = "",
    stat_val: int = 10,
) -> dict:
    """Executes single action resolution using circumstance, dice, and DC comparison."""
    ...
```

### 1.2 NPC Contest Modifier Extraction
```python
def extract_npc_contest_modifier(
    npc: dict,
    stat_requested: str = "",
) -> tuple[str, int]:
    """Extracts a stat name and modifier value from NPC psychology (Hexagon) or classification."""
    ...
```

### 1.3 Opposed Contest Resolution Function
```python
def roll_contest(
    pc_name: str,
    pc_stat_name: str,
    pc_stat_val: int,
    npc_name: str,
    npc_stat_name: str,
    npc_stat_mod: int,
    pc_variant: str = "normal",
    npc_variant: str = "normal",
    p1_is_npc: bool = False,
) -> dict:
    """Executes opposed contest between PC and NPC, or between two NPCs."""
    ...
```

---

## 2. Discovery & Validation Contract (`council/helpers.py:find_campaign`)

### Signature
```python
def find_campaign(campaign_id: str) -> dict | None:
    """Discovers a campaign directory and verifies schema integrity.
    
    Returns:
        dict: Path mapping enriched with 'schema_version' and 'system' metadata.
        None: If campaign directory does not exist.
        
    Raises:
        FileNotFoundError: If campaign folder exists but 'diario.md' is missing.
        ValueError: If 'schema_version' is missing, non-numeric, or greater than CURRENT_SCHEMA_VERSION.
    """
    ...
```

### Return Dictionary Schema
```python
{
    "type": "markdown",
    "dir": Path,
    "ficha": Path,
    "diario": Path,
    "npcs": Path,
    "mundo": Path,
    "regras": Path,
    "schema_version": int,
    "system": str,
}
```

---

## 3. CLI Help Contract Sanitization (`lazy_turn.py`)

All argument parser descriptions and help strings must be validated against the forbidden franchise list:
- Forbidden terms in CLI help:
  - `Shinjuku`
  - `Kenjaku`
  - `Fleur`
  - `Cedric`
  - `Krum`
  - `cyber_neo_tokyo`
- Allowed replacements:
  - Archetype names (`Aliado`, `Mentor`, `Invasor`)
  - Generic locations (`Cidadela Superior`, `Fronteira Norte`, `Posto Avançado`)
  - Generic clock names (`Invasão:1`, `Conspiração:2`, `Ameaça:1`)
