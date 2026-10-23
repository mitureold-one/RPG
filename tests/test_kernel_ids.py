"""Contrato dos identificadores de evento."""

from __future__ import annotations

import re
import unittest
from concurrent.futures import ThreadPoolExecutor

from kernel.ids import new_event_id

EVENT_ID_RE = re.compile(r"^evt_[0-9A-HJKMNP-TV-Z]{26}$")


class EventIdContractTests(unittest.TestCase):
    def test_format(self) -> None:
        event_id = new_event_id()
        self.assertRegex(event_id, EVENT_ID_RE)
        self.assertEqual(len(event_id), 30)

    def test_uniqueness(self) -> None:
        ids = [new_event_id() for _ in range(2000)]
        self.assertEqual(len(set(ids)), len(ids))

    def test_lexicographic_order_follows_creation(self) -> None:
        ids = [new_event_id() for _ in range(2000)]
        self.assertEqual(ids, sorted(ids))

    def test_generation_is_thread_safe(self) -> None:
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(lambda _: new_event_id(), range(800)))
        self.assertEqual(len(set(ids)), len(ids))
        for event_id in ids:
            self.assertRegex(event_id, EVENT_ID_RE)


if __name__ == "__main__":
    unittest.main()
