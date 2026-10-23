"""Módulo de campanhas do RPGPRO: localização, manifesto de regras e templates."""

from campaign.locator import (
    BASE_DIR,
    CAMPAIGN_DIRS,
    CURRENT_SCHEMA_VERSION,
    DEFAULT_RULESET,
    find_campaign,
    get_available_rulesets,
    get_campaign_overrides,
    get_campaign_system,
    load_ruleset,
    parse_regras_manifest,
    validate_campaign_id,
)
from campaign.templates import (
    TEMPLATES_DIR,
    init_campaign_from_templates,
)

__all__ = [
    "BASE_DIR",
    "CAMPAIGN_DIRS",
    "CURRENT_SCHEMA_VERSION",
    "DEFAULT_RULESET",
    "TEMPLATES_DIR",
    "find_campaign",
    "get_available_rulesets",
    "get_campaign_overrides",
    "get_campaign_system",
    "init_campaign_from_templates",
    "load_ruleset",
    "parse_regras_manifest",
    "validate_campaign_id",
]
