"""tests/test_factions_reputation.py: Suíte de Testes de Facções, Reputação Numérica e Turno Off-Screen (Fase 3).

Cobre:
- User Story 1: Cadastro e parsing de facções em mundo.md com Poder, Escala e Relógio
- User Story 2: Reputação numérica (-3 a +3), favores/débitos e ledger em diario.md
- User Story 3: Automação de contratos em commit (--quest-complete e --quest-fail) e mutações manuais
- User Story 4: Injeção de step_1_faction_context no payload de prepare
- User Story 5: Simulação off-screen de avanço de relógios de facções (faction --tick)
- User Story 6: Lints determinísticos de integridade (FACTION_UNKNOWN, FACTION_ORPHANED_NPC, FACTION_ATTITUDE_DESYNC, FACTION_REP_MISMATCH)
"""

import unittest
import uuid
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_ROOT = PROJECT_ROOT / ".tmp" / "test_scratch"


def make_test_temp_dir(prefix: str = "test_fac_") -> Path:
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    p = SCRATCH_ROOT / f"{prefix}{uuid.uuid4().hex}"
    p.mkdir(parents=True, exist_ok=True)
    return p


import council.helpers as helpers
from council.factions import (
    clamp_reputation,
    score_to_tier_name,
    legacy_label_to_score,
    parse_factions_from_mundo,
    upsert_faction_in_mundo,
    parse_reputation_from_ficha,
    update_reputation_in_ficha,
    parse_faction_ledger_from_diario,
    append_faction_ledger_entry,
    simulate_faction_tick,
    resolve_scene_factions,
)
from council.ssot import parse_diario_md
import council.reviewer as rev
import lazy_turn


class TestFactionMundoParsingAndUpsert(unittest.TestCase):
    """US1: Cadastro e parsing de facções em mundo.md."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir("mundo_")
        self.mundo_path = self.temp_dir / "mundo.md"
        self.mundo_path.write_text(
            "# O Mundo e o Cenário\n\n"
            "## 1. Geografia & Locais\n"
            "Terras áridas e fortalezas de pedra.\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n\n"
            "- **[CONSELHO_LORDES] Conselho dos Lordes de Cinzas** (Poder: 4, Escala: regional, Relógio: Conspiração da Corte) — Nobres tradicionalistas.\n"
            "* **[GUARDA_NOITE] A Guarda da Meia-Noite:** Tropa veterana de choque | Poder: 3 | Escala: local | Relógio: Golpe Militar\n\n"
            "## 5. Mistérios e Rumores\n"
            "Rumores sobre o retorno das sombras.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_factions_from_mundo(self):
        factions = parse_factions_from_mundo(self.mundo_path)
        self.assertEqual(len(factions), 2)
        c = factions[0]
        self.assertEqual(c["tag"], "CONSELHO_LORDES")
        self.assertEqual(c["name"], "Conselho dos Lordes de Cinzas")
        self.assertEqual(c["power"], 4)
        self.assertEqual(c["scale"], "regional")
        self.assertEqual(c["clock"], "Conspiração da Corte")
        self.assertIn("Nobres tradicionalistas", c["description"])

    def test_upsert_faction_in_mundo_new(self):
        res = upsert_faction_in_mundo(
            self.mundo_path,
            name="Guilda dos Mercadores Livres",
            tag="GUILDA_MERCADORES",
            power=2,
            scale="urbano",
            clock="Monopólio Comercial",
            desc="Controlam as caravanas.",
        )
        self.assertEqual(res["action"], "faction_added")
        factions = parse_factions_from_mundo(self.mundo_path)
        self.assertEqual(len(factions), 3)
        tags = [f["tag"] for f in factions]
        self.assertIn("GUILDA_MERCADORES", tags)

    def test_upsert_faction_in_mundo_update(self):
        res = upsert_faction_in_mundo(
            self.mundo_path,
            name="A Guarda da Meia-Noite",
            power=5,
            scale="continental",
            desc="Exército fortalecido após aliança.",
        )
        self.assertEqual(res["action"], "faction_updated")
        factions = parse_factions_from_mundo(self.mundo_path)
        g = next(f for f in factions if f["name"] == "A Guarda da Meia-Noite")
        self.assertEqual(g["power"], 5)
        self.assertEqual(g["scale"], "continental")
        self.assertIn("Exército fortalecido", g["description"])

    def test_legacy_tolerance(self):
        legacy_path = self.temp_dir / "legacy_mundo.md"
        legacy_path.write_text(
            "# Mundo Antigo\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n"
            "* Clã da Montanha: Guerreiros nômades do norte.\n"
            "* Ordem Solitária: Monges ermitões.\n",
            encoding="utf-8",
        )
        factions = parse_factions_from_mundo(legacy_path)
        self.assertEqual(len(factions), 2)
        self.assertEqual(factions[0]["power"], 3)  # default power


class TestFactionFichaAndLedger(unittest.TestCase):
    """US2: Reputação numérica, clamping, favores, débitos e ledger."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir("ficha_")
        self.ficha_path = self.temp_dir / "ficha.md"
        self.diario_path = self.temp_dir / "diario.md"

        self.ficha_path.write_text(
            "# Ficha do Protagonista\n\n"
            "### Atributos & Estatísticas\n"
            "- **FOR:** 14 (+2)\n\n"
            "### Vínculos, Laços & Matriz Relacional\n"
            "* **Reputação com Facções:**\n"
            "  * **Conselho dos Lordes:** +1 (Amigável) | Favores: 2 | Débitos: 0\n"
            "  * **A Guarda da Meia-Noite:** -2 (Hostil) | Favores: 0 | Débitos: 1\n",
            encoding="utf-8",
        )

        self.diario_path.write_text(
            "# Diário\n\n"
            "## Cabeçalho da Cena Ativa\n"
            "* **Data & Local:** 01/10/2026, 12:00 | Fortaleza\n"
            "* **Presentes:** Protagonista\n\n"
            "### Registro de Reputação & Facções\n"
            "* **[Turno 1]** Conselho dos Lordes: +1 Reputação (0 -> +1 [Amigável]) | Favores: +2 | Motivo: Entrega de suprimentos\n"
            "* **[Turno 1]** A Guarda da Meia-Noite: -2 Reputação (0 -> -2 [Hostil]) | Débitos: +1 | Motivo: Quebra de cessar-fogo\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_reputation_from_ficha(self):
        reps = parse_reputation_from_ficha(self.ficha_path)
        self.assertIn("conselho dos lordes", reps)
        self.assertEqual(reps["conselho dos lordes"]["score"], 1)
        self.assertEqual(reps["conselho dos lordes"]["favors"], 2)
        self.assertEqual(reps["conselho dos lordes"]["debts"], 0)

        self.assertIn("a guarda da meia-noite", reps)
        self.assertEqual(reps["a guarda da meia-noite"]["score"], -2)
        self.assertEqual(reps["a guarda da meia-noite"]["debts"], 1)

    def test_update_reputation_clamping_and_non_negative(self):
        # Clamp upper at +3
        res = update_reputation_in_ficha(self.ficha_path, "Conselho dos Lordes", score_delta=5, favors_delta=-5)
        self.assertEqual(res["new_score"], 3)
        self.assertEqual(res["new_tier"], "Venerado")
        self.assertEqual(res["favors"], 0)  # clamped at 0, cannot be negative

        # Clamp lower at -3
        res2 = update_reputation_in_ficha(self.ficha_path, "A Guarda da Meia-Noite", score_delta=-5, debts_delta=2)
        self.assertEqual(res2["new_score"], -3)
        self.assertEqual(res2["new_tier"], "Jurado de Morte")
        self.assertEqual(res2["debts"], 3)

    def test_append_faction_ledger_entry(self):
        append_faction_ledger_entry(
            self.diario_path,
            faction_name="Conselho dos Lordes",
            delta_rep=1,
            new_score=2,
            reason="Resgate de emissário",
            turn=2,
            delta_favors=1,
        )
        ledger = parse_faction_ledger_from_diario(self.diario_path)
        self.assertEqual(len(ledger), 3)
        last = ledger[-1]
        self.assertEqual(last["faction"], "Conselho dos Lordes")
        self.assertEqual(last["delta_rep"], 1)
        self.assertEqual(last["delta_favors"], 1)
        self.assertEqual(last["turn"], 2)


class TestFactionCommitAutomation(unittest.TestCase):
    """US3: Automação de contratos em commit (--quest-complete e --quest-fail) e mutações manuais."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir("commit_")
        self.camps_dir = self.temp_dir / "campaigns"
        self.camp_dir = self.camps_dir / "test_camp"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        helpers.CAMPAIGN_DIRS.insert(0, self.camps_dir)

        self.ficha_path = self.camp_dir / "ficha.md"
        self.diario_path = self.camp_dir / "diario.md"
        self.mundo_path = self.camp_dir / "mundo.md"
        self.npcs_path = self.camp_dir / "npcs.md"
        self.regras_path = self.camp_dir / "regras.md"

        self.ficha_path.write_text(
            "# Ficha\n\n"
            "### Recursos Vitais\n"
            "- **HP:** 20/20\n\n"
            "### Progressão & Nível\n"
            "- **Nível:** 1\n"
            "- **Experiência (XP):** 0 / 250\n"
            "- **Pontos de Atributo:** 0\n"
            "- **Pontos de Habilidade:** 0\n\n"
            "### Vínculos, Laços & Matriz Relacional\n"
            "* **Reputação com Facções:**\n"
            "  * **Conselho dos Lordes:** +1 (Amigável) | Favores: 0 | Débitos: 0\n",
            encoding="utf-8",
        )

        self.mundo_path.write_text(
            "# Mundo\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n"
            "- **[CONSELHO_LORDES] Conselho dos Lordes** (Poder: 4, Escala: regional) — Nobres.\n",
            encoding="utf-8",
        )

        self.npcs_path.write_text(
            "# NPCs\n\n"
            "### Lorde Aemon\n"
            "* **Facção / Afiliação:** Conselho dos Lordes\n"
            "* **Atitude Atual:** Amigável\n"
            "* **Vontade Própria:** Proteger os nobres.\n"
            "* **Fraquezas:** Orgulho.\n",
            encoding="utf-8",
        )

        self.regras_path.write_text("# Regras\nsystem: d20_3gates\n", encoding="utf-8")

        self.diario_path.write_text(
            "# Diário\n<!-- schema_version: 1 -->\n\n"
            "## Cabeçalho da Cena Ativa\n"
            "* **Data & Local:** 01/10/2026, 12:00 | Grande Salão\n"
            "* **Presentes:** Protagonista, Lorde Aemon\n\n"
            "## Relógios Narrativos (Ameaças & Prazos)\n"
            "- [ ] Defesa da Corte: 1/4 [ACTIVE] -> Gatilho: Invasão.\n\n"
            "### Missões & Objetivos Ativos\n"
            "* **[Q1] [MAIN] Recuperar os Selos Perdidos** | Status: ACTIVE | Contratante: Conselho dos Lordes | Recompensa: 150 XP\n"
            "  * [ ] 1. Encontrar o cofre na fortaleza\n\n"
            "### Histórico de Turnos & Cenas\n\n"
            "#### Turno 1 (01/10/2026, 12:00)\n"
            "* **Vitais:** HP: 20/20\n"
            "* **Resumo:** Chegada à fortaleza.\n\n"
            "### Registro de Experiência\n\n"
            "### Registro de Reputação & Facções\n"
            "* **[Turno 1]** Conselho dos Lordes: +1 Reputação (0 -> +1 [Amigável]) | Favores: 0 | Motivo: Apresentação formal\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.camps_dir in helpers.CAMPAIGN_DIRS:
            helpers.CAMPAIGN_DIRS.remove(self.camps_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_commit_quest_complete_contractor(self):
        res = lazy_turn.cmd_commit(
            campaign_id="test_camp",
            summary="Recuperou com sucesso os selos do cofre.",
            quest_complete="Q1",
        )

        reps = parse_reputation_from_ficha(self.ficha_path)
        c = reps["conselho dos lordes"]
        self.assertEqual(c["score"], 2)  # +1 from 1 -> 2
        self.assertEqual(c["tier"], "Aliado")
        self.assertEqual(c["favors"], 1)  # +1 favor

        ledger = parse_faction_ledger_from_diario(self.diario_path)
        self.assertEqual(len(ledger), 2)
        self.assertEqual(ledger[-1]["delta_rep"], 1)
        self.assertEqual(ledger[-1]["delta_favors"], 1)
        self.assertIn("Cumprimento de missão contratada (Q1)", ledger[-1]["reason"])

    def test_commit_quest_fail_contractor(self):
        res = lazy_turn.cmd_commit(
            campaign_id="test_camp",
            summary="Os selos foram destruídos irremediavelmente.",
            quest_fail="Q1:Destruição dos selos",
        )

        reps = parse_reputation_from_ficha(self.ficha_path)
        c = reps["conselho dos lordes"]
        self.assertEqual(c["score"], 0)  # -1 from 1 -> 0
        self.assertEqual(c["tier"], "Neutro")
        self.assertEqual(c["debts"], 1)  # +1 debt

        ledger = parse_faction_ledger_from_diario(self.diario_path)
        self.assertEqual(len(ledger), 2)
        self.assertEqual(ledger[-1]["delta_rep"], -1)
        self.assertEqual(ledger[-1]["delta_debts"], 1)

    def test_commit_manual_faction_mutations(self):
        res = lazy_turn.cmd_commit(
            campaign_id="test_camp",
            summary="Concedeu favores especiais e estreitou aliança.",
            faction_rep="Conselho dos Lordes:+1",
            faction_favor="Conselho dos Lordes:+2",
            faction_debt="Conselho dos Lordes:+0",
        )

        reps = parse_reputation_from_ficha(self.ficha_path)
        c = reps["conselho dos lordes"]
        self.assertEqual(c["score"], 2)
        self.assertEqual(c["favors"], 2)


class TestFactionPrepareAndContext(unittest.TestCase):
    """US4: Injeção de step_1_faction_context no prepare."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir("prep_")
        self.camps_dir = self.temp_dir / "campaigns"
        self.camp_dir = self.camps_dir / "test_prep"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        helpers.CAMPAIGN_DIRS.insert(0, self.camps_dir)

        self.ficha_path = self.camp_dir / "ficha.md"
        self.diario_path = self.camp_dir / "diario.md"
        self.mundo_path = self.camp_dir / "mundo.md"
        self.npcs_path = self.camp_dir / "npcs.md"
        self.regras_path = self.camp_dir / "regras.md"

        self.ficha_path.write_text(
            "# Ficha\n\n"
            "### Recursos Vitais\n"
            "- **HP:** 20/20\n\n"
            "### Atributos & Estatísticas\n"
            "- **FOR:** 14 (+2)\n"
            "- **CAR:** 10 (+0)\n\n"
            "### Vínculos, Laços & Matriz Relacional\n"
            "* **Reputação com Facções:**\n"
            "  * **Culto da Sombra:** -2 (Hostil) | Favores: 0 | Débitos: 2\n",
            encoding="utf-8",
        )

        self.mundo_path.write_text(
            "# Mundo\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n"
            "- **[CULTO_SOMBRA] Culto da Sombra** (Poder: 4, Escala: regional) — Fanáticos das trevas.\n",
            encoding="utf-8",
        )

        self.npcs_path.write_text(
            "# NPCs\n\n"
            "### Malakar o Sombrio\n"
            "* **Facção / Afiliação:** Culto da Sombra\n"
            "* **Atitude Atual:** Hostil\n"
            "* **Vontade Própria:** Eliminar forasteiros.\n"
            "* **Fraquezas:** Intolerância ao fracasso.\n",
            encoding="utf-8",
        )

        self.regras_path.write_text("# Regras\nsystem: d20_3gates\n", encoding="utf-8")

        self.diario_path.write_text(
            "# Diário\n<!-- schema_version: 1 -->\n\n"
            "## Cabeçalho da Cena Ativa\n"
            "* **Data & Local:** 01/10/2026, 12:00 | Cripta Sombria\n"
            "* **Presentes:** Protagonista, Malakar o Sombrio\n\n"
            "## Relógios Narrativos (Ameaças & Prazos)\n"
            "- [ ] Ascensão das Trevas: 1/4 [ACTIVE] -> Gatilho: Apocalipse.\n\n"
            "### Histórico de Turnos & Cenas\n\n"
            "#### Turno 1 (01/10/2026, 12:00)\n"
            "* **Vitais:** HP: 20/20\n"
            "* **Resumo:** Encontro inicial.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.camps_dir in helpers.CAMPAIGN_DIRS:
            helpers.CAMPAIGN_DIRS.remove(self.camps_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_step_1_faction_context_in_prepare(self):
        prep = lazy_turn.cmd_prepare(
            campaign_id="test_prep",
            action="Tentar negociar a passagem",
            no_roll=True,
        )

        self.assertIn("step_1_faction_context", prep)
        fac_ctx = prep["step_1_faction_context"]
        self.assertIn("factions_in_scene", fac_ctx)
        f_in_s = fac_ctx["factions_in_scene"]
        self.assertEqual(len(f_in_s), 1)
        cult = f_in_s[0]
        self.assertEqual(cult["tag"], "CULTO_SOMBRA")
        self.assertEqual(cult["score"], -2)
        self.assertEqual(cult["tier"], "Hostil")
        self.assertEqual(cult["social_dc_mod"], 3)  # +3 DC penalty for hostile
        self.assertEqual(cult["suggested_variant"], "disadvantage")
        self.assertIn("Malakar o Sombrio", cult["members_in_scene"])
        self.assertIn("POSTURA OBRIGATÓRIA DE FACÇÃO HOSTIL", cult["writer_directive"])


class TestFactionOffScreenTick(unittest.TestCase):
    """US5: Simulação off-screen de avanço de relógios de facções (faction --tick)."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir("tick_")
        self.camp_dir = self.temp_dir / "campaigns" / "test_tick"
        self.camp_dir.mkdir(parents=True, exist_ok=True)

        self.ficha_path = self.camp_dir / "ficha.md"
        self.diario_path = self.camp_dir / "diario.md"
        self.mundo_path = self.camp_dir / "mundo.md"
        self.npcs_path = self.camp_dir / "npcs.md"
        self.regras_path = self.camp_dir / "regras.md"

        self.ficha_path.write_text("# Ficha\n", encoding="utf-8")
        self.npcs_path.write_text("# NPCs\n", encoding="utf-8")
        self.regras_path.write_text("# Regras\n", encoding="utf-8")

        self.mundo_path.write_text(
            "# Mundo\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n"
            "- **[IMPERIO] Império do Ferro** (Poder: 4, Escala: regional, Relógio: Invasão da Fronteira) — Conquistadores.\n"
            "- **[CULTISTAS] Cultistas Ocultos** (Poder: 2, Escala: local, Relógio: Ritual Menor) — Pequeno círculo.\n"
            "- **[ORDEM_SOL] Ordem da Alvorada** (Poder: 5, Escala: continental, Relógio: Cerco Final) — Força maciça.\n",
            encoding="utf-8",
        )

        self.diario_path.write_text(
            "# Diário\n\n"
            "## Relógios Narrativos (Ameaças & Prazos)\n"
            "* **[Invasão da Fronteira]:** 1/4 (Gatilho: As muralhas caem) [ACTIVE]\n"
            "* **[Ritual Menor]:** 1/4 (Gatilho: Praga local) [ACTIVE]\n"
            "* **[Cerco Final]:** 3/4 (Gatilho: Capitulação total) [ACTIVE]\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_simulate_faction_tick_advancement_and_breach(self):
        camp_info = {
            "mundo": self.mundo_path,
            "diario": self.diario_path,
            "ficha": self.ficha_path,
            "npcs": self.npcs_path,
        }

        res = simulate_faction_tick(camp_info)
        self.assertEqual(res["operation"], "faction_tick")
        advs = res["advancements"]
        breaches = res["breaches"]

        # Império (Power 4) advances 1 step
        # Ordem da Alvorada (Power 5) advances 1 step -> reaches 4/4 (BREACHED)
        adv_names = [a["faction"] for a in advs]
        self.assertIn("Império do Ferro", adv_names)
        self.assertIn("Ordem da Alvorada", adv_names)

        # Ordem da Alvorada was 3/4, now 4/4 -> BREACHED
        breached_clocks = [b["clock"] for b in breaches]
        self.assertIn("Cerco Final", breached_clocks)

        # Verify diario.md was updated
        clocks = parse_diario_md(self.diario_path).get("clocks", [])
        c_map = {c["name"]: c for c in clocks}
        self.assertEqual(c_map["Invasão da Fronteira"]["current"], 2)
        self.assertEqual(c_map["Cerco Final"]["current"], 4)
        self.assertEqual(c_map["Cerco Final"]["status"], "BREACHED")


class TestFactionReviewerLints(unittest.TestCase):
    """US6: Lints determinísticos de integridade no council/reviewer.py."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir("rev_")
        self.camps_dir = self.temp_dir / "campaigns"
        self.camp_dir = self.camps_dir / "test_rev"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        helpers.CAMPAIGN_DIRS.insert(0, self.camps_dir)

        self.ficha_path = self.camp_dir / "ficha.md"
        self.diario_path = self.camp_dir / "diario.md"
        self.mundo_path = self.camp_dir / "mundo.md"
        self.npcs_path = self.camp_dir / "npcs.md"
        self.regras_path = self.camp_dir / "regras.md"

        self.regras_path.write_text("# Regras\nsystem: d20_3gates\n", encoding="utf-8")
        self.ficha_path.write_text(
            "# Ficha\n\n"
            "### Recursos Vitais\n"
            "- **HP:** 20/20\n\n"
            "### Progressão & Nível\n"
            "- **Nível:** 1\n"
            "- **Experiência (XP):** 0 / 250\n"
            "- **Pontos de Atributo:** 0\n"
            "- **Pontos de Habilidade:** 0\n\n"
            "### Vínculos, Laços & Matriz Relacional\n"
            "* **Reputação com Facções:**\n"
            "  * **Guilda das Sombras:** +2 (Aliado) | Favores: 0 | Débitos: 0\n",
            encoding="utf-8",
        )

        self.mundo_path.write_text(
            "# Mundo\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n"
            "- **[CLÃ_LOBO] Clã do Lobo** (Poder: 3, Escala: local) — Caçadores.\n",
            encoding="utf-8",
        )

        self.npcs_path.write_text(
            "# NPCs\n\n"
            "### Rogar o Caçador\n"
            "* **Facção / Afiliação:** Culto Proibido\n"
            "* **Atitude Atual:** Neutro\n"
            "* **Vontade Própria:** Caçar feras.\n"
            "* **Fraquezas:** Medo do escuro.\n",
            encoding="utf-8",
        )

        self.diario_path.write_text(
            "# Diário\n<!-- schema_version: 1 -->\n\n"
            "## Cabeçalho da Cena Ativa\n"
            "* **Data & Local:** 01/10/2026, 12:00 | Posto Avançado\n"
            "* **Presentes:** Protagonista, Rogar o Caçador\n\n"
            "## Relógios Narrativos (Ameaças & Prazos)\n"
            "- [ ] Perigo do Lobo: 1/4 [ACTIVE] -> Gatilho: Ataque.\n\n"
            "### Histórico de Turnos & Cenas\n\n"
            "#### Turno 1 (01/10/2026, 12:00)\n"
            "* **Vitais:** HP: 20/20\n"
            "* **Resumo:** Início.\n\n"
            "### Registro de Experiência\n\n"
            "### Registro de Reputação & Facções\n"
            "* **[Turno 1]** Guilda das Sombras: +1 Reputação (0 -> +1 [Amigável]) | Favores: 0 | Motivo: Teste\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.camps_dir in helpers.CAMPAIGN_DIRS:
            helpers.CAMPAIGN_DIRS.remove(self.camps_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_lints_detection(self):
        res = rev.cmd_review("test_rev")
        issues = {iss["type"]: iss for iss in res.get("issues", [])}

        # 1. FACTION_UNKNOWN: Guilda das Sombras is in ficha, but not in mundo
        self.assertIn("FACTION_UNKNOWN", issues)
        self.assertEqual(issues["FACTION_UNKNOWN"]["severity"], "HIGH")

        # 2. FACTION_ORPHANED_NPC: Rogar is affiliated with 'Culto Proibido', not in mundo
        self.assertIn("FACTION_ORPHANED_NPC", issues)
        self.assertEqual(issues["FACTION_ORPHANED_NPC"]["severity"], "MEDIUM")

        # 3. FACTION_REP_MISMATCH: Guilda das Sombras has score +2 on ficha, but only +1 in ledger
        self.assertIn("FACTION_REP_MISMATCH", issues)
        self.assertEqual(issues["FACTION_REP_MISMATCH"]["severity"], "HIGH")

    def test_lint_faction_attitude_desync(self):
        self.mundo_path.write_text(
            "# Mundo\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n"
            "- **[CLÃ_LOBO] Clã do Lobo** (Poder: 3, Escala: local) — Caçadores.\n",
            encoding="utf-8",
        )
        self.ficha_path.write_text(
            "# Ficha\n\n"
            "### Recursos Vitais\n"
            "- **HP:** 20/20\n\n"
            "### Progressão & Nível\n"
            "- **Nível:** 1\n"
            "- **Experiência (XP):** 0 / 250\n"
            "- **Pontos de Atributo:** 0\n"
            "- **Pontos de Habilidade:** 0\n\n"
            "### Vínculos, Laços & Matriz Relacional\n"
            "* **Reputação com Facções:**\n"
            "  * **Clã do Lobo:** -2 (Hostil) | Favores: 0 | Débitos: 0\n",
            encoding="utf-8",
        )
        self.npcs_path.write_text(
            "# NPCs\n\n"
            "### Fenrir Lobo-Gris\n"
            "* **Facção / Afiliação:** Clã do Lobo\n"
            "* **Atitude Atual:** Amigável e prestativo com o herói\n"
            "* **Vontade Própria:** Expandir as matilhas.\n"
            "* **Fraquezas:** Impaciência.\n",
            encoding="utf-8",
        )
        self.diario_path.write_text(
            "# Diário\n<!-- schema_version: 1 -->\n\n"
            "## Cabeçalho da Cena Ativa\n"
            "* **Data & Local:** 01/10/2026, 12:00 | Floresta\n"
            "* **Presentes:** Protagonista, Fenrir Lobo-Gris\n\n"
            "## Relógios Narrativos (Ameaças & Prazos)\n"
            "- [ ] Caçada Selvagem: 1/4 [ACTIVE] -> Gatilho: Invasão da vila.\n\n"
            "### Histórico de Turnos & Cenas\n\n"
            "#### Turno 1 (01/10/2026, 12:00)\n"
            "* **Vitais:** HP: 20/20\n"
            "* **Resumo:** Encontro.\n\n"
            "### Registro de Experiência\n\n"
            "### Registro de Reputação & Facções\n"
            "* **[Turno 1]** Clã do Lobo: -2 Reputação (0 -> -2 [Hostil]) | Favores: 0 | Motivo: Guerra declarada\n",
            encoding="utf-8",
        )

        res = rev.cmd_review("test_rev")
        issue_types = [iss["type"] for iss in res.get("issues", [])]
        self.assertIn("FACTION_ATTITUDE_DESYNC", issue_types)


if __name__ == "__main__":
    unittest.main()
