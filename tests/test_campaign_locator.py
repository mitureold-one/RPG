"""Testes unitários para campaign/locator.py e campaign/templates.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from campaign.locator import (
    CURRENT_SCHEMA_VERSION,
    DEFAULT_RULESET,
    find_campaign,
    get_available_rulesets,
    get_campaign_overrides,
    get_campaign_system,
    load_ruleset,
    parse_regras_manifest,
)


class CampaignLocatorTests(unittest.TestCase):
    def test_default_ruleset_and_available(self) -> None:
        self.assertEqual(DEFAULT_RULESET, "d20_3gates")
        available = get_available_rulesets()
        self.assertIn("d20_3gates", available)

    def test_load_ruleset(self) -> None:
        mod = load_ruleset("d20_3gates")
        self.assertIsNotNone(mod)

        with self.assertRaises(ValueError):
            load_ruleset("ruleset_que_nao_existe_123")

    def test_parse_regras_manifest_empty_or_nonexistent(self) -> None:
        res = parse_regras_manifest(Path("caminho_inexistente_xyz.md"))
        self.assertEqual(res["system"], DEFAULT_RULESET)
        self.assertEqual(res["overrides"], [])
        self.assertEqual(res["calendar"], {})


if __name__ == "__main__":
    unittest.main()
