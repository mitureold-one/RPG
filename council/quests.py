"""council/quests.py: Fachada de compatibilidade para resources/quests/."""

from __future__ import annotations

from resources.quests.ledger import (
    LEDGER_SECTION_HEADER,
    append_xp_ledger_entry,
    parse_xp_ledger_from_diario,
    parse_xp_ledger_from_text,
)
from resources.quests.mutations import (
    SECTION_HEADER,
    VALID_QUEST_STATUSES,
    VALID_QUEST_TYPES,
    upsert_quest_in_diario,
)
from resources.quests.parser import (
    format_quest_header,
    parse_quests_from_diario,
    parse_quests_from_text,
    parse_reward_xp,
)

__all__ = [
    "LEDGER_SECTION_HEADER",
    "SECTION_HEADER",
    "VALID_QUEST_STATUSES",
    "VALID_QUEST_TYPES",
    "append_xp_ledger_entry",
    "format_quest_header",
    "parse_quests_from_diario",
    "parse_quests_from_text",
    "parse_reward_xp",
    "parse_xp_ledger_from_diario",
    "parse_xp_ledger_from_text",
    "upsert_quest_in_diario",
]
