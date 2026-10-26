"""council/narrator.py: Fachada de compatibilidade para resources/npcs/."""

from __future__ import annotations

from resources.npcs.initiative import (
    derive_npc_initiative,
    extract_epistemic_forbidden_terms,
    find_scene_relational_tensions,
)
from resources.npcs.mutations import (
    apply_npc_updates_to_md,
    upsert_npc_to_md,
)
from resources.npcs.parser import (
    _NPC_PIPE_RE,
    _NPC_SEPARATOR_RE,
    _NPC_SUBFIELDS,
    extract_md_field,
    extract_npc_bonds,
    parse_npc_update_fields,
    parse_npcs_md,
    split_npc_updates,
)
from resources.npcs.scene_director import (
    derive_situational_scene_structures,
)

__all__ = [
    "_NPC_PIPE_RE",
    "_NPC_SEPARATOR_RE",
    "_NPC_SUBFIELDS",
    "apply_npc_updates_to_md",
    "derive_npc_initiative",
    "derive_situational_scene_structures",
    "extract_epistemic_forbidden_terms",
    "extract_md_field",
    "extract_npc_bonds",
    "find_scene_relational_tensions",
    "parse_npc_update_fields",
    "parse_npcs_md",
    "split_npc_updates",
    "upsert_npc_to_md",
]
