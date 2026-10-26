"""Testes unitários dos contratos e modelos puros de contexto."""

from __future__ import annotations

import unittest
from contracts.context import (
    ContextItem,
    ContextLimits,
    ContextOmission,
    ContextRequest,
    ContextScene,
    ContextSection,
    HolderRef,
    TurnContext,
)
from resources.context.model import Availability, ContextKind, ContextLayer
from resources.context.relevance import score_npc, score_faction, select


class FakeContextStateView:
    def __init__(self, clocks=(), quests=(), arc=None, recent=()):
        self._clocks = clocks
        self._quests = quests
        self._arc = arc or {}
        self._recent = recent
        self.last_seq = 10
        self.stale = False

    def npcs(self):
        return {}

    def factions(self):
        return {}

    def knowledge(self):
        return []

    def recent_events(self, limit: int = 50):
        return self._recent[:limit]

    def quests(self):
        return self._quests

    def clocks(self):
        return self._clocks

    def arc(self):
        return self._arc


class ContextFoundationsTest(unittest.TestCase):
    def test_dataclass_validations(self):
        h = HolderRef("protagonist", "aemon")
        self.assertEqual(h.kind, "protagonist")
        self.assertEqual(h.id, "aemon")

        with self.assertRaises(ValueError):
            HolderRef("", "aemon")

        scene = ContextScene(
            location="Castelo Negro",
            present=("aemon", "jeor"),
            game_time="01/10/300 10:00",
            game_time_sort=1000,
        )
        self.assertEqual(scene.location, "Castelo Negro")

        item = ContextItem(
            kind="npc",
            id="jeor",
            label="Jeor Mormont",
            layer="causal",
            score=1000,
            reasons=("presenca",),
        )
        self.assertEqual(item.score, 1000)
        self.assertEqual(item.availability, "known")

    def test_relevance_deterministic_selection(self):
        limits = ContextLimits(max_npcs=2, min_relevance=200)
        items = [
            ContextItem(kind="npc", id="c", label="NPC C", layer="causal", score=300),
            ContextItem(kind="npc", id="a", label="NPC A", layer="causal", score=500),
            ContextItem(kind="npc", id="b", label="NPC B", layer="causal", score=500),
            ContextItem(kind="npc", id="d", label="NPC D", layer="causal", score=100),  # below min
        ]
        selected = select(items, limits)
        # score 500 for A and B -> tie-breaker by (kind, id): 'a' then 'b'
        # max_npcs is 2, so only 'a' and 'b' selected
        self.assertEqual([i.id for i in selected], ["a", "b"])

    def test_score_npc_distant_antagonist_with_plan(self):
        req = ContextRequest(
            campaign_id="test",
            mode="gm",
            action="Aemon investiga ameaças",
            scene=ContextScene("Muralha", ("aemon",), "01/10", 1),
            viewer=HolderRef("human", "gm"),
            audience=HolderRef("universe", "gm"),
            purpose="arbitration",
        )
        state = FakeContextStateView()
        npc_data = {
            "id": "malakor",
            "name": "Malakor",
            "location": "Porto Real",
            "plan": {"status": "active", "imminent": True},
            "relational_vector": {"rivalry": 2},
        }
        score, reasons = score_npc(npc_data, req, state)
        # plano_iminente (+300), ameaca (+200), fora_de_cena (-100) = 400
        self.assertEqual(score, 400)
        self.assertIn("plano_iminente", reasons)
        self.assertIn("ameaca", reasons)
        self.assertIn("fora_de_cena", reasons)


if __name__ == "__main__":
    unittest.main()
