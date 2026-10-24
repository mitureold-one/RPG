"""tests/test_prose_and_queue.py: Testes de ProseStore e SkeletonQueue."""

import tempfile
import unittest
from pathlib import Path

from adapters.persistence.skeleton_queue import SkeletonQueue
from application.prose_store import ProseStore


class TestProseAndQueue(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.camp_dir = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_prose_store_lifecycle_and_verification(self):
        store = ProseStore(self.camp_dir)
        content = "A lâmina de Valerius cortou o ar gélido da cripta."
        rel_path, sha_hash, length = store.store_turn_prose(1, content)

        self.assertTrue(rel_path.startswith("artifacts/prose/turn_000001-"))
        self.assertTrue(rel_path.endswith(".md"))
        self.assertTrue(sha_hash.startswith("sha256:"))
        self.assertGreater(length, 0)

        # Verification passes
        self.assertTrue(store.verify_prose(rel_path, sha_hash))

        # Tampering fails verification
        target = self.camp_dir / rel_path
        target.write_text("Texto adulterado", encoding="utf-8")
        self.assertFalse(store.verify_prose(rel_path, sha_hash))

        # Nonexistent file returns False
        self.assertFalse(store.verify_prose("artifacts/prose/ghost.md", sha_hash))

    def test_skeleton_queue_append_only_transitions(self):
        queue = SkeletonQueue(self.camp_dir)
        self.assertEqual(queue.list_pending(), [])

        # Enqueue task 1
        t1 = queue.enqueue("task_01", "sync_daemon", {"step": "pull"})
        self.assertEqual(t1["status"], "pending")

        # Enqueue task 2
        t2 = queue.enqueue("task_02", "indexing", {"rebuild": True})
        self.assertEqual(len(queue.list_pending()), 2)

        # Complete task 1
        queue.complete("task_01", {"result": "success"})
        pending = queue.list_pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["task_id"], "task_02")

        # Task 1 status is done
        status_1 = queue.get_task("task_01")
        self.assertIsNotNone(status_1)
        self.assertEqual(status_1["status"], "done")
        self.assertEqual(status_1["result"], {"result": "success"})

        # Fail task 2
        queue.fail("task_02", "Network error")
        self.assertEqual(queue.list_pending(), [])

        status_2 = queue.get_task("task_02")
        self.assertIsNotNone(status_2)
        self.assertEqual(status_2["status"], "failed")
        self.assertEqual(status_2["error"], "Network error")

        # Verify that queue.jsonl contains 4 distinct append-only lines
        lines = (self.camp_dir / "queue.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 4)


if __name__ == "__main__":
    unittest.main()
