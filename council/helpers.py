"""council.helpers: Fachada de compatibilidade para persistência, tempo e campanhas.

A implementação concreta foi refatorada em R0d:
- adapters.persistence.files: atomic_write_text, campaign_lock
- temporal.calendar: advance_time_str, parse_time_increment, calendários
- campaign.locator: find_campaign, parse_regras_manifest, rulesets, validate_campaign_id
- campaign.templates: init_campaign_from_templates
"""

from __future__ import annotations

import os
from pathlib import Path

from adapters.persistence import atomic_write_text, campaign_lock
from campaign import (
    BASE_DIR,
    CAMPAIGN_DIRS,
    CURRENT_SCHEMA_VERSION,
    DEFAULT_RULESET,
    TEMPLATES_DIR,
    find_campaign,
    get_available_rulesets,
    get_campaign_overrides,
    get_campaign_system,
    init_campaign_from_templates,
    load_ruleset,
    parse_regras_manifest,
    validate_campaign_id,
)
from temporal import (
    MONTHS_MAP,
    MONTHS_PT,
    advance_time_str,
    parse_time_increment,
)
from temporal.calendar import _normalize_calendar

AIMEMORY_BIN = os.path.expandvars(r"%LOCALAPPDATA%\ai-memory\ai-memory.exe")

__all__ = [
    "AIMEMORY_BIN",
    "BASE_DIR",
    "CAMPAIGN_DIRS",
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_RULESET",
    "MONTHS_MAP",
    "MONTHS_PT",
    "TEMPLATES_DIR",
    "_normalize_calendar",
    "advance_time_str",
    "atomic_write_text",
    "campaign_lock",
    "find_campaign",
    "get_available_rulesets",
    "get_campaign_overrides",
    "get_campaign_system",
    "init_campaign_from_templates",
    "load_ruleset",
    "parse_regras_manifest",
    "parse_time_increment",
    "validate_campaign_id",
]
