"""tests/test_phase03_agents_and_g3.py: Suíte Integrada de Aceite da Fase 03 e Gate G3 (AT01 a AT17).

100% integrados via JsonlEventStore real (append/read) e rebuild de projeções,
cobrindo estritamente a semântica canônica ratificada em specs/012-phase-03-agents/spec.md §4.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from application.rebuild import rebuild_projections
from contracts.event import ActorRef, Event, EventDraft
from contracts.ports import Intent
from kernel.ids import new_claim_id, new_knowledge_id, new_plan_id
from resources.admission import (
    make_proposal_rejected_draft,
    validate_intent_admission,
)
from resources.factions.service import (
    make_faction_plan_draft,
    make_faction_subgroup_updated_draft,
    make_faction_updated_draft,
    project_factions_state,
)
from resources.knowledge.model import (
    Claim,
    ClaimProposition,
    HolderRef,
    KnowledgeRecord,
    ProvenanceRef,
)
from resources.knowledge.provenance import (
    InvalidPremiseError,
    ProvenanceCycleError,
    check_and_assert_provenance,
    validate_provenance_chain,
)
from resources.knowledge.resolver import resolve_claim
from resources.knowledge.service import (
    make_claim_registered_draft,
    make_knowledge_acquired_draft,
    make_knowledge_inferred_draft,
    make_knowledge_revised_draft,
    make_knowledge_shared_draft,
    project_knowledge_state,
)
from resources.knowledge.view import (
    ClaimQueryResult,
    DefaultKnowledgeProvider,
    KnowledgeView,
)
from resources.npcs.service import (
    make_npc_goal_updated_draft,
    make_npc_plan_draft,
    make_npc_plan_updated_draft,
    make_npc_promoted_draft,
    make_npc_relationship_updated_draft,
    make_npc_updated_draft,
    project_npcs_state,
)


def _init_campaign_store(tmp_dir: str, campaign_id: str = "camp_g3") -> JsonlEventStore:
    store = JsonlEventStore(tmp_dir)
    init_draft = EventDraft(
        type="campaign.created",
        schema_version=1,
        actor=ActorRef(kind="system", id="init"),
        game_time="01 de Outubro de 2026, 08:00",
        game_time_sort=1,
        payload={
            "title": "Campanha Teste Gate G3",
            "system": "tagmar2",
            "calendar": "padrao",
            "start_game_time": "01 de Outubro de 2026, 08:00",
            "config_version": 1,
        },
    )
    store.append(campaign_id, [init_draft])
    return store


class Phase03AgentsAndG3Tests(unittest.TestCase):

    def test_at01_fact_vs_belief(self) -> None:
        """AT01: Fato canônico no motor vs crença subjetiva do NPC no store."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid_alive = "clm_01J7ABCDEF0000000000000001"
            cid_dead = "clm_01J7ABCDEF0000000000000002"

            claim_alive = Claim(cid_alive, ClaimProposition("rei", "status", "vivo"), "state", fact_ref="npc:rei:status")
            claim_dead = Claim(cid_dead, ClaimProposition("rei", "status", "morto"), "state", fact_ref="npc:rei:status")

            # Store registra a crença subjetiva do guarda de que o rei está morto
            d_clm_dead = make_claim_registered_draft(cid_dead, {"subject": "rei", "predicate": "status", "object": "morto"}, "state", "01/10", 10, fact_ref="npc:rei:status")
            d_acq = make_knowledge_acquired_draft(
                record_id="knw_01J7ABCDEF0000000000000001",
                holder=HolderRef("npc", "guarda"),
                claim_id=cid_dead,
                game_time="01/10",
                game_time_sort=10,
                stance="believed",
                confidence=9000,
                provenance=[{"source_type": "npc", "source_id": "boato", "channel": "testimony", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 9000, "derived_from": [], "supports": True}],
            )
            store.append("camp_g3", [d_clm_dead, d_acq])

            # Motor avalia estado físico real: rei está vivo
            projected = {"npc": {"rei": {"status": "vivo"}}}
            evs = list(store.read("camp_g3"))

            # Fato no motor permanece vivo (TRUE) e morto é falso (FALSE)
            self.assertEqual(resolve_claim(claim_alive, 100, evs, projected), "TRUE")
            self.assertEqual(resolve_claim(claim_dead, 100, evs, projected), "FALSE")

            # Crença subjetiva do NPC no store permanece 'believed' para 'morto'
            recs = project_knowledge_state(evs)
            view = KnowledgeView(records=recs, holder=HolderRef("npc", "guarda"))
            res = view.query_claim(cid_dead)
            self.assertEqual(res.availability, "known")
            self.assertEqual(res.effective_stance, "believed")

    def test_at02_knowing_without_believing(self) -> None:
        """AT02: NPC tem ciência de um fato (awareness=known, stance=disbelieved) e intenção é admitida."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid = "clm_01J7ABCDEF0000000000000003"
            holder = HolderRef("npc", "viajante")

            intent = Intent(
                actor_kind="npc",
                actor_id="viajante",
                intent_kind="investigate",
                description="Verificar se a ponte realmente caiu",
                required_claims=(cid,),
            )

            # Fase 1: NPC desconhece a claim (availability='unknown') -> rejeição com EPISTEMIC_UNSATISFIED
            empty_view = KnowledgeView(records={}, holder=holder)
            prov_empty = DefaultKnowledgeProvider(empty_view)
            admitted_before, errs_before = validate_intent_admission(intent, prov_empty)
            self.assertFalse(admitted_before)
            self.assertTrue(any("EPISTEMIC_UNSATISFIED" in e for e in errs_before), f"Esperado erro EPISTEMIC_UNSATISFIED: {errs_before}")

            # Fase 2: NPC recebe relato de ponte caída, mas não acredita (awareness=known, stance=disbelieved)
            d_clm = make_claim_registered_draft(cid, {"subject": "ponte", "predicate": "status", "object": "caida"}, "occurrence", "01/10", 10)
            d_acq = make_knowledge_acquired_draft(
                record_id="knw_01J7ABCDEF0000000000000003",
                holder=holder,
                claim_id=cid,
                game_time="01/10",
                game_time_sort=10,
                awareness="known",
                stance="disbelieved",
                confidence=2000,
                provenance=[{"source_type": "npc", "source_id": "batedor", "channel": "testimony", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 2000, "derived_from": [], "supports": True}],
            )
            store.append("camp_g3", [d_clm, d_acq])

            evs = list(store.read("camp_g3"))
            view = KnowledgeView(records=project_knowledge_state(evs), holder=holder)
            prov = DefaultKnowledgeProvider(view)

            # Intenção agora é admitida com sucesso pois o agente possui awareness=known
            admitted, errs = validate_intent_admission(intent, prov)
            self.assertTrue(admitted, f"Intenção deveria ser admitida por ter awareness=known: {errs}")

    def test_at03_provenance_required_and_acyclic(self) -> None:
        """AT03: Registro com proveniência e DAG é aceito; sem proveniência ou com ciclo é rejeitado."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            h = HolderRef("npc", "erudito")
            cid_a = "clm_01J7ABCDEF000000000000000A"
            cid_b = "clm_01J7ABCDEF000000000000000B"

            # Registro com proveniência válida gravado no store
            d_clm_a = make_claim_registered_draft(cid_a, {"subject": "tomo", "predicate": "autentico", "object": "sim"}, "state", "01/10", 10)
            d_acq_a = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF000000000000000A", h, cid_a, "01/10", 10,
                provenance=[{"source_type": "document", "source_id": "tomo_1", "channel": "document", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 9500, "derived_from": [], "supports": True}],
            )
            d_clm_b = make_claim_registered_draft(cid_b, {"subject": "segredo", "predicate": "revelado", "object": "sim"}, "state", "01/10", 11)
            d_inf_b = make_knowledge_inferred_draft(
                "knw_01J7ABCDEF000000000000000B", h, cid_b, derived_from=["knw_01J7ABCDEF000000000000000A"], game_time="01/10", game_time_sort=11,
            )
            store.append("camp_g3", [d_clm_a, d_acq_a, d_clm_b, d_inf_b])

            recs = project_knowledge_state(list(store.read("camp_g3")))
            self.assertEqual(len(recs), 2)
            self.assertEqual(recs["knw_01J7ABCDEF000000000000000B"].derived_from, ("knw_01J7ABCDEF000000000000000A",))

            # Registro sem proveniência é rejeitado
            rec_empty_prov = KnowledgeRecord("knw_inv", h, "clm_x", "known", "believed", 10000, "current", (), "01/10", 10)
            with self.assertRaises(ValueError):
                check_and_assert_provenance(rec_empty_prov, recs)

            # Dependência circular é rejeitada
            rec_cycle = KnowledgeRecord(
                "knw_01J7ABCDEF000000000000000A", h, cid_a, "known", "believed", 9000, "current",
                (ProvenanceRef("inference", "inf_cyc", "inference", "01/10", 12, 9000, ("knw_01J7ABCDEF000000000000000B",)),),
                "01/10", 12, derived_from=("knw_01J7ABCDEF000000000000000B",),
            )
            with self.assertRaises(ProvenanceCycleError):
                check_and_assert_provenance(rec_cycle, recs)

    def test_at04_false_belief_drives_plan_not_fact(self) -> None:
        """AT04: Crença falsa sustenta plano operacional no store sem alterar a verdade do mundo."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid = "clm_01J7ABCDEF0000000000000004"
            holder = HolderRef("npc", "marechal_kurt")

            # Mundo físico: ponte destruída
            projected_world = {"estrutura": {"ponte": {"status": "destruida"}}}
            claim = Claim(cid, ClaimProposition("ponte", "status", "intacta"), "state", fact_ref="estrutura:ponte:status")

            # Marechal crê no rumor de ponte intacta e adota plano
            d_clm = make_claim_registered_draft(cid, {"subject": "ponte", "predicate": "status", "object": "intacta"}, "state", "01/10", 10)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000004", holder, cid, "01/10", 10,
                provenance=[{"source_type": "npc", "source_id": "boato", "channel": "testimony", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 9000, "derived_from": [], "supports": True}],
            )
            d_plan = make_npc_plan_draft(
                "marechal_kurt", "cruzar_rio", [{"step_id": "s1", "order": 0, "description": "Marchar"}], "01/10", 10,
            )
            store.append("camp_g3", [d_clm, d_acq, d_plan])

            evs = list(store.read("camp_g3"))
            npcs = project_npcs_state(evs)
            self.assertIsNotNone(npcs["marechal_kurt"].active_plan)

            # Motor avalia como FALSE: a crença falsa não mutou a verdade do mundo
            self.assertEqual(resolve_claim(claim, 10, evs, projected_world), "FALSE")

    def test_at05_outdated_distinct_from_current(self) -> None:
        """AT05: Informação histórica expirada transiciona deterministicamente para 'outdated'."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid = "clm_01J7ABCDEF0000000000000005"
            holder = HolderRef("npc", "viajante")

            # Claim com janela válida até t=200
            d_clm = make_claim_registered_draft(cid, {"subject": "ponte", "predicate": "status", "object": "de pe"}, "state", "01/10", 10, valid_to=200)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000005", holder, cid, "01/10", 20,
                provenance=[{"source_type": "npc", "source_id": "viajante", "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 20, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            store.append("camp_g3", [d_clm, d_acq])

            evs = list(store.read("camp_g3"))
            r_in = project_knowledge_state(evs, current_time_sort=150)["knw_01J7ABCDEF0000000000000005"]
            r_out = project_knowledge_state(evs, current_time_sort=300)["knw_01J7ABCDEF0000000000000005"]

            self.assertEqual(r_in.status, "current")
            self.assertEqual(r_out.status, "outdated")

    def test_at06_provisional_inference_with_premises(self) -> None:
        """AT06: Inferência provisória exige premissas e nunca se promove a fato canônico consumado."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            h = HolderRef("npc", "detetive")
            cid_premise = "clm_01J7ABCDEF000000000000006A"
            cid_infer = "clm_01J7ABCDEF000000000000006B"

            d_p = make_claim_registered_draft(cid_premise, {"subject": "pegadas", "predicate": "no_chao", "object": "sim"}, "occurrence", "01/10", 10)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF000000000000006A", h, cid_premise, "01/10", 10,
                provenance=[{"source_type": "npc", "source_id": "detetive", "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            d_i = make_claim_registered_draft(cid_infer, {"subject": "ladrao", "predicate": "passou_aqui", "object": "sim"}, "occurrence", "01/10", 11)
            d_inf = make_knowledge_inferred_draft(
                "knw_01J7ABCDEF000000000000006B", h, cid_infer, derived_from=["knw_01J7ABCDEF000000000000006A"], game_time="01/10", game_time_sort=11, confidence=8000,
            )
            store.append("camp_g3", [d_p, d_acq, d_i, d_inf])

            evs = list(store.read("camp_g3"))
            recs = project_knowledge_state(evs)
            self.assertEqual(recs["knw_01J7ABCDEF000000000000006B"].derived_from, ("knw_01J7ABCDEF000000000000006A",))

            # Motor avalia inferência como UNKNOWN (não consumado fisicamente)
            claim = Claim(cid_infer, ClaimProposition("ladrao", "passou_aqui", "sim"), "occurrence")
            self.assertEqual(resolve_claim(claim, 12, evs, {}), "UNKNOWN")

    def test_at07_collective_knowledge_no_auto_propagation(self) -> None:
        """AT07: Segredo de membro não vaza para a facção sem knowledge.shared."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid = "clm_01J7ABCDEF0000000000000007"
            membro = HolderRef("npc", "ladrao_membro")
            fac = HolderRef("faction", "GUILDA")

            d_clm = make_claim_registered_draft(cid, {"subject": "mapa", "predicate": "escondido", "object": "caverna"}, "state", "01/10", 10)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000007", membro, cid, "01/10", 10, visibility="holder_only",
                provenance=[{"source_type": "npc", "source_id": "ladrao_membro", "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            store.append("camp_g3", [d_clm, d_acq])

            evs = list(store.read("camp_g3"))
            recs = project_knowledge_state(evs)

            # Facção não conhece
            v_fac = KnowledgeView(records=recs, holder=fac)
            self.assertEqual(v_fac.query_claim(cid).availability, "unknown")

            # Compartilha com a facção
            d_sh = make_knowledge_shared_draft("knw_01J7ABCDEF0000000000000008", membro, fac, cid, "faction_internal", 10000, "01/10", 11)
            store.append("camp_g3", [d_sh])

            evs2 = list(store.read("camp_g3"))
            recs2 = project_knowledge_state(evs2)
            v_fac2 = KnowledgeView(records=recs2, holder=fac)
            self.assertEqual(v_fac2.query_claim(cid).availability, "known")

    def test_at08_player_secret_blocked_for_protagonist(self) -> None:
        """AT08: Conhecimento com visibility='player_meta' retorna 'unavailable' para o protagonista."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid = "clm_01J7ABCDEF0000000000000008"
            p_holder = HolderRef("player", "jogador1")
            prot_aud = HolderRef("protagonist", "heroi")

            d_clm = make_claim_registered_draft(cid, {"subject": "traidor", "predicate": "identidade", "object": "mentor"}, "state", "01/10", 10)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000008", p_holder, cid, "01/10", 10, visibility="player_meta",
                provenance=[{"source_type": "system", "source_id": "narrador", "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            store.append("camp_g3", [d_clm, d_acq])

            recs = project_knowledge_state(list(store.read("camp_g3")))
            view = KnowledgeView(records=recs, holder=p_holder, audience=prot_aud)
            res = view.query_claim(cid)
            self.assertEqual(res.availability, "unavailable")

    def test_at09_rejected_proposal_leaves_state_unchanged(self) -> None:
        """AT09: Proposta rejeitada emite proposal.rejected e comprova que estado do NPC permanece inalterado."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            # NPC guarda major já existente com objetivo base
            d_promote = make_npc_promoted_draft(
                npc_id="guarda",
                from_tier="minor",
                to_tier="major",
                game_time="01/10",
                game_time_sort=5,
                goals=[{"goal_id": "g_base", "description": "Guardar o portão central", "priority": 1, "status": "active"}],
            )
            store.append("camp_g3", [d_promote])

            # Intenção proposta que exige conhecimento inexistente
            intent = Intent(
                actor_kind="npc",
                actor_id="guarda",
                intent_kind="adopt_plan",
                description="Desertar do posto e abrir o portão clandestinamente",
                required_claims=("clm_chave_inexistente",),
            )
            prov = DefaultKnowledgeProvider(KnowledgeView(records={}))
            admitted, errs = validate_intent_admission(intent, prov)
            self.assertFalse(admitted)

            # Emite evento canônico proposal.rejected alinhado ao catálogo
            d_rej = make_proposal_rejected_draft(intent, errs, "01/10", 10)
            self.assertEqual(d_rej.payload["proposal_kind"], "adopt_plan")
            self.assertEqual(d_rej.payload["actor_id"], "guarda")
            self.assertEqual(d_rej.payload["reasons"], list(errs))
            store.append("camp_g3", [d_rej])

            # Replay e projeção de estado comprovam que nenhum plano ou objetivo foi adotado
            evs = list(store.read("camp_g3"))
            npcs = project_npcs_state(evs)
            self.assertIn("guarda", npcs)
            guarda = npcs["guarda"]
            self.assertIsNone(guarda.active_plan)
            self.assertEqual(len(guarda.plans), 0)
            self.assertEqual(len(guarda.goals), 1)
            self.assertEqual(guarda.goals[0].goal_id, "g_base")

    def test_at10_reconstruction_with_correction(self) -> None:
        """AT10: Reconstrução com rebuild_projections e correction.issued anula fato preservando proveniências."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir, "camp_at10")
            camp_dir = Path(tmp_dir) / "campaigns" / "camp_at10"
            camp_dir.mkdir(parents=True, exist_ok=True)

            # 1. Turno canônico com ocorrência física gravado no store
            d_turn = EventDraft(
                type="turn.committed", schema_version=1, actor=ActorRef("agent", "narrator"),
                game_time="01/10", game_time_sort=10,
                payload={"turn": 1, "summary": "O monstro atacou a muralha"},
            )
            res_turn = store.append("camp_at10", [d_turn])
            target_evt_id = res_turn.events[0].event_id

            # 2. Claim e conhecimento com proveniência apontando para o evento do turno
            cid = "clm_atk"
            claim = Claim(cid, ClaimProposition("monstro", "atacou", "muralha"), "occurrence", source_event_id=target_evt_id)
            d_clm = make_claim_registered_draft(cid, {"subject": "monstro", "predicate": "atacou", "object": "muralha"}, "occurrence", "01/10", 11, source_event_id=target_evt_id)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000010", HolderRef("npc", "sentinela"), cid, "01/10", 11,
                provenance=[{"source_type": "event", "source_id": target_evt_id, "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 11, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            store.append("camp_at10", [d_clm, d_acq])

            # Sem correção: fato físico resolve como TRUE
            evs_before = list(store.read("camp_at10"))
            self.assertEqual(resolve_claim(claim, 15, evs_before, {}), "TRUE")

            # 3. Emite correction.issued corrigindo o evento de turno
            d_corr = EventDraft(
                type="correction.issued", schema_version=1, actor=ActorRef("system", "arbiter"),
                game_time="01/10", game_time_sort=20,
                payload={
                    "correction_id": "cor_01J7ABCDEF0000000000000010",
                    "corrects": [target_evt_id],
                    "reason": "Ataque não ocorreu na realidade",
                    "changes": [],
                },
            )
            store.append("camp_at10", [d_corr])

            # 4. Executa reconstrução completa de projeções
            seq, h_snap = rebuild_projections(store=store, campaign_id="camp_at10", campaign_dir=camp_dir, force=True)
            self.assertGreater(seq, 0)
            self.assertTrue((camp_dir / "diario.md").exists())

            # 5. Verifica que o log e as proveniências originais em project_knowledge_state permanecem íntegros
            evs_all = list(store.read("camp_at10"))
            recs = project_knowledge_state(evs_all)
            self.assertIn("knw_01J7ABCDEF0000000000000010", recs)
            rec_sentinela = recs["knw_01J7ABCDEF0000000000000010"]
            self.assertEqual(rec_sentinela.provenance[0].source_id, target_evt_id)
            self.assertEqual(rec_sentinela.provenance[0].channel, "observation")
            self.assertEqual(rec_sentinela.provenance[0].confidence, 10000)

            # 6. E a alegação física corrigida resolve deterministicamente como UNKNOWN
            self.assertEqual(resolve_claim(claim, 25, evs_all, {}), "UNKNOWN")

    def test_at11_contradictory_sources_coexist_as_contested(self) -> None:
        """AT11: Duas fontes conflitantes em eventos separados consolidam status como 'contested'."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid = "clm_01J7ABCDEF0000000000000011"
            h = HolderRef("npc", "detetive")

            d_clm = make_claim_registered_draft(cid, {"subject": "suspeito", "predicate": "is_at", "object": "porto"}, "occurrence", "01/10", 30)
            d_acq1 = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000011", h, cid, "01/10", 30,
                provenance=[{"source_type": "npc", "source_id": "fonte_a", "channel": "testimony", "acquired_at": "01/10", "acquired_at_sort": 30, "confidence": 9000, "derived_from": [], "supports": True}],
            )
            d_acq2 = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000012", h, cid, "01/10", 31,
                provenance=[{"source_type": "npc", "source_id": "fonte_b", "channel": "testimony", "acquired_at": "01/10", "acquired_at_sort": 31, "confidence": 9000, "derived_from": [], "supports": False}],
            )
            store.append("camp_g3", [d_clm, d_acq1, d_acq2])

            recs = project_knowledge_state(list(store.read("camp_g3")))
            self.assertEqual(recs["knw_01J7ABCDEF0000000000000011"].status, "contested")
            self.assertEqual(recs["knw_01J7ABCDEF0000000000000012"].status, "contested")
            self.assertEqual(recs["knw_01J7ABCDEF0000000000000011"].stance, "uncertain")

    def test_at12_outdated_is_not_false(self) -> None:
        """AT12: Estado com janela expirada é FALSE no presente, mas válido no período histórico."""
        claim = Claim("clm_porto", ClaimProposition("porto", "status", "aberto"), "state", valid_from=10, valid_to=100)
        # Durante a vigência
        self.assertEqual(resolve_claim(claim, 50, [], {}), "UNKNOWN")  # Sem estado ou fact_ref
        claim_ref = Claim("clm_porto", ClaimProposition("porto", "status", "aberto"), "state", valid_from=10, valid_to=100, fact_ref="porto:status")
        self.assertEqual(resolve_claim(claim_ref, 50, [], {"porto": {"status": "aberto"}}), "TRUE")
        # Após a expiração do estado
        self.assertEqual(resolve_claim(claim_ref, 150, [], {"porto": {"status": "fechado"}}), "FALSE")

    def test_at13_inference_with_refuted_premise(self) -> None:
        """AT13: Premissa refutada via knowledge.revised bloqueia nova inferência e mantém histórico."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            h = HolderRef("npc", "alquimista")
            cid_p = "clm_01J7ABCDEF0000000000000013"

            d_clm = make_claim_registered_draft(cid_p, {"subject": "pedra", "predicate": "filosofal", "object": "sim"}, "state", "01/10", 10)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000013", h, cid_p, "01/10", 10,
                provenance=[{"source_type": "document", "source_id": "livro", "channel": "document", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 9000, "derived_from": [], "supports": True}],
            )
            # Premissa é refutada
            d_rev = make_knowledge_revised_draft(
                "knw_01J7ABCDEF0000000000000013", h, cid_p, stance="disbelieved", confidence=0, status="refuted", reason="Falsificação comprovada", game_time="01/10", game_time_sort=15,
            )
            store.append("camp_g3", [d_clm, d_acq, d_rev])

            recs = project_knowledge_state(list(store.read("camp_g3")))
            self.assertEqual(recs["knw_01J7ABCDEF0000000000000013"].status, "refuted")

            # Nova inferência baseada na premissa refutada é rejeitada
            cand_inf = KnowledgeRecord(
                "knw_01J7ABCDEF0000000000000014", h, "clm_nova", "known", "believed", 7000, "current",
                (ProvenanceRef("inference", "inf_1", "inference", "01/10", 20, 7000, ("knw_01J7ABCDEF0000000000000013",)),),
                "01/10", 20, derived_from=("knw_01J7ABCDEF0000000000000013",),
            )
            with self.assertRaises(InvalidPremiseError):
                check_and_assert_provenance(cand_inf, recs)

    def test_at14_divided_faction_and_subgroup_divergence(self) -> None:
        """AT14: Subgrupo com postura rebelde mantém planos com 'subgroup_only' inacessíveis para a liderança."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            sub_holder = HolderRef("subgroup", "ALA_REBELDE")
            fac_holder = HolderRef("faction", "ORDEM")
            cid = "clm_01J7ABCDEF0000000000000014"

            d_clm = make_claim_registered_draft(cid, {"subject": "golpe", "predicate": "planejado", "object": "sim"}, "state", "01/10", 10)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000014", sub_holder, cid, "01/10", 10, visibility="subgroup_only",
                provenance=[{"source_type": "faction", "source_id": "ALA_REBELDE", "channel": "communication", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            store.append("camp_g3", [d_clm, d_acq])

            recs = project_knowledge_state(list(store.read("camp_g3")))
            # Liderança consulta plano do subgrupo
            view_fac = KnowledgeView(records=recs, holder=fac_holder, audience=fac_holder)
            self.assertEqual(view_fac.query_claim(cid).availability, "unknown")

            # Audiência como facção tentando ler o registro do subgrupo
            view_sub = KnowledgeView(records=recs, holder=sub_holder, audience=fac_holder)
            self.assertEqual(view_sub.query_claim(cid).availability, "unavailable")

    def test_at15_fact_correction_does_not_rewrite_belief(self) -> None:
        """AT15: correction.issued anula fato no motor mas preserva crença subjetiva do NPC no store."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid = "clm_01J7ABCDEF0000000000000015"
            h = HolderRef("npc", "guarda")
            target_evt_id = "evt_01J7ABCDEF0000000000000015"

            ev_fact = Event(
                event_id=target_evt_id, campaign_id="camp_g3", seq=2,
                type="turn.committed", schema_version=1, recorded_at="2026-10-26T10:00:00Z",
                game_time="01/10", game_time_sort=10, actor=ActorRef("agent", "narrator"),
                causation_id=None, correlation_id=None,
                payload={"summary": "O dragão destruiu a torre"}, meta={},
            )
            d_clm = make_claim_registered_draft(cid, {"subject": "dragao", "predicate": "destruiu", "object": "torre"}, "occurrence", "01/10", 10, source_event_id=target_evt_id)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000015", h, cid, "01/10", 10,
                provenance=[{"source_type": "event", "source_id": target_evt_id, "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            d_corr = EventDraft(
                type="correction.issued", schema_version=1, actor=ActorRef("system", "arbiter"),
                game_time="01/10", game_time_sort=20,
                payload={
                    "correction_id": "cor_01J7ABCDEF0000000000000015",
                    "corrects": [target_evt_id],
                    "reason": "Ilusão mágica",
                    "changes": [],
                },
            )
            store.append("camp_g3", [d_clm, d_acq, d_corr])

            evs = [ev_fact] + list(store.read("camp_g3"))

            # Motor anula o fato físico (UNKNOWN)
            claim = Claim(cid, ClaimProposition("dragao", "destruiu", "torre"), "occurrence", source_event_id=target_evt_id)
            self.assertEqual(resolve_claim(claim, 25, evs, {}), "UNKNOWN")

            # Crença subjetiva do NPC permanece intacta no store (believed) sem knowledge.revised
            recs = project_knowledge_state(evs)
            self.assertEqual(recs["knw_01J7ABCDEF0000000000000015"].stance, "believed")
            self.assertEqual(recs["knw_01J7ABCDEF0000000000000015"].status, "current")

    def test_at16_replay_and_snapshot_byte_identical(self) -> None:
        """AT16: Replay do zero e a partir de snapshot gera arquivos npcs.md e faccoes.md byte-idênticos."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir, "camp_at16")
            batch = [
                make_claim_registered_draft("clm_01J7ABCDEF0000000000000016", {"subject": "tesouro", "predicate": "is_at", "object": "torre"}, "state", "01/10", 10),
                make_knowledge_acquired_draft("knw_01J7ABCDEF0000000000000016", HolderRef("npc", "kael"), "clm_01J7ABCDEF0000000000000016", "01/10", 10),
                make_npc_promoted_draft("kael", "minor", "major", "01/10", 10, capabilities=["furtividade"]),
                make_npc_plan_draft("kael", "infiltrar", [{"description": "subir"}], "01/10", 10),
                make_faction_updated_draft("CORVOS", "Ordem dos Corvos", "01/10", 10, collective_goals=[{"goal_id": "g1", "description": "Dominar o porto"}]),
            ]
            store.append("camp_at16", batch)

            camp_dir = Path(tmp_dir) / "campaigns" / "camp_at16"
            camp_dir.mkdir(parents=True, exist_ok=True)

            # Rebuild 1 do zero
            seq1, hash1 = rebuild_projections(store=store, campaign_id="camp_at16", campaign_dir=camp_dir, force=True)
            npcs1 = (camp_dir / "npcs.md").read_text(encoding="utf-8")
            fac1 = (camp_dir / "faccoes.md").read_text(encoding="utf-8")

            # Rebuild 2 a partir do snapshot
            seq2, hash2 = rebuild_projections(store=store, campaign_id="camp_at16", campaign_dir=camp_dir, force=False)
            npcs2 = (camp_dir / "npcs.md").read_text(encoding="utf-8")
            fac2 = (camp_dir / "faccoes.md").read_text(encoding="utf-8")

            self.assertEqual(hash1, hash2)
            self.assertEqual(npcs1, npcs2)
            self.assertEqual(fac1, fac2)
            self.assertTrue((camp_dir / "faccoes.md").exists())

    def test_at17_knowledge_view_prevents_secret_leakage(self) -> None:
        """AT17: KnowledgeView bloqueia vazamento de segredos para todas as classes de audiência não autorizadas."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir)
            cid = "clm_01J7ABCDEF0000000000000017"

            # 1. holder_only bloqueado para terceiros e protagonista
            d_clm = make_claim_registered_draft(cid, {"subject": "segredo", "predicate": "privado", "object": "x"}, "state", "01/10", 10)
            d_acq = make_knowledge_acquired_draft(
                "knw_01J7ABCDEF0000000000000017", HolderRef("npc", "agente_a"), cid, "01/10", 10, visibility="holder_only",
                provenance=[{"source_type": "npc", "source_id": "agente_a", "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            store.append("camp_g3", [d_clm, d_acq])

            recs = project_knowledge_state(list(store.read("camp_g3")))
            v_self = KnowledgeView(records=recs, holder=HolderRef("npc", "agente_a"), audience=HolderRef("npc", "agente_a"))
            v_prot = KnowledgeView(records=recs, holder=HolderRef("npc", "agente_a"), audience=HolderRef("protagonist", "heroi"))
            v_third = KnowledgeView(records=recs, holder=HolderRef("npc", "agente_a"), audience=HolderRef("npc", "agente_b"))

            self.assertEqual(v_self.query_claim(cid).availability, "known")
            self.assertEqual(v_prot.query_claim(cid).availability, "unavailable")
            self.assertEqual(v_third.query_claim(cid).availability, "unavailable")

    def test_fr_ag_04_admission(self) -> None:
        """FR-AG-04: Admissão valida autoridade de facção, condição física e descompasso de localização."""
        prov = DefaultKnowledgeProvider(KnowledgeView(records={}))

        # 1. Autoridade de facção: membro tenta agir pela facção sem autoridade de liderança
        intent_faction = Intent(
            actor_kind="npc",
            actor_id="soldado_1",
            intent_kind="negotiate_treaty",
            description="Assinar tratado em nome da Ordem",
            acts_for_faction="ORDEM",
        )
        admitted_fac, errs_fac = validate_intent_admission(intent_faction, prov, is_leader=False)
        self.assertFalse(admitted_fac)
        self.assertTrue(any("UNAUTHORIZED_FACTION_LEADERSHIP" in e for e in errs_fac))

        admitted_fac_ok, _ = validate_intent_admission(intent_faction, prov, is_leader=True)
        self.assertTrue(admitted_fac_ok)

        # 2. Condição física: ator incapacitado não pode executar ações ativas
        intent_action = Intent(
            actor_kind="npc",
            actor_id="soldado_1",
            intent_kind="patrol",
            description="Patrulhar o pátio",
        )
        for cond in ("incapacitated", "dead", "unconscious", "paralyzed"):
            admitted_cond, errs_cond = validate_intent_admission(intent_action, prov, actor_condition=cond)
            self.assertFalse(admitted_cond)
            self.assertTrue(any("ACTOR_INCAPACITATED" in e for e in errs_cond))

        admitted_healthy, _ = validate_intent_admission(intent_action, prov, actor_condition="healthy")
        self.assertTrue(admitted_healthy)

        # 3. Descompasso de localização
        intent_loc = Intent(
            actor_kind="npc",
            actor_id="soldado_1",
            intent_kind="defend_wall",
            description="Defender a muralha",
            location="Muralha Norte",
        )
        admitted_loc, errs_loc = validate_intent_admission(intent_loc, prov, actor_location="Taverna Central")
        self.assertFalse(admitted_loc)
        self.assertTrue(any("LOCATION_MISMATCH" in e for e in errs_loc))

        admitted_loc_ok, _ = validate_intent_admission(intent_loc, prov, actor_location="Muralha Norte")
        self.assertTrue(admitted_loc_ok)

    def test_regression_p0_knowledge_shared_non_npc_origins(self) -> None:
        """Regressão P0: knowledge.shared com origens não-NPC reconstrói e preserva proveniência canônica."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir, "camp_at18")
            cid1 = "clm_01J7ABCDEF0000000000000018"
            cid2 = "clm_01J7ABCDEF0000000000000019"
            cid3 = "clm_01J7ABCDEF000000000000001A"

            # 1. player -> protagonist
            h_player = HolderRef("player", "jogador1")
            h_prot = HolderRef("protagonist", "heroi")
            d_clm1 = make_claim_registered_draft(cid1, {"subject": "mapa", "predicate": "revelado", "object": "sim"}, "state", "01/10", 10)
            d_sh1 = make_knowledge_shared_draft("knw_sh1", h_player, h_prot, cid1, "faction_internal", 9000, "01/10", 10)

            # 2. subgroup -> faction
            h_sub = HolderRef("subgroup", "ALA_REBELDE")
            h_fac = HolderRef("faction", "ORDEM")
            d_clm2 = make_claim_registered_draft(cid2, {"subject": "armas", "predicate": "quantidade", "object": "100"}, "state", "01/10", 11)
            d_sh2 = make_knowledge_shared_draft("knw_sh2", h_sub, h_fac, cid2, "faction_internal", 8500, "01/10", 11)

            # 3. protagonist -> player
            d_clm3 = make_claim_registered_draft(cid3, {"subject": "visao", "predicate": "experimentada", "object": "sim"}, "state", "01/10", 12)
            d_sh3 = make_knowledge_shared_draft("knw_sh3", h_prot, h_player, cid3, "faction_internal", 9500, "01/10", 12)

            store.append("camp_at18", [d_clm1, d_sh1, d_clm2, d_sh2, d_clm3, d_sh3])

            evs = list(store.read("camp_at18"))
            recs = project_knowledge_state(evs)

            # Valida que nenhum levantou ValueError de source_type inválido e proveniências estão íntegras
            self.assertIn("knw_sh1", recs)
            self.assertEqual(recs["knw_sh1"].provenance[0].source_type, "player")

            self.assertIn("knw_sh2", recs)
            self.assertEqual(recs["knw_sh2"].provenance[0].source_type, "subgroup")

            self.assertIn("knw_sh3", recs)
            self.assertEqual(recs["knw_sh3"].provenance[0].source_type, "protagonist")

    def test_regression_p1_player_meta_coexistence_and_holder_only_leakage(self) -> None:
        """Regressão P1: player_meta não bloqueia claim com registro público e holder_only é inacessível sem audiência."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir, "camp_at19")
            cid_coex = "clm_coex_01J7ABC"
            cid_secret = "clm_secret_01J7ABC"

            # Cenário 1: Claim com registro público de NPC + player_meta
            d_clm1 = make_claim_registered_draft(cid_coex, {"subject": "castelo", "predicate": "status", "object": "cercado"}, "state", "01/10", 10)
            d_acq_pub = make_knowledge_acquired_draft(
                "knw_pub", HolderRef("npc", "guarda"), cid_coex, "01/10", 10, visibility="public",
                provenance=[{"source_type": "npc", "source_id": "guarda", "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 10, "confidence": 10000, "derived_from": [], "supports": True}],
            )
            d_acq_meta = make_knowledge_acquired_draft(
                "knw_meta", HolderRef("player", "jogador"), cid_coex, "01/10", 11, visibility="player_meta",
                provenance=[{"source_type": "player", "source_id": "jogador", "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 11, "confidence": 10000, "derived_from": [], "supports": True}],
            )

            # Cenário 2: Segredo holder_only de outro holder
            d_clm2 = make_claim_registered_draft(cid_secret, {"subject": "rei", "predicate": "escondido", "object": "cripta"}, "state", "01/10", 12)
            d_acq_sec = make_knowledge_acquired_draft(
                "knw_sec", HolderRef("npc", "espião"), cid_secret, "01/10", 12, visibility="holder_only",
                provenance=[{"source_type": "npc", "source_id": "espião", "channel": "observation", "acquired_at": "01/10", "acquired_at_sort": 12, "confidence": 10000, "derived_from": [], "supports": True}],
            )

            store.append("camp_at19", [d_clm1, d_acq_pub, d_acq_meta, d_clm2, d_acq_sec])
            recs = project_knowledge_state(list(store.read("camp_at19")))

            # Cenário 1: Audiência de NPC consultando claim com registro público + player_meta -> deve retornar known
            view_npc = KnowledgeView(records=recs, holder=HolderRef("npc", "guarda"), audience=HolderRef("npc", "cidadao"))
            res1 = view_npc.query_claim(cid_coex)
            self.assertEqual(res1.availability, "known")

            # Cenário 2: KnowledgeView sem audiência (aud=None) consultando segredo holder_only -> deve retornar unavailable
            view_no_aud = KnowledgeView(records=recs)
            res2 = view_no_aud.query_claim(cid_secret)
            self.assertEqual(res2.availability, "unavailable")

    def test_regression_p2_negation_and_dedup_and_commitments(self) -> None:
        """Regressão P2: Antinegação correta, negação explícita (FALSE), deduplicação de versões e persistência."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _init_campaign_store(tmp_dir, "camp_at20")

            # 1. Antinegação: 'sem luta' não deve anular 'morreu' (TRUE); 'nao morreu' refuta a ocorrência (FALSE)
            ev_turn1 = Event(
                event_id="evt_01J7ABCDEF0000000000000021", campaign_id="camp_at20", seq=2,
                type="turn.committed", schema_version=1, recorded_at="2026-10-26T10:00:00Z",
                game_time="01/10", game_time_sort=10, actor=ActorRef("agent", "narrator"),
                causation_id=None, correlation_id=None,
                payload={"turn": 1, "summary": "O capitao morreu sem luta no patio"}, meta={},
            )
            ev_turn2 = Event(
                event_id="evt_01J7ABCDEF0000000000000022", campaign_id="camp_at20", seq=3,
                type="turn.committed", schema_version=1, recorded_at="2026-10-26T10:00:00Z",
                game_time="01/10", game_time_sort=20, actor=ActorRef("agent", "narrator"),
                causation_id=None, correlation_id=None,
                payload={"turn": 2, "summary": "O tenente nao morreu na batalha"}, meta={},
            )
            claim1 = Claim("clm_cap1", ClaimProposition("capitao", "morreu", "sem luta"), "occurrence")
            claim2 = Claim("clm_ten2", ClaimProposition("tenente", "morreu", "batalha"), "occurrence")

            self.assertEqual(resolve_claim(claim1, 15, [ev_turn1], {}), "TRUE")
            self.assertEqual(resolve_claim(claim2, 25, [ev_turn2], {}), "FALSE")

            # 2. Deduplicação de planos de NPC e persistência de commitments
            d_promote = make_npc_promoted_draft(
                npc_id="kurt", from_tier="minor", to_tier="major", game_time="01/10", game_time_sort=1,
                commitments=["lealdade_ao_duque"],
            )
            d_plan_v1 = make_npc_plan_updated_draft(
                npc_id="kurt", plan_id="pln_defesa", goal_id="g_defesa", title="Defesa v1",
                steps=[{"step_id": "s1", "order": 0, "description": "Barricada"}],
                status="active", game_time="01/10", game_time_sort=2,
            )
            d_plan_v2 = make_npc_plan_updated_draft(
                npc_id="kurt", plan_id="pln_defesa", goal_id="g_defesa", title="Defesa v2",
                steps=[{"step_id": "s1", "order": 0, "description": "Fosso e Barricada"}],
                status="active", game_time="01/10", game_time_sort=3,
            )
            d_update = make_npc_updated_draft(
                npc_id="kurt", game_time="01/10", game_time_sort=4,
                commitments=["lealdade_ao_duque", "vigiar_porto"],
            )
            store.append("camp_at20", [d_promote, d_plan_v1, d_plan_v2, d_update])

            evs = list(store.read("camp_at20"))
            npcs = project_npcs_state(evs)
            kurt = npcs["kurt"]

            # Comprova deduplicação por plan_id (apenas 1 plano em vez de 2 duplicados)
            self.assertEqual(len(kurt.plans), 1)
            self.assertEqual(kurt.plans[0].plan_id, "pln_defesa")
            self.assertEqual(kurt.plans[0].steps[0].description, "Fosso e Barricada")

            # Comprova persistência de commitments a partir de npc.promoted e npc.updated
            self.assertEqual(kurt.commitments, ("lealdade_ao_duque", "vigiar_porto"))


if __name__ == "__main__":
    unittest.main()
