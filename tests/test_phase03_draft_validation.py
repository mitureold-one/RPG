"""tests/test_phase03_draft_validation.py: Validação de Fábricas de Drafts contra o Catálogo v1 (T007)."""

from __future__ import annotations

import unittest
from adapters.persistence.batch_io import validate_draft_batch
from contracts.ports import Intent
from kernel.event_catalog import build_v1_catalog
from resources.admission import make_proposal_rejected_draft
from resources.factions.service import (
    make_faction_plan_updated_draft,
    make_faction_subgroup_updated_draft,
    make_faction_updated_draft,
)
from resources.knowledge.model import HolderRef
from resources.knowledge.service import (
    make_claim_registered_draft,
    make_knowledge_acquired_draft,
    make_knowledge_inferred_draft,
    make_knowledge_revised_draft,
    make_knowledge_shared_draft,
)
from resources.npcs.service import (
    make_npc_goal_updated_draft,
    make_npc_plan_updated_draft,
    make_npc_promoted_draft,
    make_npc_relationship_updated_draft,
)


class TestPhase03DraftValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = build_v1_catalog()
        self.fps: set[str] = set()

    def test_all_13_new_events_drafts_pass_batch_validation(self) -> None:
        gt = "10 de Queluz, 10:00"
        gts = 1000

        h_val = HolderRef("npc", "npc_val")
        h_elena = HolderRef("npc", "npc_elena")

        drafts = [
            # 1. knowledge.claim_registered
            make_claim_registered_draft(
                claim_id="clm_001",
                proposition={"subject": "valerius", "predicate": "is_at", "object": "port"},
                claim_type="occurrence",
                game_time=gt,
                game_time_sort=gts,
                valid_from=1000,
                valid_to=2000,
            ),
            # 2. knowledge.acquired
            make_knowledge_acquired_draft(
                record_id="knw_001",
                holder=h_val,
                claim_id="clm_001",
                game_time=gt,
                game_time_sort=gts,
                awareness="known",
                stance="believed",
                confidence=10000,
                provenance=[{
                    "source_type": "event",
                    "source_id": "evt_001",
                    "channel": "observation",
                    "acquired_at": gt,
                    "acquired_at_sort": gts,
                    "confidence": 10000,
                    "derived_from": [],
                    "supports": True,
                }],
            ),
            # 3. knowledge.inferred
            make_knowledge_inferred_draft(
                record_id="knw_002",
                holder=h_val,
                claim_id="clm_002",
                derived_from=["knw_001"],
                game_time=gt,
                game_time_sort=gts,
                confidence=8500,
            ),
            # 4. knowledge.revised
            make_knowledge_revised_draft(
                record_id="knw_001",
                holder=h_val,
                claim_id="clm_001",
                stance="uncertain",
                confidence=4000,
                status="contested",
                reason="Divergência de testemunhos",
                game_time=gt,
                game_time_sort=gts,
            ),
            # 5. knowledge.shared
            make_knowledge_shared_draft(
                record_id="knw_003",
                from_holder=h_val,
                to_holder=h_elena,
                claim_id="clm_001",
                scope="subgroup_only",
                confidence=9000,
                game_time=gt,
                game_time_sort=gts,
            ),
            # 6. npc.promoted
            make_npc_promoted_draft(
                npc_id="npc_valerius",
                from_tier="minor",
                to_tier="major",
                game_time=gt,
                game_time_sort=gts,
                capabilities=["investigation", "stealth"],
                resources={"gold": 150},
            ),
            # 7. npc.goal_updated
            make_npc_goal_updated_draft(
                npc_id="npc_valerius",
                goal_id="goal_find_traitor",
                description="Descobrir o infiltrado",
                horizon="short",
                priority=1,
                status="active",
                game_time=gt,
                game_time_sort=gts,
            ),
            # 8. npc.plan_updated
            make_npc_plan_updated_draft(
                npc_id="npc_valerius",
                plan_id="plan_infiltrate",
                goal_id="goal_find_traitor",
                title="Plano de Infiltração",
                steps=[{"step_id": "s1", "order": 0, "action_kind": "scout", "description": "Vigiar cais"}],
                status="active",
                game_time=gt,
                game_time_sort=gts,
            ),
            # 9. npc.relationship_updated
            make_npc_relationship_updated_draft(
                npc_id="npc_valerius",
                target_id="npc_elena",
                trust=30,
                rivalry=10,
                game_time=gt,
                game_time_sort=gts,
            ),
            # 10. faction.updated
            make_faction_updated_draft(
                tag="CORVOS",
                name="Ordem dos Corvos",
                game_time=gt,
                game_time_sort=gts,
                leadership={"leader_id": "npc_corvo_mestre", "title": "Grão-Mestre", "authority_level": 5},
                resources={"ouro": 5000},
            ),
            # 11. faction.subgroup_updated
            make_faction_subgroup_updated_draft(
                faction_tag="CORVOS",
                subgroup_id="ala_cinzenta",
                name="Ala Cinzenta",
                leader_id="npc_elena",
                stance_towards_leadership="rebellious",
                game_time=gt,
                game_time_sort=gts,
            ),
            # 12. faction.plan_updated
            make_faction_plan_updated_draft(
                faction_tag="CORVOS",
                plan_id="plan_strike",
                title="Golpe Corporativo",
                steps=[{"step_id": "s1", "order": 0, "description": "Bloquear portão"}],
                status="active",
                game_time=gt,
                game_time_sort=gts,
            ),
            # 13. proposal.rejected
            make_proposal_rejected_draft(
                intent=Intent(
                    actor_kind="npc",
                    actor_id="npc_valerius",
                    intent_kind="strike",
                    description="Atacar guarda",
                ),
                reasons=["CAPABILITY_MISSING: Ator carece de 'combat'"],
                game_time=gt,
                game_time_sort=gts,
            ),
        ]

        # Executa validação de draft batch com catálogo v1
        validate_draft_batch(drafts, self.catalog, self.fps)
        self.assertEqual(len(drafts), 13)


if __name__ == "__main__":
    unittest.main()
