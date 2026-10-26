"""council/factions.py: Fachada Reexportadora de Facções, Reputação e Tick (RPGPRO).

Compatibilidade retroativa estrita (R2). Delega para submódulos em resources/factions/.
"""

from resources.factions.parser import (
    FACTION_SECTION_HEADER,
    REPUTATION_TIERS,
    SOCIAL_DC_MODIFIERS,
    SUGGESTED_VARIANTS,
    VALID_SCALES,
    clamp_reputation,
    format_faction_line,
    legacy_label_to_score,
    normalize_ascii_slug,
    parse_factions_from_mundo,
    score_to_tier_name,
    upsert_faction_in_mundo,
)
from resources.factions.reputation import (
    FACTION_LEDGER_HEADER,
    append_faction_ledger_entry,
    parse_faction_ledger_from_diario,
    parse_reputation_from_ficha,
    update_reputation_in_ficha,
)
from resources.factions.tick import (
    simulate_faction_tick,
)
from resources.factions.context import (
    resolve_scene_factions,
)

__all__ = [
    "FACTION_SECTION_HEADER",
    "FACTION_LEDGER_HEADER",
    "REPUTATION_TIERS",
    "SOCIAL_DC_MODIFIERS",
    "SUGGESTED_VARIANTS",
    "VALID_SCALES",
    "append_faction_ledger_entry",
    "clamp_reputation",
    "format_faction_line",
    "legacy_label_to_score",
    "normalize_ascii_slug",
    "parse_faction_ledger_from_diario",
    "parse_factions_from_mundo",
    "parse_reputation_from_ficha",
    "resolve_scene_factions",
    "score_to_tier_name",
    "simulate_faction_tick",
    "update_reputation_in_ficha",
    "upsert_faction_in_mundo",
]
