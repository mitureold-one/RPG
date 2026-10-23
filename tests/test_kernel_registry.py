"""Testes de contrato para kernel/registry.py (PluginManifest e Registry)."""

from __future__ import annotations

import unittest

from kernel.errors import (
    ConfigurationError,
    DuplicateRegistrationError,
    MissingRequirementError,
    RegistryFrozenError,
    UnknownPortError,
)
from kernel.registry import PluginManifest, Registry


class DummyService:
    def __init__(self, val: str) -> None:
        self.val = val


class KernelRegistryTests(unittest.TestCase):
    def test_plugin_manifest_validation(self) -> None:
        manifest = PluginManifest(
            name="d20_3gates",
            version="1.0.0",
            api_version=1,
            provides=("resolution",),
            requires=(),
            deterministic=True,
            config_schema={"type": "object"},
        )
        self.assertEqual(manifest.name, "d20_3gates")
        self.assertEqual(manifest.provides, ("resolution",))
        self.assertEqual(manifest.config_schema, {"type": "object"})

        # Invalid name/version
        with self.assertRaises(ValueError):
            PluginManifest(name="", version="1.0", api_version=1, provides=("res",))
        with self.assertRaises(ValueError):
            PluginManifest(name="p", version="", api_version=1, provides=("res",))

        # Invalid api_version
        with self.assertRaises(ValueError):
            PluginManifest(name="p", version="1.0", api_version=0, provides=("res",))

        # Invalid provides
        with self.assertRaises(ValueError):
            PluginManifest(name="p", version="1.0", api_version=1, provides=())

    def test_register_and_get(self) -> None:
        registry = Registry()
        svc = DummyService("engine1")
        registry.register("resolution", "d20", svc)

        self.assertTrue(registry.has("resolution", "d20"))
        self.assertFalse(registry.has("resolution", "other"))
        self.assertIs(registry.get("resolution", "d20"), svc)
        self.assertEqual(registry.all("resolution"), [svc])
        self.assertEqual(registry.all_names("resolution"), ["d20"])
        self.assertEqual(registry.points(), {"resolution"})

    def test_duplicate_registration_raises(self) -> None:
        registry = Registry()
        registry.register("resolution", "d20", DummyService("a"))
        with self.assertRaises(DuplicateRegistrationError):
            registry.register("resolution", "d20", DummyService("b"))

    def test_unknown_port_raises(self) -> None:
        registry = Registry()
        with self.assertRaises(UnknownPortError):
            registry.get("nonexistent", "svc")
        with self.assertRaises(UnknownPortError):
            registry.get_manifest("nonexistent", "svc")

    def test_manifest_validation_on_register(self) -> None:
        registry = Registry()
        # Name mismatch
        manifest_wrong_name = PluginManifest(
            name="wrong_name",
            version="1.0",
            api_version=1,
            provides=("resolution",),
        )
        with self.assertRaises(ConfigurationError):
            registry.register("resolution", "d20", DummyService("a"), manifest=manifest_wrong_name)

        # Port mismatch
        manifest_wrong_port = PluginManifest(
            name="d20",
            version="1.0",
            api_version=1,
            provides=("other_port",),
        )
        with self.assertRaises(ConfigurationError):
            registry.register("resolution", "d20", DummyService("a"), manifest=manifest_wrong_port)

        # Matching manifest
        valid_manifest = PluginManifest(
            name="d20",
            version="1.0",
            api_version=1,
            provides=("resolution",),
        )
        registry.register("resolution", "d20", DummyService("a"), manifest=valid_manifest)
        self.assertIs(registry.get_manifest("resolution", "d20"), valid_manifest)

    def test_freeze_prevents_registration(self) -> None:
        registry = Registry()
        registry.register("p", "a", DummyService("a"))
        self.assertFalse(registry.is_frozen)
        registry.freeze()
        self.assertTrue(registry.is_frozen)

        with self.assertRaises(RegistryFrozenError):
            registry.register("p", "b", DummyService("b"))

    def test_freeze_validates_requirements(self) -> None:
        registry = Registry()
        manifest_with_req = PluginManifest(
            name="d20",
            version="1.0",
            api_version=1,
            provides=("resolution",),
            requires=("event_store",),
        )
        registry.register("resolution", "d20", DummyService("a"), manifest=manifest_with_req)

        # Freezing without satisfying event_store requirement
        with self.assertRaises(MissingRequirementError):
            registry.freeze()

        # Satisfy requirement and freeze
        registry.register("event_store", "fake", DummyService("store"))
        registry.freeze()
        self.assertTrue(registry.is_frozen)


if __name__ == "__main__":
    unittest.main()
