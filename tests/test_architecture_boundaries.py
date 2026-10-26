"""Fronteira arquitetural de ``contracts/``, ``kernel/``, ``application/``, etc.

Verifica restrições de importação entre camadas e limites de tamanho por arquivo.
O teste é estrutural (AST), não depende de execução.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOUNDARY_PACKAGES = ("contracts", "kernel")
FORBIDDEN_IMPORTS = {
    "adapters",
    "council",
    "interfaces",
    "lazy_turn",
    "resources",
    "rulesets",
    "sync_daemon",
}
FORBIDDEN_IO_IMPORTS = {
    "http",
    "io",
    "os",
    "pathlib",
    "shutil",
    "socket",
    "subprocess",
    "urllib",
}


def _imported_roots(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.append(node.module.split(".")[0])
    return roots


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_no_forbidden_layer_imports(self) -> None:
        for package in BOUNDARY_PACKAGES:
            for path in (ROOT / package).rglob("*.py"):
                for module in _imported_roots(path):
                    self.assertNotIn(
                        module,
                        FORBIDDEN_IMPORTS,
                        f"{path.relative_to(ROOT)} importa a camada proibida '{module}'",
                    )

    def test_no_io_imports_or_open_calls(self) -> None:
        for package in BOUNDARY_PACKAGES:
            for path in (ROOT / package).rglob("*.py"):
                for module in _imported_roots(path):
                    self.assertNotIn(
                        module,
                        FORBIDDEN_IO_IMPORTS,
                        f"{path.relative_to(ROOT)} importa I/O proibido '{module}'",
                    )
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "open"
                    ):
                        self.fail(f"{path.relative_to(ROOT)} chama open() no kernel")

    def test_application_does_not_import_cli(self) -> None:
        for path in (ROOT / "application").rglob("*.py"):
            for module in _imported_roots(path):
                self.assertNotIn(
                    module,
                    {"interfaces", "lazy_turn"},
                    f"{path.relative_to(ROOT)} importa a camada de entrada '{module}'",
                )

    def test_temporal_has_no_io_and_no_domain_imports(self) -> None:
        for path in (ROOT / "temporal").rglob("*.py"):
            for module in _imported_roots(path):
                self.assertNotIn(
                    module,
                    {"council", "interfaces", "lazy_turn", "rulesets", "adapters", "os", "subprocess", "socket"},
                    f"{path.relative_to(ROOT)} importa camada proibida '{module}'",
                )

    def test_adapters_persistence_has_no_domain_imports(self) -> None:
        for path in (ROOT / "adapters" / "persistence").rglob("*.py"):
            for module in _imported_roots(path):
                self.assertNotIn(
                    module,
                    {"council", "interfaces", "lazy_turn", "rulesets", "application"},
                    f"{path.relative_to(ROOT)} importa módulo de domínio proibido '{module}'",
                )

    def test_council_does_not_import_application_or_cli(self) -> None:
        for path in (ROOT / "council").rglob("*.py"):
            for module in _imported_roots(path):
                self.assertNotIn(
                    module,
                    {"application", "interfaces", "lazy_turn"},
                    f"{path.relative_to(ROOT)} importa camada superior proibida '{module}'",
                )

    def test_plugins_have_no_io_and_are_pure(self) -> None:
        for path in (ROOT / "plugins").rglob("*.py"):
            for module in _imported_roots(path):
                self.assertNotIn(
                    module,
                    FORBIDDEN_IO_IMPORTS | {"lazy_turn", "interfaces"},
                    f"{path.relative_to(ROOT)} importa camada/módulo proibido '{module}'",
                )
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "open"
                ):
                    self.fail(f"{path.relative_to(ROOT)} chama open() em plugin puro")

    def test_entry_point_and_file_size_limits(self) -> None:
        entry = len((ROOT / "lazy_turn.py").read_text(encoding="utf-8").splitlines())
        self.assertLess(entry, 200, "lazy_turn.py deve ter menos de 200 linhas")

        helpers_len = len((ROOT / "council" / "helpers.py").read_text(encoding="utf-8").splitlines())
        self.assertLess(helpers_len, 100, f"council/helpers.py deve ter menos de 100 linhas (tem {helpers_len})")

        ssot_len = len((ROOT / "council" / "ssot.py").read_text(encoding="utf-8").splitlines())
        self.assertLess(ssot_len, 100, f"council/ssot.py deve ter menos de 100 linhas (tem {ssot_len})")

        for facade_name in ("quests.py", "narrator.py", "factions.py"):
            facade_len = len((ROOT / "council" / facade_name).read_text(encoding="utf-8").splitlines())
            self.assertLess(facade_len, 100, f"council/{facade_name} deve ser fachada reexportadora com menos de 100 linhas (tem {facade_len})")

        for r_file in (ROOT / "resources").rglob("*.py"):
            r_len = len(r_file.read_text(encoding="utf-8").splitlines())
            self.assertLess(r_len, 300, f"{r_file.relative_to(ROOT)} deve ter menos de 300 linhas (tem {r_len})")

        for p_file in (ROOT / "plugins").rglob("*.py"):
            p_len = len(p_file.read_text(encoding="utf-8").splitlines())
            self.assertLess(p_len, 300, f"{p_file.relative_to(ROOT)} deve ter menos de 300 linhas (tem {p_len})")

        strict_300_targets = (
            ROOT / "application" / "arbitration.py",
            ROOT / "application" / "commit.py",
            ROOT / "application" / "commit_stage.py",
            ROOT / "application" / "correction.py",
            ROOT / "application" / "context" / "agents.py",
            ROOT / "application" / "context" / "assembler.py",
            ROOT / "application" / "context" / "knowledge.py",
            ROOT / "application" / "context" / "providers.py",
            ROOT / "application" / "context" / "query.py",
            ROOT / "application" / "context" / "scene.py",
            ROOT / "application" / "context" / "state.py",
            ROOT / "application" / "prepare.py",
            ROOT / "application" / "projectors" / "journal.py",
            ROOT / "application" / "projectors" / "sheet.py",
            ROOT / "application" / "projectors" / "npc.py",
            ROOT / "application" / "projectors" / "faction.py",
            ROOT / "application" / "projectors" / "state.py",
            ROOT / "contracts" / "catalog.py",
            ROOT / "adapters" / "persistence" / "event_store.py",
            ROOT / "adapters" / "persistence" / "batch_io.py",
            ROOT / "adapters" / "persistence" / "segment_io.py",
            ROOT / "council" / "reviewer.py",
            ROOT / "council" / "prose_linter.py",
            ROOT / "council" / "reviewer_checks.py",
        )
        for path in strict_300_targets:
            size = len(path.read_text(encoding="utf-8").splitlines())
            self.assertLess(size, 300, f"{path.relative_to(ROOT)} deve ter menos de 300 linhas (tem {size})")

        for package in ("application", "interfaces", "contracts", "kernel", "adapters", "temporal", "campaign", "resources", "plugins"):
            for path in (ROOT / package).rglob("*.py"):
                size = len(path.read_text(encoding="utf-8").splitlines())
                self.assertLess(size, 600, f"{path.relative_to(ROOT)} tem {size} linhas (limite de falha: 600)")


if __name__ == "__main__":
    unittest.main()
