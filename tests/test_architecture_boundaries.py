"""Fronteira arquitetural de ``contracts/`` e ``kernel/``.

Nenhum dos dois pode importar camadas de domínio, adaptadores ou CLI, e o
kernel não faz I/O. O teste é estrutural (AST), não depende de execução.
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


if __name__ == "__main__":
    unittest.main()
