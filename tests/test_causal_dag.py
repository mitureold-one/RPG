"""tests/test_causal_dag.py: Testes do grafo de dependências causal e resolução intra-lote (C2)."""

import shutil
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from contract_support import make_draft
from kernel.dag import DependencyGraph
from kernel.errors import (
    DependencyCycleError,
    DependencyDepthError,
    DependencyError,
)


class CausalDAGTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = Path(".tmp/test_scratch/test_dag")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.dag = DependencyGraph(max_depth=64)
        self.store = JsonlEventStore(base_dir=self.test_dir, dep_graph=self.dag, catalog=None)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_intra_batch_dependencies_accepted(self) -> None:
        # Critério C2: D2 depende de D1 dentro do mesmo append
        # Para referenciar dentro do lote antes de ter o ID gerado pelo store,
        # podemos testar via DependencyGraph diretamente com provisional_ids
        prov_ids = ["evt_01J00000000000000000000001", "evt_01J00000000000000000000002", "evt_01J00000000000000000000003"]
        drafts = [
            make_draft(payload={"step": 1}, meta={"dependencies": []}),
            make_draft(payload={"step": 2}, meta={"dependencies": [prov_ids[0]]}),
            make_draft(payload={"step": 3}, meta={"dependencies": [prov_ids[1]]}),
        ]

        self.dag.validate_batch(drafts, prov_ids, set())
        # Validação passou sem erro!

    def test_intra_batch_forward_dependency_rejected(self) -> None:
        prov_ids = ["evt_01J00000000000000000000001", "evt_01J00000000000000000000002"]
        # D1 tenta referenciar D2 que vem depois no lote
        drafts = [
            make_draft(payload={"step": 1}, meta={"dependencies": [prov_ids[1]]}),
            make_draft(payload={"step": 2}, meta={"dependencies": []}),
        ]
        with self.assertRaises(DependencyError):
            self.dag.validate_batch(drafts, prov_ids, set())

    def test_self_dependency_raises_cycle_error(self) -> None:
        prov_ids = ["evt_01J00000000000000000000001"]
        drafts = [
            make_draft(payload={"step": 1}, meta={"dependencies": [prov_ids[0]]}),
        ]
        with self.assertRaises(DependencyCycleError):
            self.dag.validate_batch(drafts, prov_ids, set())

    def test_unknown_dependency_rejected(self) -> None:
        prov_ids = ["evt_01J00000000000000000000001"]
        drafts = [
            make_draft(payload={"step": 1}, meta={"dependencies": ["evt_INEXISTENTE00000000000000"]}),
        ]
        with self.assertRaises(DependencyError):
            self.dag.validate_batch(drafts, prov_ids, set())

    def test_historical_dependency_integration_in_store(self) -> None:
        # 1. Grava evento 1
        res1 = self.store.append("camp_dag", [make_draft(payload={"step": 1})])
        parent_id = res1.events[0].event_id

        # 2. Grava evento 2 dependendo do evento 1 persistido
        res2 = self.store.append("camp_dag", [make_draft(payload={"step": 2}, meta={"dependencies": [parent_id]})])
        self.assertEqual(res2.events[0].meta["dependencies"], [parent_id])

        # 3. Tenta gravar dependendo de ID inexistente via store
        with self.assertRaises(DependencyError):
            self.store.append("camp_dag", [make_draft(payload={"step": 3}, meta={"dependencies": ["evt_FANTASMA0000000000000000"]})])

    def test_max_depth_exceeded_raises_depth_error(self) -> None:
        shallow_dag = DependencyGraph(max_depth=3)
        # Monta cadeia de 4 níveis: 1 -> 2 -> 3 -> 4
        prov_ids = [f"evt_{i:026d}" for i in range(1, 5)]
        drafts = [
            make_draft(meta={"dependencies": []}),
            make_draft(meta={"dependencies": [prov_ids[0]]}),
            make_draft(meta={"dependencies": [prov_ids[1]]}),
            make_draft(meta={"dependencies": [prov_ids[2]]}),
        ]
        with self.assertRaises(DependencyDepthError):
            shallow_dag.validate_batch(drafts, prov_ids, set())


if __name__ == "__main__":
    unittest.main()
