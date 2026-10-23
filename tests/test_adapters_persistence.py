"""Testes unitários para adapters/persistence/files.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.persistence.files import atomic_write_text, campaign_lock


class AdaptersPersistenceTests(unittest.TestCase):
    def test_atomic_write_creates_and_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "sub" / "file.txt"
            atomic_write_text(target, "primeiro")
            self.assertEqual(target.read_text(encoding="utf-8"), "primeiro")

            atomic_write_text(target, "segundo")
            self.assertEqual(target.read_text(encoding="utf-8"), "segundo")

    def test_campaign_lock_acquisition_and_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            camp_dir = Path(tmp_dir)
            with campaign_lock(camp_dir, timeout=1.0):
                self.assertTrue((camp_dir / ".campaign.lock").exists())

            # Pode ser adquirido novamente após sair do bloco
            with campaign_lock(camp_dir, timeout=1.0):
                pass


if __name__ == "__main__":
    unittest.main()
