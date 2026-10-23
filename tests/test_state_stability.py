"""tests/test_state_stability.py: contratos da Etapa 1 (estado consistente).

Cobre:
- escrita atômica sem temporários órfãos;
- rejeição de relógios, missões e facções inexistentes antes de gravar;
- parsing de subcampos de NPC sem criar NPC fantasma;
- idempotência de conclusão de missão feita pela CLI;
- caminho de prosa por arquivo;
- calendário declarativo e falha alta para mês desconhecido.
"""

import shutil
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_ROOT = PROJECT_ROOT / ".tmp" / "test_scratch"


def make_stability_dir(prefix: str = "stab_") -> Path:
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    path = SCRATCH_ROOT / f"{prefix}{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


import council.helpers as helpers
from council.helpers import atomic_write_text
from council.ssot import parse_progression_from_ficha
from lazy_turn import cmd_check_prose, cmd_commit, cmd_quest


class StabilityFixture(unittest.TestCase):
    def setUp(self):
        self.temp_dir = make_stability_dir()
        self.camps_dir = self.temp_dir / "campaigns"
        self.camp_dir = self.camps_dir / "test_camp"
        self.camp_dir.mkdir(parents=True, exist_ok=True)
        helpers.CAMPAIGN_DIRS.insert(0, self.camps_dir)

        self.ficha = self.camp_dir / "ficha.md"
        self.diario = self.camp_dir / "diario.md"
        self.npcs = self.camp_dir / "npcs.md"
        self.mundo = self.camp_dir / "mundo.md"
        self.regras = self.camp_dir / "regras.md"

        self.ficha.write_text(
            "# Ficha do Protagonista: Ari\n\n"
            "### Vitais & Recursos\n"
            "* **HP:** 20 / 20\n"
            "* **Stamina:** 10 / 10\n\n"
            "### Atributos\n"
            "* **FOR (Força Física):** 14\n\n"
            "### Vínculos, Laços & Matriz Relacional\n"
            "* **Reputação com Facções:** Conselho (Neutro)\n",
            encoding="utf-8",
        )
        self.diario.write_text(
            "---\n"
            "schema_version: 1\n"
            "---\n"
            "# Diário\n\n"
            "## Cena 1: O Porto\n"
            "* **Data & Local:** 04 de Ventania de 304, 21:15 — Porto.\n"
            "* **Presentes:** Ari, Lady.\n"
            "* **Fatos:** O porto amanhece sob neblina.\n\n"
            "### Relógios de Ameaça & Prazos\n"
            "* **[Defesa do Porto]:** 1/4 (Gatilho: O porto cai) [ACTIVE]\n\n"
            "### Missões & Objetivos\n"
            "* **[Q1] [MAIN] Proteger o porto** | Status: ACTIVE | Contratante: Conselho | Recompensa: 150 XP\n"
            "  * [ ] Repelir a primeira onda\n\n"
            "### Histórico de Turnos\n"
            "* **Turno 1:** Ari chega ao porto. Vitais: HP 20/20, Stamina 10/10.\n",
            encoding="utf-8",
        )
        self.npcs.write_text(
            "# Catálogo de NPCs\n\n"
            "### Lady\n"
            "* **Grau / Classificação:** Nobre\n"
            "* **Papel:** Aliada\n"
            "* **Atitude Atual:** Cautelosa.\n"
            "* **Relação com Protagonista:** Confiança +0.\n"
            "* **Vontade Própria & Agenda:** Proteger o porto.\n",
            encoding="utf-8",
        )
        self.mundo.write_text(
            "# Mundo\n\n"
            "## 4. Facções, Forças Ativas & Alianças\n"
            "* **[CONSELHO] Conselho:** Governa o porto. | Poder: 3 | Escala: regional\n",
            encoding="utf-8",
        )
        self._write_regras()

    def _write_regras(self, calendar: bool = False):
        extra = ""
        if calendar:
            extra = (
                "calendar:\n"
                "  months: [\"Ventania\", \"Geada\"]\n"
                "  days_per_month: 10\n"
            )
        self.regras.write_text(
            "# Regras\n\n```yaml\n"
            "system: d20_3gates\n"
            f"{extra}"
            "```\n",
            encoding="utf-8",
        )

    def tearDown(self):
        if self.camps_dir in helpers.CAMPAIGN_DIRS:
            helpers.CAMPAIGN_DIRS.remove(self.camps_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def turn_count(self) -> int:
        text = self.diario.read_text(encoding="utf-8")
        return text.count("* **Turno ")


class TestEntityValidation(StabilityFixture):
    def test_unknown_clock_is_rejected_without_writing(self):
        before = self.diario.read_text(encoding="utf-8")
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Ari tenta mover um relógio inexistente.",
            clock_advance="Relogio Errado:2",
        )
        self.assertIn("validation_errors", res)
        self.assertIn("Relógio 'Relogio Errado'", res["error"] + " " + " ".join(res["validation_errors"]))
        self.assertEqual(self.diario.read_text(encoding="utf-8"), before)

    def test_unknown_quest_is_rejected_without_writing(self):
        before = self.diario.read_text(encoding="utf-8")
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Ari tenta concluir uma missão inexistente.",
            quest_complete="Q99",
        )
        self.assertIn("validation_errors", res)
        self.assertEqual(self.diario.read_text(encoding="utf-8"), before)

    def test_unknown_faction_is_rejected_without_writing(self):
        before = self.diario.read_text(encoding="utf-8")
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Ari tenta ajustar uma facção inexistente.",
            faction_rep="Fantasma:+1",
        )
        self.assertIn("validation_errors", res)
        self.assertEqual(self.diario.read_text(encoding="utf-8"), before)


class TestNpcParsing(StabilityFixture):
    def test_subfields_update_one_npc_without_phantom(self):
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Lady assume postura de guarda.",
            npc_updates="Lady: Atitude: Em guarda; Relação: Confiança +1",
        )
        self.assertEqual(res.get("status"), "ok")
        text = self.npcs.read_text(encoding="utf-8")
        headings = [line for line in text.splitlines() if line.startswith("### ")]
        self.assertEqual(headings, ["### Lady"])
        self.assertIn("**Atitude Atual:** Em guarda.", text)
        self.assertIn("**Relação com Protagonista:** Confiança +1.", text)

    def test_two_npcs_with_pipe(self):
        self.npcs.write_text(
            self.npcs.read_text(encoding="utf-8")
            + "\n### Rival\n* **Atitude Atual:** Hostil.\n",
            encoding="utf-8",
        )
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Lady e Rival se enfrentam.",
            npc_updates="Lady: Atitude: Em guarda | Rival: Atitude: Furioso",
        )
        self.assertEqual(res.get("status"), "ok")
        text = self.npcs.read_text(encoding="utf-8")
        self.assertIn("**Atitude Atual:** Em guarda.", text)
        self.assertIn("**Atitude Atual:** Furioso.", text)


class TestQuestIdempotency(StabilityFixture):
    def test_completed_via_cli_is_not_paid_again_by_commit(self):
        cmd_quest(campaign_id="test_camp", complete_id="Q1")
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Ari reivindica a mesma recompensa.",
            quest_complete="Q1",
        )
        self.assertEqual(res.get("status"), "ok")
        updates = "\n".join(res.get("updates", []))
        self.assertIn("já está COMPLETED", updates)
        self.assertIn("XP não concedido novamente", updates)
        self.assertEqual(parse_progression_from_ficha(self.ficha)["xp"], 0)


class TestProseFile(StabilityFixture):
    def test_check_prose_file_path_does_not_raise(self):
        prose = self.temp_dir / "prose.md"
        prose.write_text("Ari ergueu o olhar.\n— O porto resiste — disse ele.", encoding="utf-8")
        res = cmd_check_prose(file_path=str(prose))
        self.assertIn("status", res)
        self.assertEqual(res["status"], "CLEAN")


class TestCalendar(StabilityFixture):
    def test_custom_calendar_advances_and_rolls_month(self):
        self._write_regras(calendar=True)
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Ari aguarda cinco dias.",
            time="+5d",
        )
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("9 de Ventania de 304", res["canonical_header_for_response"])

        res2 = cmd_commit(
            campaign_id="test_camp",
            summary="Ari aguarda mais dez dias.",
            time="+10d",
        )
        self.assertEqual(res2.get("status"), "ok")
        self.assertIn("9 de Geada de 304", res2["canonical_header_for_response"])

    def test_unknown_month_intra_month_advances(self):
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Ari avança um dia dentro de Ventania.",
            time="+1d",
        )
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("5 de Ventania de 304", res["canonical_header_for_response"])

    def test_unknown_month_boundary_fails_before_writing(self):
        before = self.diario.read_text(encoding="utf-8")
        res = cmd_commit(
            campaign_id="test_camp",
            summary="Ari tenta atravessar o mês sem calendário.",
            time="+30d",
        )
        self.assertIn("error", res)
        self.assertIn("calendar", res["error"].lower())
        self.assertEqual(self.diario.read_text(encoding="utf-8"), before)


class TestCommitRollback(StabilityFixture):
    def test_unexpected_failure_after_writes_restores_snapshot(self):
        from unittest.mock import patch

        before_diario = self.diario.read_text(encoding="utf-8")
        before_ficha = self.ficha.read_text(encoding="utf-8")
        with patch("application.commit.cmd_review", side_effect=RuntimeError("falha simulada")):
            with self.assertRaises(RuntimeError):
                cmd_commit(
                    campaign_id="test_camp",
                    summary="Ari tenta um turno que falha no fim.",
                )
        self.assertEqual(self.diario.read_text(encoding="utf-8"), before_diario)
        self.assertEqual(self.ficha.read_text(encoding="utf-8"), before_ficha)


class TestAtomicWrite(unittest.TestCase):
    def test_atomic_write_replaces_and_leaves_no_temp(self):
        temp_dir = make_stability_dir("atomic_")
        try:
            target = temp_dir / "state.md"
            atomic_write_text(target, "primeiro")
            atomic_write_text(target, "segundo")
            self.assertEqual(target.read_text(encoding="utf-8"), "segundo")
            leftovers = [p.name for p in temp_dir.iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
