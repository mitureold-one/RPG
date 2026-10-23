"""Suíte de contrato do EventStore, exercitada contra o FakeEventStore."""

from __future__ import annotations

import unittest

from contract_support import EventStoreContract, FakeEventStore, make_draft


class FakeEventStoreContractTests(EventStoreContract, unittest.TestCase):
    def make_store(self) -> FakeEventStore:
        return FakeEventStore()


class FakeEventStoreFailureTests(unittest.TestCase):
    """Falha injetada é específica do fake e não faz parte da porta."""

    def test_failed_batch_persists_nothing_and_does_not_consume_seq(self) -> None:
        store = FakeEventStore()
        store.fail_next_append()

        with self.assertRaises(RuntimeError):
            store.append("camp", [make_draft(), make_draft()])

        self.assertEqual(store.last_seq("camp"), 0)
        self.assertEqual(tuple(store.read("camp")), ())

        after = store.append("camp", [make_draft()])
        self.assertEqual(after.events[0].seq, 1)


if __name__ == "__main__":
    unittest.main()
