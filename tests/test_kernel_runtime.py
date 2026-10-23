"""Testes de contrato para kernel/runtime.py."""

from __future__ import annotations

import unittest

from contracts.config import CampaignConfig
from kernel.errors import UnknownPortError
from kernel.registry import Registry
from kernel.runtime import Runtime


class DummyEngine:
    def __init__(self, tag: str) -> None:
        self.tag = tag


class KernelRuntimeTests(unittest.TestCase):
    def test_runtime_creation_and_immutability(self) -> None:
        config = CampaignConfig(campaign_id="valiria", system="d20_3gates")
        registry = Registry()
        svc = DummyEngine("d20")
        registry.register("resolution", "d20_3gates", svc)

        runtime = Runtime(campaign_id="valiria", config=config, registry=registry)
        self.assertEqual(runtime.campaign_id, "valiria")
        self.assertEqual(runtime.config.system, "d20_3gates")
        self.assertTrue(runtime.registry.is_frozen)

        # Dataclass frozen
        with self.assertRaises(Exception):
            runtime.campaign_id = "outro"  # type: ignore[misc]

    def test_campaign_id_mismatch_raises(self) -> None:
        config = CampaignConfig(campaign_id="valiria", system="d20_3gates")
        registry = Registry()
        with self.assertRaises(ValueError):
            Runtime(campaign_id="diferente", config=config, registry=registry)

    def test_unregistered_configured_plugin_raises(self) -> None:
        config = CampaignConfig(
            campaign_id="valiria",
            system="d20_3gates",
            plugins={"resolution": "missing_plugin"},
        )
        registry = Registry()
        with self.assertRaises(UnknownPortError):
            Runtime(campaign_id="valiria", config=config, registry=registry)

    def test_service_lookup_by_exact_name(self) -> None:
        config = CampaignConfig(campaign_id="valiria", system="d20_3gates")
        registry = Registry()
        svc1 = DummyEngine("engine1")
        svc2 = DummyEngine("engine2")
        registry.register("engine", "v1", svc1)
        registry.register("engine", "v2", svc2)

        runtime = Runtime(campaign_id="valiria", config=config, registry=registry)
        self.assertIs(runtime.service("engine", "v1"), svc1)
        self.assertIs(runtime.service("engine", "v2"), svc2)
        self.assertEqual(runtime.services("engine"), [svc1, svc2])
        self.assertTrue(runtime.has_service("engine", "v1"))
        self.assertFalse(runtime.has_service("engine", "v3"))

    def test_service_lookup_by_configuration(self) -> None:
        config = CampaignConfig(
            campaign_id="valiria",
            system="d20_3gates",
            plugins={"resolution": "d20_v2"},
        )
        registry = Registry()
        svc1 = DummyEngine("v1")
        svc2 = DummyEngine("v2")
        registry.register("resolution", "d20_v1", svc1)
        registry.register("resolution", "d20_v2", svc2)

        runtime = Runtime(campaign_id="valiria", config=config, registry=registry)
        # Without specifying name in service(), it resolves to configured plugin d20_v2
        self.assertIs(runtime.service("resolution"), svc2)

    def test_service_lookup_single_registered_default(self) -> None:
        config = CampaignConfig(campaign_id="valiria", system="d20_3gates")
        registry = Registry()
        svc = DummyEngine("only_one")
        registry.register("clock", "realtime", svc)

        runtime = Runtime(campaign_id="valiria", config=config, registry=registry)
        # Unambiguous: single registered service for port resolves directly
        self.assertIs(runtime.service("clock"), svc)

    def test_service_lookup_ambiguous_raises(self) -> None:
        config = CampaignConfig(campaign_id="valiria", system="d20_3gates")
        registry = Registry()
        registry.register("engine", "v1", DummyEngine("1"))
        registry.register("engine", "v2", DummyEngine("2"))

        runtime = Runtime(campaign_id="valiria", config=config, registry=registry)
        with self.assertRaises(UnknownPortError):
            runtime.service("engine")


if __name__ == "__main__":
    unittest.main()
