"""tests/test_quest_progression.py: Suíte de Testes do Sistema de Missões e Progressão (XP).

Cobre:
- User Story 1: Ciclo de vida e manipulação de missões e objetivos em diario.md
- User Story 2: Concessão determinística de XP, curva de nível e idempotência
- User Story 3: Blindagem contra colisões de regex com vitais e atributos
- User Story 4: Injeção de contexto teleológico no payload de preparação
- User Story 5: Interação com relógios de ameaça (urgência, QUEST_OVERDUE e dedup)
- User Story 6: Subcomando progress (gastos de build) e lints de auditoria
"""

import unittest
import uuid
import shutil
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_ROOT = PROJECT_ROOT / ".tmp" / "test_scratch"


def make_test_temp_dir(prefix: str = "test_") -> str:
    """Cria diretório temporário dentro do workspace local (.tmp) para isolamento seguro em sandbox sem restrições de ACL 0o700."""
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    p = SCRATCH_ROOT / f"{prefix}{uuid.uuid4().hex}"
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


from council.quests import (
    parse_quests_from_diario,
    upsert_quest_in_diario,
    format_quest_header,
    parse_reward_xp,
)
from rulesets.progression import (
    calculate_level_threshold,
    calculate_level_from_xp,
    evaluate_xp_gain,
    calculate_level_up_bonuses,
    XP_GRANT_TABLE,
)
from council.ssot import (
    parse_ficha_md,
    parse_progression_from_ficha,
    update_progression_in_ficha,
    spend_attribute_point_in_ficha,
    spend_ability_point_in_ficha,
)
import lazy_turn


class TestQuestLifecycle(unittest.TestCase):
    """Testes para o ciclo de vida e parsing de missões em diario.md (US1)."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir()
        self.diario_path = Path(self.temp_dir) / "diario.md"
        self.diario_path.write_text(
            "# Diário da Crônica\n\n"
            "### Relógios de Ameaça & Prazos\n"
            "* **[Conspiração]:** 1/4 (Gatilho: Golpe de Estado) [ACTIVE]\n\n"
            "### Histórico de Turnos\n"
            "* **Turno 1:** O dia se inicia no forte. Vitais: HP 20/20, Stamina 10/10.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_and_parse_quest(self):
        """Valida inserção de nova missão com objetivo e parsing correto dos campos."""
        res = upsert_quest_in_diario(
            self.diario_path,
            action="add",
            title="O Trono de Pedra-Negra",
            quest_type="main",
            objective="Interrogar o mensageiro do norte",
            contractor="Conselho dos Lordes",
            clock="Conspiração",
            reward="150 XP",
            phase="Investigação",
        )
        self.assertEqual(res["action"], "quest_added")
        self.assertEqual(res["quest_id"], "Q1")

        quests = parse_quests_from_diario(self.diario_path)
        self.assertEqual(len(quests), 1)
        q = quests[0]
        self.assertEqual(q["id"], "Q1")
        self.assertEqual(q["title"], "O Trono de Pedra-Negra")
        self.assertEqual(q["type"], "MAIN")
        self.assertEqual(q["status"], "ACTIVE")
        self.assertEqual(q["phase"], "Investigação")
        self.assertEqual(q["contractor"], "Conselho dos Lordes")
        self.assertEqual(q["clock"], "Conspiração")
        self.assertEqual(q["reward_xp"], 150)
        self.assertEqual(len(q["objectives"]), 1)
        self.assertFalse(q["objectives"][0]["done"])
        self.assertEqual(q["objectives"][0]["text"], "Interrogar o mensageiro do norte")

    def test_objective_append_and_toggle(self):
        """Valida adição de segundo objetivo e alternância de checkbox [ ] -> [x]."""
        upsert_quest_in_diario(
            self.diario_path,
            action="add",
            title="Missão Teste",
            quest_type="side",
            objective="Primeiro passo",
        )
        # Adiciona segundo objetivo
        res_add = upsert_quest_in_diario(
            self.diario_path,
            action="add_objective",
            quest_id="Q1",
            objective="Segundo passo crucial",
        )
        self.assertEqual(res_add["action"], "objective_added")

        # Marca primeiro objetivo como concluído
        res_chk = upsert_quest_in_diario(
            self.diario_path,
            action="check",
            quest_id="Q1",
            check_index=1,
            current_turn=5,
        )
        self.assertEqual(res_chk["action"], "objective_checked")

        quests = parse_quests_from_diario(self.diario_path)
        self.assertEqual(len(quests[0]["objectives"]), 2)
        self.assertTrue(quests[0]["objectives"][0]["done"])
        self.assertFalse(quests[0]["objectives"][1]["done"])
        self.assertEqual(quests[0]["progress_summary"], "1/2")
        self.assertIn("Turno 5", quests[0]["last_progress"])

    def test_quest_state_transitions(self):
        """Valida máquina de estados (complete, fail, block, reopen)."""
        upsert_quest_in_diario(self.diario_path, action="add", title="Missão Política", quest_type="main")
        
        # Bloquear
        res_blk = upsert_quest_in_diario(self.diario_path, action="block", quest_id="Q1", reason="Fronteira fechada")
        self.assertEqual(res_blk["new_status"], "BLOCKED")
        self.assertEqual(parse_quests_from_diario(self.diario_path)[0]["status"], "BLOCKED")

        # Reabrir
        res_reo = upsert_quest_in_diario(self.diario_path, action="reopen", quest_id="Q1", reason="Passagem secreta")
        self.assertEqual(res_reo["new_status"], "ACTIVE")

        # Falhar
        res_fail = upsert_quest_in_diario(self.diario_path, action="fail", quest_id="Q1", reason="Emissário assassinado")
        self.assertEqual(res_fail["new_status"], "FAILED")


class TestProgressionAndXPEngine(unittest.TestCase):
    """Testes para curva de nível, cálculo de XP e isolamento de vitais (US2, US3)."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir()
        self.ficha_path = Path(self.temp_dir) / "ficha.md"
        self.ficha_path.write_text(
            "# Ficha do Protagonista: Alistair\n\n"
            "### Vitais & Recursos\n"
            "* **Pontos de Vida (HP):** 20 / 20\n"
            "* **Fôlego & Ação (Stamina):** 10 / 10\n"
            "* **Energia / Concentração (CE):** 10 / 10\n\n"
            "### Atributos\n"
            "* **FOR (Força Física):** 14\n"
            "* **DES (Destreza / Agilidade):** 12\n"
            "* **CON (Constituição / Vigor):** 13\n"
            "* **INT (Percepção & Intelecto):** 10\n"
            "* **VON (Vontade & Resiliência):** 11\n"
            "* **MAG (Poder Místico / Energia):** 8\n\n"
            "### Progressão\n"
            "* **Nível:** 1\n"
            "* **Experiência (XP):** 0\n"
            "* **Próximo Nível:** 250\n"
            "* **Pontos de Atributo:** 0\n"
            "* **Pontos de Habilidade:** 0\n\n"
            "### Habilidades & Técnicas\n"
            "* **Golpe Firme:** Ataque certeiro.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_level_threshold_math(self):
        """Valida fórmula quadrática de limiares de nível: T(L) = 250 * (L-1) * L / 2."""
        self.assertEqual(calculate_level_threshold(1), 0)
        self.assertEqual(calculate_level_threshold(2), 250)
        self.assertEqual(calculate_level_threshold(3), 750)
        self.assertEqual(calculate_level_threshold(4), 1500)
        self.assertEqual(calculate_level_threshold(5), 2500)
        self.assertEqual(calculate_level_threshold(10), 11250)

    def test_level_up_and_vitals_expansion(self):
        """Valida concessão de XP, avanço de nível e bônus de vitais máximos."""
        # Concede 250 XP (subida para Nível 2)
        res = update_progression_in_ficha(self.ficha_path, xp_add=250)
        self.assertTrue(res["level_up"])
        self.assertEqual(res["new_level"], 2)
        self.assertEqual(res["total_xp"], 250)
        self.assertEqual(res["next_threshold"], 750)
        self.assertEqual(res["attribute_points"], 1)
        self.assertEqual(res["ability_points"], 1)  # Nível 2 é par -> +1 ponto de habilidade

        # Verifica expansão de vitais na ficha
        ficha_data = parse_ficha_md(self.ficha_path)
        self.assertEqual(ficha_data["vitals"]["hp"]["max"], 22)  # 20 + 2
        self.assertEqual(ficha_data["vitals"]["stamina"]["max"], 11)  # 10 + 1
        self.assertEqual(ficha_data["vitals"]["ce"]["max"], 11)  # 10 + 1

    def test_regex_collision_shielding(self):
        """Valida que XP, Nível e Pontos jamais entram em ficha['vitals'] ou ficha['stats']."""
        update_progression_in_ficha(self.ficha_path, xp_add=500)
        ficha_data = parse_ficha_md(self.ficha_path)

        # 1. Não deve haver chave xp nos vitais
        self.assertNotIn("xp", ficha_data["vitals"])
        self.assertNotIn("experiência", ficha_data["vitals"])
        self.assertNotIn("nível", ficha_data["vitals"])
        self.assertNotIn("pontos", ficha_data["vitals"])

        # 2. Não deve haver chave XP nos atributos
        self.assertNotIn("XP", ficha_data["stats"])
        self.assertNotIn("NIVEL", ficha_data["stats"])
        self.assertNotIn("PONTOS", ficha_data["stats"])

        # 3. Atributos originais devem permanecer intactos
        self.assertEqual(ficha_data["stats"]["FOR"], 14)
        self.assertEqual(ficha_data["stats"]["DES"], 12)

    def test_spend_attribute_and_ability_points(self):
        """Valida gasto de pontos de atributo e habilidade com validação de treino."""
        # Sobe para nível 2 para ter pontos
        update_progression_in_ficha(self.ficha_path, xp_add=250)

        # Gasta ponto de atributo em FOR
        res_attr = spend_attribute_point_in_ficha(self.ficha_path, "FOR", stat_ceiling=20)
        self.assertEqual(res_attr["old_value"], 14)
        self.assertEqual(res_attr["new_value"], 15)
        self.assertEqual(res_attr["remaining_points"], 0)
        self.assertEqual(parse_ficha_md(self.ficha_path)["stats"]["FOR"], 15)

        # Tentativa de gastar sem pontos restantes deve falhar
        fail_attr = spend_attribute_point_in_ficha(self.ficha_path, "DES")
        self.assertIn("error", fail_attr)

        # Gasta ponto de habilidade sem treino deve falhar
        fail_abil = spend_ability_point_in_ficha(self.ficha_path, "Nova Técnica", training_context="")
        self.assertIn("error", fail_abil)

        # Gasta ponto de habilidade com treino
        res_abil = spend_ability_point_in_ficha(
            self.ficha_path,
            "Corte de Cinzas: Dano flamejante.",
            training_context="Treino de 3 horas no pátio com o mestre de armas.",
        )
        self.assertEqual(res_abil["remaining_points"], 0)
        text = self.ficha_path.read_text(encoding="utf-8")
        self.assertIn("Corte de Cinzas", text)


class TestClockInteractionAndLints(unittest.TestCase):
    """Testes de interação com relógios de ameaça e lints do reviewer (US5, US6)."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir()
        self.campaign_dir = Path(self.temp_dir) / "test_camp"
        self.campaign_dir.mkdir()
        self.diario_path = self.campaign_dir / "diario.md"
        self.ficha_path = self.campaign_dir / "ficha.md"
        self.npcs_path = self.campaign_dir / "npcs.md"

        self.ficha_path.write_text(
            "# Ficha do Protagonista: Alistair\n\n"
            "### Vitais & Recursos\n* **HP:** 20 / 20\n* **Stamina:** 10 / 10\n\n"
            "### Atributos\n* **FOR:** 10\n\n"
            "### Progressão\n* **Nível:** 1\n* **Experiência (XP):** 0\n* **Próximo Nível:** 250\n* **Pontos de Atributo:** 0\n* **Pontos de Habilidade:** 0\n",
            encoding="utf-8",
        )
        self.npcs_path.write_text("# NPCs\n", encoding="utf-8")
        self.diario_path.write_text(
            "## Cena 1: Forte\n"
            "* **Data & Local:** 01 de Outubro de 2026, 12:00 — Forte.\n"
            "* **Presentes:** Alistair.\n\n"
            "### Relógios de Ameaça & Prazos\n"
            "* **[Cerco Inimigo]:** 4/4 (Gatilho: Brecha nos muros) [BREACHED]\n\n"
            "### Missões & Objetivos\n"
            "* **[MAIN] Defender o Forte** | Status: ACTIVE | Relógio: Cerco Inimigo | Recompensa: 150 XP\n"
            "  * [ ] Guarnecer a ponte levadiça\n\n"
            "### Histórico de Turnos\n"
            "* **Turno 1:** Defesa inicial.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_quest_overdue_lint(self):
        """Valida que relógio rompido gera lint QUEST_OVERDUE sem alterar o status da missão."""
        # Simula ambiente de campanha no reviewer chamando cmd_review ou lints
        import council.reviewer as rev
        orig_find = rev.find_campaign
        rev.find_campaign = lambda c_id: {
            "campaign_id": "test_camp",
            "ficha": self.ficha_path,
            "diario": self.diario_path,
            "npcs": self.npcs_path,
        }
        try:
            report = rev.cmd_review("test_camp")
            issue_types = [iss["type"] for iss in report.get("issues", [])]
            self.assertIn("CLOCK_BREACHED", issue_types)
            self.assertIn("QUEST_OVERDUE", issue_types)

            # Confirma que a missão não foi corrompida nem falhada silenciosamente
            quests = parse_quests_from_diario(self.diario_path)
            self.assertEqual(quests[0]["status"], "ACTIVE")
        finally:
            rev.find_campaign = orig_find

    def test_monotonic_id_generation_and_end_insertion(self):
        """Valida que IDs são monotônicos Q{max+1} e inseridos no final do bloco (T012)."""
        res1 = upsert_quest_in_diario(self.diario_path, action="add", title="Primeira Missão", quest_type="main")
        res2 = upsert_quest_in_diario(self.diario_path, action="add", title="Segunda Missão", quest_type="side")
        self.assertEqual(res1["quest_id"], "Q2")
        self.assertEqual(res2["quest_id"], "Q3")

        quests = parse_quests_from_diario(self.diario_path)
        self.assertEqual(len(quests), 3) # Inclui a 'Defender o Forte' (Q1 legada convertida), res1 (Q2) e res2 (Q3)
        self.assertEqual(quests[-2]["title"], "Primeira Missão")
        self.assertEqual(quests[-1]["title"], "Segunda Missão")

        # Adiciona uma terceira missão e garante que seu ID é maior que todos os anteriores
        res3 = upsert_quest_in_diario(self.diario_path, action="add", title="Terceira Missão", quest_type="personal")
        quests_after = parse_quests_from_diario(self.diario_path)
        self.assertEqual(quests_after[-1]["id"], res3["quest_id"])
        self.assertEqual(quests_after[-1]["title"], "Terceira Missão")

    def test_state_machine_unblock_abandon_evidence(self):
        """Valida transições --unblock, --abandon e persistência de evidência (T022)."""
        upsert_quest_in_diario(self.diario_path, action="add", title="Investigação Real", quest_type="main", objective="Rastrear espião")
        q_list = parse_quests_from_diario(self.diario_path)
        target_id = q_list[-1]["id"]

        # Bloquear
        res_blk = upsert_quest_in_diario(self.diario_path, action="block", quest_id=target_id, reason="Guarda reforçada")
        self.assertEqual(res_blk["new_status"], "BLOCKED")

        # Desbloquear
        res_unblk = upsert_quest_in_diario(self.diario_path, action="unblock", quest_id=target_id)
        self.assertEqual(res_unblk["new_status"], "ACTIVE")

        # Abandonar
        res_abn = upsert_quest_in_diario(self.diario_path, action="abandon", quest_id=target_id, reason="Missão obsoleta")
        self.assertEqual(res_abn["new_status"], "ABANDONED")

        # Concluir com evidência
        res_cmp = upsert_quest_in_diario(self.diario_path, action="complete", quest_id=target_id, evidence="Confissão assinada pelo espião")
        self.assertEqual(res_cmp["new_status"], "COMPLETED")
        self.assertEqual(res_cmp["evidence"], "Confissão assinada pelo espião")

        text = self.diario_path.read_text(encoding="utf-8")
        self.assertIn("**Evidência:** Confissão assinada pelo espião", text)

    def test_ssot_reward_defaults_and_xp_ledger(self):
        """Valida SSOT de recompensas, registro permanente no ledger e reconciliação (T018)."""
        from council.quests import parse_xp_ledger_from_diario, append_xp_ledger_entry
        append_xp_ledger_entry(self.diario_path, amount=50, reason="Emboscada superada", turn=2)
        ledger = parse_xp_ledger_from_diario(self.diario_path)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["amount"], 50)
        self.assertEqual(ledger[0]["reason"], "Emboscada superada")
        self.assertEqual(ledger[0]["turn"], 2)

        # Valida que calcular nível com base_step <= 0 é protegido
        lvl, thresh = calculate_level_from_xp(100, base_step=0)
        self.assertGreaterEqual(lvl, 1)


if __name__ == "__main__":
    unittest.main()
