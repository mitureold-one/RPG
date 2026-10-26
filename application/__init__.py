"""Camada de aplicação: casos de uso e fronteira transacional.

Orquestra os módulos de domínio (`council/`, `rulesets/`) e é dona da
serialização de mutações por campanha. Não importa `interfaces/` nem
`lazy_turn`.
"""

from council import (
    cmd_review,
    find_campaign,
    init_campaign_from_templates,
    upsert_npc_to_md,
)
from application.commit import cmd_commit
from application.commit_validation import validate_commit_entities
from application.factions import cmd_faction
from application.prepare import cmd_prepare
from application.progression import cmd_progress, cmd_quest
from application.prose import cmd_check_prose
from application.showrunner import cmd_arc, cmd_clock, cmd_correct, cmd_plan, cmd_rebuild
from application.world_schedule import cmd_queue, cmd_schedule
from application.world_tick import cmd_world_tick

__all__ = [
    "cmd_arc",
    "cmd_check_prose",
    "cmd_clock",
    "cmd_commit",
    "cmd_correct",
    "cmd_faction",
    "cmd_plan",
    "cmd_prepare",
    "cmd_progress",
    "cmd_quest",
    "cmd_queue",
    "cmd_rebuild",
    "cmd_review",
    "cmd_schedule",
    "cmd_world_tick",
    "find_campaign",
    "init_campaign_from_templates",
    "upsert_npc_to_md",
    "validate_commit_entities",
]
