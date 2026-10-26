"""Suíte de testes de aceite C01 a C10 da Fase 04: Contexto Causal no prepare."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.persistence.event_store import JsonlEventStore
from application import cmd_prepare
from application.context.query import ContextQueryService
from application.rebuild import rebuild_projections
from contracts.event import ActorRef, EventDraft
from resources.context.policy import resolve_mode_policy
from resources.factions.service import make_faction_updated_draft
from resources.knowledge.drafts import make_claim_registered_draft, make_knowledge_acquired_draft
from resources.knowledge.model import HolderRef, ProvenanceRef
from resources.npcs.drafts import make_npc_plan_updated_draft, make_npc_promoted_draft, make_npc_relationship_updated_draft


class Phase04CausalContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.camp_dir = Path(self.tmp.name) / "ctx_camp"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        self.store = JsonlEventStore(self.camp_dir)

        # Configura ambiente de campanha
        diario_md = (
            "<!-- schema_version: 1 -->\n"
            "# Diário de Campanha\n\n"
            "### Cena 1: Início\n"
            "* **Data & Local:** 01/10/300 10:00 — Fortaleza Vermelha\n"
            "* **Presentes:** Aemon, Bob O Guarda.\n\n"
            "### Missões & Objetivos\n"
            "* **[Q1] [MAIN] Proteger o Reino** | Status: ACTIVE | Contratante: Rei | Alvo: Malakor | Relógio: Golpe da Guarda\n"
            "  * [ ] Defender o portão\n\n"
            "### Relógios de Ameaça & Prazos\n"
            "* **[Golpe da Guarda]:** 3/4 (Gatilho: Golpe) [ACTIVE]\n\n"
            "### Arco Narrativo Ativo\n"
            "* **Título:** O Destino do Trono\n"
            "* **Pergunta Central:** Malakor tomará a coroa?\n"
        )
        ficha_md = (
            "# Ficha do Protagonista\n\n"
            "### Identidade\n"
            "* **Nome:** Aemon\n"
            "* **Arquétipo:** Guerreiro\n\n"
            "### Vitais\n"
            "* **Pontos de Vida (PV):** 18/20\n"
            "* **Fôlego:** 10/10\n\n"
            "### Atributos\n"
            "* **FORÇA:** 14 (+2)\n"
            "* **DESTREZA:** 12 (+1)\n"
            "* **VIGOR:** 15 (+2)\n"
            "* **VONTADE:** 13 (+1)\n\n"
            "### Nível & XP\n"
            "* **Nível:** 2\n"
            "* **XP:** 350/1000\n"
        )
        npcs_md = (
            "# Personagens Não-Jogáveis (NPCs)\n\n"
            "### Bob O Guarda\n"
            "* **Atitude Atual:** Neutro\n"
            "* **Papel:** Soldado raso\n"
            "* **Local:** Fortaleza Vermelha\n\n"
            "### Malakor\n"
            "* **Atitude Atual:** Hostil\n"
            "* **Papel:** Comandante Renegado\n"
            "* **Local:** Acampamento Externo\n"
            "* **Vontade Própria:** Tomar o trono de ferro\n"
            "* **Fraqueza:** Arrogância estratégica\n"
            "* **Relações:** Rivalidade: 3\n"
        )
        mundo_md = (
            "# Mundo\n\n"
            "## Facções\n"
            "### Guarda de Malakor (MALAKOR)\n"
            "- Poder: 4\n"
            "- Reputação: -3\n"
        )
        regras_md = (
            "# Regras\n"
            "```yaml\n"
            "system: d20_3gates\n"
            "```\n"
        )

        (self.camp_dir / "diario.md").write_text(diario_md, encoding="utf-8")
        (self.camp_dir / "ficha.md").write_text(ficha_md, encoding="utf-8")
        (self.camp_dir / "npcs.md").write_text(npcs_md, encoding="utf-8")
        (self.camp_dir / "mundo.md").write_text(mundo_md, encoding="utf-8")
        (self.camp_dir / "regras.md").write_text(regras_md, encoding="utf-8")

        # Cria lote causal de eventos
        actor = ActorRef(kind="human", id="gm")
        ev0 = EventDraft(
            type="campaign.created",
            schema_version=1,
            actor=actor,
            game_time="01/10/300 08:00",
            game_time_sort=1,
            payload={
                "title": "Campanha Causal",
                "system": "d20_3gates",
                "calendar": "standard",
                "start_game_time": "01/10/300 08:00",
                "config_version": 1,
            },
            meta={"baseline": {"diario.md": diario_md, "ficha.md": ficha_md, "npcs.md": npcs_md, "mundo.md": mundo_md, "regras.md": regras_md}},
        )
        ev1 = make_npc_promoted_draft("malakor", "minor", "major", "01/10/300 08:00", 2, capabilities=["guerra"])
        ev2 = make_npc_plan_updated_draft(
            "malakor", "pln_golpe", "tomar_trono", "Golpe", [{"step_id": "s1", "description": "Cercar", "status": "in_progress"}],
            "active", "01/10/300 08:00", 3
        )
        ev3 = make_faction_updated_draft("MALAKOR", "Guarda de Malakor", "01/10/300 08:00", 4, leadership={"leader_id": "malakor"})
        ev4 = make_claim_registered_draft(
            claim_id="clm_tesouro",
            proposition={"subject": "torre", "predicate": "tesouro_secreto", "object": "existe"},
            claim_type="state",
            game_time="01/10/300 08:00",
            game_time_sort=5,
        )
        prov5 = ProvenanceRef(
            source_type="event",
            source_id="evt_04",
            channel="observation",
            acquired_at="01/10/300 08:00",
            acquired_at_sort=6,
            confidence=9000,
        )
        ev5 = make_knowledge_acquired_draft(
            record_id="knw_tesouro_01",
            holder=HolderRef("player", "player"),
            claim_id="clm_tesouro",
            game_time="01/10/300 08:00",
            game_time_sort=6,
            awareness="known",
            stance="believed",
            confidence=9000,
            provenance=[prov5],
            visibility="player_meta",
        )
        ev_rel = make_npc_relationship_updated_draft(
            "malakor", "Aemon", "01/10/300 08:30", 7, trust=-2, rivalry=2
        )
        ev_unk = make_claim_registered_draft(
            claim_id="clm_desconhecida",
            proposition={"subject": "artefato", "predicate": "localizacao", "object": "cripta"},
            claim_type="state",
            game_time="01/10/300 08:30",
            game_time_sort=7,
        )
        ev_sec_reg = make_claim_registered_draft(
            claim_id="clm_segredo_fac",
            proposition={"subject": "MALAKOR", "predicate": "conspiracao", "object": "ativa"},
            claim_type="state",
            game_time="01/10/300 08:35",
            game_time_sort=8,
        )
        ev_sec_acq = make_knowledge_acquired_draft(
            record_id="knw_segredo_01",
            holder=HolderRef("faction", "MALAKOR"),
            claim_id="clm_segredo_fac",
            game_time="01/10/300 08:35",
            game_time_sort=8,
            visibility="faction_internal",
            provenance=[prov5],
        )
        ev6 = EventDraft(
            type="turn.committed",
            schema_version=1,
            actor=actor,
            game_time="01/10/300 09:00",
            game_time_sort=9,
            payload={"turn": 1, "action": "Aemon vigia o portão", "summary": "Portão reforçado com barricadas de ferro.", "changes": []},
        )

        stored = self.store.append("ctx_camp", [ev0, ev1, ev2, ev3, ev4, ev5, ev_rel, ev_unk, ev_sec_reg, ev_sec_acq, ev6])
        self.ev6_id = stored.events[-1].event_id

        # Configura ambiente apontando CAMPAIGN_DIRS temporário
        from council import helpers
        self._orig_dirs = list(helpers.CAMPAIGN_DIRS)
        helpers.CAMPAIGN_DIRS = [self.camp_dir.parent]

        rebuild_projections(self.store, "ctx_camp", self.camp_dir, emit_audit_event=True)

    def tearDown(self) -> None:
        from council import helpers
        helpers.CAMPAIGN_DIRS = self._orig_dirs
        self.tmp.cleanup()

    def test_c01_core_content_and_deterministic_hash(self) -> None:
        """C01: payload contém core completo e context_hash estável entre execuções idênticas."""
        p1 = cmd_prepare("ctx_camp", action="Aemon observa o salão", no_roll=True)
        p2 = cmd_prepare("ctx_camp", action="Aemon observa o salão", no_roll=True)

        self.assertIn("context", p1)
        self.assertIn("context_hash", p1["context"])
        self.assertEqual(p1["context"]["context_hash"], p2["context"]["context_hash"])

        core_items = p1["context"]["core"]["items"]
        kinds = {i["kind"] for i in core_items}
        self.assertIn("ruleset", kinds)
        self.assertIn("protagonist", kinds)
        self.assertIn("scene", kinds)

    def test_c02_distant_antagonist_with_imminent_plan(self) -> None:
        """C02: Malakor (antagonista distante fora da cena) com plano ativo entra em causal.items."""
        res = cmd_prepare("ctx_camp", action="Aemon investiga conspirações", no_roll=True)
        causal_items = res["context"]["causal"]["items"]
        malakor = next((i for i in causal_items if i["id"] == "malakor"), None)

        self.assertIsNotNone(malakor, "Malakor deve entrar em causal.items por plano iminente/relevância")
        self.assertGreater(malakor["score"], 0)
        self.assertIn("plano_iminente", malakor["reasons"])
        self.assertIn("fora_de_cena", malakor["reasons"])

    def test_c03_presence_is_not_sufficiency(self) -> None:
        """C03: Bob O Guarda está presente na cena mas sem impacto causal, não entra em causal.items."""
        res = cmd_prepare("ctx_camp", action="Aemon afia sua espada", no_roll=True)
        causal_items = res["context"]["causal"]["items"]
        bob_causal = next((i for i in causal_items if "bob" in i["id"].lower()), None)
        self.assertIsNone(bob_causal, "Bob O Guarda não deve ser promovido a causal.items")

        # Bob deve permanecer no background_cast do briefing
        background = res["step_2_narrator_briefing"]["background_cast"]
        self.assertTrue(any("Bob" in b for b in background), "Bob deve constar em background_cast")

    def test_c04_audience_epistemic_isolation_and_no_player_meta_leak(self) -> None:
        """C04: player_meta é acessível ao player, mas inacessível/oculto ao protagonist, narrator e writer."""
        # Modo GM / Player
        p_player = cmd_prepare("ctx_camp", action="Procurar clm_tesouro", mode="gm", audience="player", no_roll=True)
        claims_player = [i["id"] for i in p_player["context"]["causal"]["items"] if i["kind"] == "claim"]
        self.assertIn("clm_tesouro", claims_player, "Player deve ter acesso a claim player_meta")

        # Modo Narrator / Protagonist
        p_narrator = cmd_prepare("ctx_camp", action="Procurar clm_tesouro", mode="narrator", no_roll=True)
        claims_narrator = [i["id"] for i in p_narrator["context"]["causal"]["items"] if i["kind"] == "claim"]
        self.assertNotIn("clm_tesouro", claims_narrator, "Narrator NUNCA deve receber claim player_meta!")

        # A claim deve constar em omissões com disponibilidade unavailable
        omissions = [o for o in p_narrator["context_omissions"] if o["reference"] == "clm_tesouro"]
        self.assertTrue(len(omissions) > 0)
        self.assertEqual(omissions[0]["availability"], "unavailable")

    def test_c05_facts_and_corrections(self) -> None:
        """C05: fato corrigido por correction.issued não entra como fato vigente e vira consequência."""
        # Emite uma correção sobre o turno 1 referenciando seu event_id
        actor = ActorRef(kind="human", id="gm")
        ev_corr = EventDraft(
            type="correction.issued",
            schema_version=1,
            actor=actor,
            game_time="01/10/300 09:30",
            game_time_sort=9,
            payload={
                "correction_id": "corr_01",
                "corrects": [self.ev6_id],
                "reason": "O portão foi reforçado com madeira, não ferro",
                "changes": [{"field": "summary", "old": "Portão de ferro", "new": "Portão de madeira"}],
            },
        )
        self.store.append("ctx_camp", [ev_corr])
        rebuild_projections(self.store, "ctx_camp", self.camp_dir, emit_audit_event=True)

        res = cmd_prepare("ctx_camp", action="Olhar o portão", no_roll=True)
        causal = res["context"]["causal"]["items"]

        # O fato original não deve estar como fato vigente
        fact_item = next((i for i in causal if i["kind"] == "fact" and ("Portão" in i["label"] or "Portão" in str(i["payload"]))), None)
        self.assertIsNone(fact_item, "Fato corrigido não pode figurar como fato vigente")

        # A correção deve entrar como consequência
        corr_item = next((i for i in causal if i["kind"] == "consequence" and "correction" in i["id"]), None)
        self.assertIsNotNone(corr_item, "A correção deve constar como consequência")

    def test_c06_strict_omissions_classification(self) -> None:
        """C06: classificação rigorosa de omissões (inexistent, unknown, unavailable)."""
        # 1. Inexistent: menção a claim e npc inexistentes no repositório
        res_inex = cmd_prepare("ctx_camp", action="Aemon pergunta por clm_fantasma e por npc_invisivel", no_roll=True)
        om_inex = {o["reference"]: o["availability"] for o in res_inex["context_omissions"]}
        self.assertEqual(om_inex.get("clm_fantasma"), "inexistent")
        self.assertEqual(om_inex.get("npc_invisivel"), "inexistent")

        # 2. Unknown: menção a claim registrada no mundo mas cujo conhecimento ninguém adquiriu
        res_unk = cmd_prepare("ctx_camp", action="Investigar clm_desconhecida", no_roll=True)
        om_unk = {o["reference"]: o["availability"] for o in res_unk["context_omissions"]}
        self.assertEqual(om_unk.get("clm_desconhecida"), "unknown")

        # 3. Unavailable: menção a player_meta em modo narrativo (oculto por sigilo epistêmico)
        res_unav = cmd_prepare("ctx_camp", action="Procurar clm_tesouro", mode="narrator", no_roll=True)
        om_unav = {o["reference"]: o["availability"] for o in res_unav["context_omissions"]}
        self.assertEqual(om_unav.get("clm_tesouro"), "unavailable")

    def test_c07_on_demand_query_service_and_visibility(self) -> None:
        """C07: ContextQueryService e CLI query respondem claim, npc, faction, quest e clock."""
        policy_gm = resolve_mode_policy("gm")
        service_gm = ContextQueryService("ctx_camp", self.camp_dir, audience=policy_gm.audience)

        q_npc = service_gm.npc("malakor")
        self.assertEqual(q_npc.availability, "known")
        self.assertEqual(q_npc.id, "malakor")

        q_fac = service_gm.faction("MALAKOR")
        self.assertEqual(q_fac.availability, "known")

        q_quest = service_gm.quest("Q1")
        self.assertEqual(q_quest.availability, "known")

        q_clock = service_gm.clock("Golpe da Guarda")
        self.assertEqual(q_clock.availability, "known")

        q_inexistent = service_gm.npc("npc_inexistente")
        self.assertEqual(q_inexistent.availability, "inexistent")

        # Teste de visibilidade na consulta: player_meta invisível para protagonista
        policy_pc = resolve_mode_policy("narrator")
        service_pc = ContextQueryService("ctx_camp", self.camp_dir, audience=policy_pc.audience)
        q_claim_pc = service_pc.claim("clm_tesouro")
        self.assertEqual(q_claim_pc.availability, "unavailable")

        # Exercita o parser e comando CLI 'query'
        from interfaces.cli.parser import build_cli
        parser = build_cli()
        args = parser.parse_args(["query", "--campaign", "ctx_camp", "--kind", "npc", "--id", "malakor", "--json"])
        self.assertEqual(args.cmd, "query")
        self.assertEqual(args.kind, "npc")
        self.assertEqual(args.id, "malakor")
        cli_res = service_gm.query(args.kind, args.id)
        self.assertEqual(cli_res.availability, "known")
        self.assertEqual(cli_res.id, "malakor")

        # Exercita a execução ponta a ponta de main() do CLI query
        import io
        import contextlib
        from interfaces.cli.main import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["query", "--campaign", "ctx_camp", "--kind", "npc", "--id", "malakor", "--json"])
        cli_out = json.loads(buf.getvalue())
        self.assertEqual(cli_out["kind"], "npc")
        self.assertEqual(cli_out["id"], "malakor")
        self.assertEqual(cli_out["availability"], "known")

    def test_c09_compatibility_and_determinism(self) -> None:
        """C09: chaves legadas preservadas, valores legados corretos e determinismo de hash com payload."""
        res = cmd_prepare("ctx_camp", action="Inspecionar área", no_roll=True)
        # Chaves legadas essenciais presentes
        for key in (
            "campaign", "system", "operation_mode", "next_turn_number", "canonical_header",
            "scene_type", "stakes", "is_critical_turn", "situational_pacing", "scheduled_scene",
            "protagonist", "step_1_quest_context", "step_1_faction_context", "step_1_gm_arbitration",
            "step_2_narrator_briefing", "step_3_writer_mandate", "step_4_post_turn_commit_template"
        ):
            self.assertIn(key, res, f"Chave legada '{key}' deve permanecer no payload")

        # Compara valores legados: alerta crítico de relógio presente no mandato de missão
        quest_mandate = res["step_1_quest_context"]["quest_pressure_mandate"]
        self.assertIn("ALERTA CRÍTICO: O relógio 'Golpe da Guarda'", quest_mandate)
        self.assertIn("a 1 passo da ruptura iminente", quest_mandate)

        # Chaves novas presentes
        self.assertIn("context_version", res)
        self.assertIn("source_last_seq", res)
        self.assertIn("context", res)
        self.assertIn("context_omissions", res)

        # Verifica determinismo de hash de seção com sensibilidade a mudanças de payload
        from application.context.assembler import _section_hash
        from contracts.context import ContextItem
        it_a = ContextItem("claim", "clm_t", "l", "causal", 100, ("r",), "known", {"stance": "believed"})
        it_b = ContextItem("claim", "clm_t", "l", "causal", 100, ("r",), "known", {"stance": "disbelieved"})
        hash_a = _section_hash((it_a,), ())
        hash_b = _section_hash((it_b,), ())
        self.assertNotEqual(hash_a, hash_b, "Mudança de payload DEVE alterar o hash de seção")

    def test_c10_modes_policies_and_r2_boundaries(self) -> None:
        """C10: matriz epistêmica de vazamento entre camadas (GM, Player, Protagonista)."""
        # 1. GM vê o universo (inclusive segredos de facção)
        p_gm = cmd_prepare("ctx_camp", action="Investigar clm_segredo_fac", mode="gm", no_roll=True)
        gm_claims = [i["id"] for i in p_gm["context"]["causal"]["items"] if i["kind"] == "claim"]
        self.assertIn("clm_segredo_fac", gm_claims, "GM deve ver alegações faction_internal")
        self.assertEqual(p_gm["context"]["audience"], "universe:gm")

        # 2. Narrador / Escritor é estritamente isolado da mente do jogador e de segredos internos
        p_narrator = cmd_prepare("ctx_camp", action="Investigar clm_segredo_fac e clm_tesouro", mode="narrator", no_roll=True)
        self.assertEqual(p_narrator["context"]["audience"], "protagonist:Aemon")
        self.assertEqual(p_narrator["context"]["purpose"], "narration")
        narr_claims = [i["id"] for i in p_narrator["context"]["causal"]["items"] if i["kind"] == "claim"]
        self.assertNotIn("clm_segredo_fac", narr_claims)
        self.assertNotIn("clm_tesouro", narr_claims)

        p_writer = cmd_prepare("ctx_camp", action="Avançar", mode="writer", no_roll=True)
        self.assertEqual(p_writer["context"]["audience"], "protagonist:Aemon")
        self.assertEqual(p_writer["context"]["purpose"], "prose")

        p_architect = cmd_prepare("ctx_camp", action="Avançar", mode="architect", no_roll=True)
        self.assertEqual(p_architect["context"]["audience"], "player:architect")
        self.assertEqual(p_architect["context"]["purpose"], "structure")


if __name__ == "__main__":
    unittest.main()
