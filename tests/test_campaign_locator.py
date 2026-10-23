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
    validate_campaign_id,
)
from campaign import templates
from campaign.templates import init_campaign_from_templates
import council.helpers as helpers


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

    def test_init_campaign_from_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            orig = list(helpers.CAMPAIGN_DIRS)
            try:
                helpers.CAMPAIGN_DIRS = [Path(tmp_dir)]
                res = init_campaign_from_templates("nova_campanha", title="Nova Campanha")
                self.assertEqual(res["status"], "ok")
                self.assertEqual(len(res["created_files"]), 5)

                # Verifica que a nova campanha é encontrada e válida
                info = find_campaign("nova_campanha")
                self.assertIsNotNone(info)
                self.assertEqual(info["id"], "nova_campanha")
                self.assertEqual(info["schema_version"], CURRENT_SCHEMA_VERSION)
                self.assertEqual(info["system"], DEFAULT_RULESET)
            finally:
                helpers.CAMPAIGN_DIRS = orig

    def test_campaign_id_validation_and_traversal_rejection(self) -> None:
        # IDs válidos
        self.assertEqual(validate_campaign_id("campanha_1"), "campanha_1")
        self.assertEqual(validate_campaign_id("solo-shadows"), "solo-shadows")
        self.assertEqual(validate_campaign_id("_test_camp"), "_test_camp")

        # IDs inválidos / directory traversal
        invalid_ids = ["../outside", "..", "foo/bar", "foo\\bar", "C:\\win", "has space", "inv@lid"]
        for cid in invalid_ids:
            with self.assertRaises(ValueError, msg=f"Deveria rejeitar '{cid}'"):
                validate_campaign_id(cid)

            with self.assertRaises(ValueError, msg=f"find_campaign deveria falhar para '{cid}'"):
                find_campaign(cid)

            res = init_campaign_from_templates(cid)
            self.assertIn("error", res, f"init_campaign_from_templates deveria retornar erro para '{cid}'")

    def test_init_campaign_all_or_nothing_on_missing_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_camp_dir, tempfile.TemporaryDirectory() as tmp_tmpl_dir:
            orig_dirs = list(helpers.CAMPAIGN_DIRS)
            orig_tmpl = templates.TEMPLATES_DIR
            try:
                helpers.CAMPAIGN_DIRS = [Path(tmp_camp_dir)]
                templates.TEMPLATES_DIR = Path(tmp_tmpl_dir)

                # Cria apenas 1 dos 5 templates
                (Path(tmp_tmpl_dir) / "ficha.template.md").write_text("ficha template", encoding="utf-8")

                res = init_campaign_from_templates("campanha_incompleta")
                self.assertIn("error", res)
                self.assertIn("Templates ausentes", res["error"])

                # Garante que nenhum diretório foi criado
                target = Path(tmp_camp_dir) / "campanha_incompleta"
                self.assertFalse(target.exists(), "Diretório não deve ser criado se faltarem templates")
            finally:
                helpers.CAMPAIGN_DIRS = orig_dirs
                templates.TEMPLATES_DIR = orig_tmpl


if __name__ == "__main__":
    unittest.main()
