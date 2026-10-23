"""Testes para o composition root bootstrap.py."""

from __future__ import annotations

import unittest

from bootstrap import build_runtime
from contracts.config import CampaignConfig
from kernel.registry import Registry


class BootstrapTests(unittest.TestCase):
    def test_build_runtime_minimal(self) -> None:
        runtime = build_runtime("imperio_valiria")
        self.assertEqual(runtime.campaign_id, "imperio_valiria")
        self.assertEqual(runtime.config.campaign_id, "imperio_valiria")
        self.assertEqual(runtime.config.system, "default")
        self.assertTrue(runtime.registry.is_frozen)

    def test_build_runtime_with_custom_config(self) -> None:
        config = CampaignConfig(campaign_id="imperio_valiria", system="d20_3gates")
        runtime = build_runtime("imperio_valiria", config=config)
        self.assertEqual(runtime.config.system, "d20_3gates")
        self.assertTrue(runtime.registry.is_frozen)

    def test_build_runtime_with_custom_registry(self) -> None:
        registry = Registry()
        registry.register("clock", "test", object())
        self.assertFalse(registry.is_frozen)

        runtime = build_runtime("test_camp", registry=registry)
        self.assertTrue(runtime.registry.is_frozen)
        self.assertTrue(runtime.has_service("clock", "test"))

    def test_build_runtime_invalid_campaign_id(self) -> None:
        with self.assertRaises(ValueError):
            build_runtime("")
        with self.assertRaises(ValueError):
            build_runtime("   ")


if __name__ == "__main__":
    unittest.main()
