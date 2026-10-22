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


class TestPhase3QAFindingsRemediation(unittest.TestCase):
    """Testes específicos para remediação dos achados da QA da Fase 3 (P1-A, P1-B, P1-C, P1-D, P2)."""

    def setUp(self):
        self.temp_dir = make_test_temp_dir("qa_rem_")
        self.camps_dir = self.temp_dir / "campaigns"
        self.camps_dir.mkdir(parents=True, exist_ok=True)
        helpers.CAMPAIGN_DIRS.insert(0, self.camps_dir)

        self.camp_dir = self.camps_dir / "qa_camp"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        self.mundo_path = self.camp_dir / "mundo.md"
        self.ficha_path = self.camp_dir / "ficha.md"
        self.diario_path = self.camp_dir / "diario.md"
        self.npcs_path = self.camp_dir / "npcs.md"
        self.regras_path = self.camp_dir / "regras.md"

        self.regras_path.write_text("system: d20_3gates\nxp_curve: 250\n", encoding="utf-8")
        self.mundo_path.write_text(
            "# Cenário\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n"
            "* **[ORDEM_ESTABELECIDA] Ordem Estabelecida:** Nobres que governam a Cidadela Branca | Poder: 4 | Escala: global | Relógio: Prazo Final\n"
            "* **[A_GUARDA] A Guarda da Meia-Noite:** Tropa veterana liderada por Malakor | Poder: 5 | Escala: regional\n",
            encoding="utf-8",
        )
        self.ficha_path.write_text(
            "# Ficha\n\n"
            "### Vitais & Recursos\n"
            "- **HP:** 25/25\n"
            "- **Stamina:** 20/20\n\n"
            "### Progressão & Nível\n"
            "- **Nível:** 1\n"
            "- **Experiência (XP):** 0 / 250\n"
            "- **Pontos de Atributo:** 0\n"
            "- **Pontos de Habilidade:** 0\n\n"
            "### Vínculos\n"
            "* **Reputação com Facções:**\n"
            "  * **[ORDEM_ESTABELECIDA] Ordem Estabelecida:** +2 (Aliado) | Favores: 1 | Débitos: 0\n",
            encoding="utf-8",
        )
        self.npcs_path.write_text(
            "# NPCs\n\n"
            "### Malakor\n"
            "* **Grau / Classificação:** Comandante\n"
            "* **Papel:** Rival Militar\n"
            "* **Atitude Atual:** Desafiador e vigilante.\n"
            "* **Vontade Própria:** Tomar o comando da guarda.\n"
            "* **Fraquezas:** Arrogância.\n",
            encoding="utf-8",
        )
        self.diario_path.write_text(
            "# Diário\n<!-- schema_version: 1 -->\n\n"
            "## Cena 1: Encontro\n"
            "* **Data & Local:** 01/10/2026, 12:00 — Cidadela Branca.\n"
            "* **Presentes:** Protagonista, Malakor.\n\n"
            "### Relógios de Ameaça & Prazos\n"
            "* **[Prazo Final]:** 1/4 (Gatilho: Ruptura) [ACTIVE]\n\n"
            "### Arco Dramático Ativo\n"
            "* **Título:** Queda do Portão\n"
            "* **Pergunta Central:** O portão resistirá?\n"
            "* **Fase:** Clímax\n\n"
            "### Marcos da Crônica (Histórico de Arcos & Milestones)\n"
            "* **Marco 0 (Prólogo):** [01/10/2026]: Início.\n\n"
            "### Histórico de Turnos\n"
            "* **Turno 1:** Defesa inicial.\n\n"
            "### Registro de Experiência\n\n"
            "### Registro de Reputação & Facções\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.camps_dir in helpers.CAMPAIGN_DIRS:
            helpers.CAMPAIGN_DIRS.remove(self.camps_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_p1_a_clock_resolve_and_arc_milestone_idempotence(self):
        # 1. Primeira resolução de relógio: concede +40 XP
        res1 = lazy_turn.cmd_clock("qa_camp", resolve_name="Prazo Final")
        self.assertEqual(res1.get("action_result", {}).get("xp_granted"), 40)

        # 2. Segunda resolução do mesmo relógio: deve conceder 0 XP
        res2 = lazy_turn.cmd_clock("qa_camp", resolve_name="Prazo Final")
        self.assertIsNone(res2.get("action_result", {}).get("xp_granted"))
        self.assertIn("xp_warning", res2.get("action_result", {}))

        # 3. Primeiro marco de arco: concede +80 XP
        arc1 = lazy_turn.cmd_arc("qa_camp", milestone="Queda do Portão de Ferro")
        self.assertEqual(arc1.get("action_result", {}).get("arc_milestone_xp"), 80)

        # 4. Segundo marco com mesmo texto: deve conceder 0 XP
        arc2 = lazy_turn.cmd_arc("qa_camp", milestone="Queda do Portão de Ferro")
        self.assertIsNone(arc2.get("action_result", {}).get("arc_milestone_xp"))
        self.assertIn("arc_milestone_warning", arc2.get("action_result", {}))

    def test_p1_b_resolve_scene_factions_inference_and_territory(self):
        c_info = helpers.find_campaign("qa_camp")
        # Inclusão por inferência do NPC Malakor (citado na descrição da Guarda da Meia-Noite)
        sc1 = resolve_scene_factions(c_info, ["Malakor"], "Local Neutro")
        matched_tags1 = [f["tag"] for f in sc1]
        self.assertIn("A_GUARDA", matched_tags1)

        # Inclusão por território (Cidadela Branca está na descrição de Ordem Estabelecida)
        sc2 = resolve_scene_factions(c_info, [], "Cidadela Branca")
        matched_tags2 = [f["tag"] for f in sc2]
        self.assertIn("ORDEM_ESTABELECIDA", matched_tags2)
        ordem_fac = next(f for f in sc2 if f["tag"] == "ORDEM_ESTABELECIDA")
        self.assertEqual(ordem_fac["social_dc_mod"], -2)
        self.assertEqual(ordem_fac["source"], "territory")

    def test_p1_c_reputation_mismatch_no_false_positive_on_clamp_or_baseline(self):
        # Ficha começa em +2. Ajuste de +1 leva a +3 (Venerado).
        lazy_turn.cmd_faction("qa_camp", rep="Ordem Estabelecida:+1", reason="Ajuda militar")
        res1 = rev.cmd_review("qa_camp")
        issues1 = [iss["type"] for iss in res1.get("issues", [])]
        self.assertNotIn("FACTION_REP_MISMATCH", issues1)

        # Mais um +1 tenta passar de +3, mas é clampeado em +3.
        lazy_turn.cmd_faction("qa_camp", rep="Ordem Estabelecida:+1", reason="Outra ajuda")
        res2 = rev.cmd_review("qa_camp")
        issues2 = [iss["type"] for iss in res2.get("issues", [])]
        self.assertNotIn("FACTION_REP_MISMATCH", issues2)

    def test_p1_d_faction_unknown_detects_phantom_with_stopword(self):
        # Insere Ordem Fantasma na ficha (compartilha a palavra 'ordem' com 'Ordem Estabelecida')
        text = self.ficha_path.read_text(encoding="utf-8")
        text = text.replace(
            "### Vínculos\n* **Reputação com Facções:**\n",
            "### Vínculos\n* **Reputação com Facções:**\n  * **[ORDEM_FANTASMA] Ordem Fantasma:** +1 (Amigável) | Favores: 0 | Débitos: 0\n",
        )
        self.ficha_path.write_text(text, encoding="utf-8")

        res = rev.cmd_review("qa_camp")
        issues = {iss["type"]: iss for iss in res.get("issues", [])}
        self.assertIn("FACTION_UNKNOWN", issues)
        self.assertEqual(issues["FACTION_UNKNOWN"]["severity"], "HIGH")

    def test_p2_findings_remediation(self):
        # P2-1: Aviso ao ajustar reputação de facção que não consta em mundo.md
        res_warn = lazy_turn.cmd_faction("qa_camp", rep="Faccao Fantasma:+1")
        self.assertIn("warning", res_warn.get("action_result", {}))

        # P2-2 & P2-3: Tick off-screen grava no diário e retorna campaign id
        res_tick = lazy_turn.cmd_faction("qa_camp", tick=True)
        act = res_tick.get("action_result", {})
        self.assertEqual(act.get("campaign"), "qa_camp")
        self.assertGreater(len(act.get("advancements", [])), 0)

        diario_content = self.diario_path.read_text(encoding="utf-8")
        self.assertIn("### Movimentações de Facções Off-Screen", diario_content)

        # P2-4: Escala global aceita e gravada
        res_scale = lazy_turn.cmd_faction("qa_camp", add_name="Império Solar", scale="global", desc="Força estelar")
        mundo_content = self.mundo_path.read_text(encoding="utf-8")
        self.assertIn("Escala: global", mundo_content)


if __name__ == "__main__":
    unittest.main()
