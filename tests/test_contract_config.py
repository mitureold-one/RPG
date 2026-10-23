"""Contrato da configuração de composição da campanha."""

from __future__ import annotations

import unittest

from contracts.config import CampaignConfig


class CampaignConfigContractTests(unittest.TestCase):
    def test_minimal_config(self) -> None:
        config = CampaignConfig(campaign_id="valiria", system="d20_3gates")
        self.assertEqual(config.plugins, {})
        self.assertEqual(config.calendar, {})
        self.assertEqual(config.config_version, 1)

    def test_plugins_and_calendar_are_copied(self) -> None:
        plugins = {"resolution": "d20_3gates"}
        calendar = {"months": ["Ventania"]}
        config = CampaignConfig(
            campaign_id="valiria",
            system="d20_3gates",
            plugins=plugins,
            calendar=calendar,
        )
        plugins["resolution"] = "outro"
        calendar["months"].append("Geada")

        self.assertEqual(config.plugins, {"resolution": "d20_3gates"})
        self.assertEqual(config.calendar, {"months": ["Ventania"]})

    def test_identity_is_required(self) -> None:
        with self.assertRaises(ValueError):
            CampaignConfig(campaign_id="", system="d20_3gates")
        with self.assertRaises(ValueError):
            CampaignConfig(campaign_id="valiria", system="  ")

    def test_plugin_names_must_be_text(self) -> None:
        with self.assertRaises(ValueError):
            CampaignConfig(campaign_id="c", system="s", plugins={"resolution": 1})  # type: ignore[dict-item]

    def test_calendar_must_be_json(self) -> None:
        with self.assertRaises(ValueError):
            CampaignConfig(campaign_id="c", system="s", calendar={"bad": {1, 2}})

    def test_config_version_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            CampaignConfig(campaign_id="c", system="s", config_version=0)


if __name__ == "__main__":
    unittest.main()
