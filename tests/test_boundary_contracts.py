"""tests/test_boundary_contracts.py: Suíte de testes de fronteira do RPGPRO (P3).

Valida isolamento de diegese (zero vazamento de substantivos de campanhas em skills),
paridade estrita entre a CLI e a documentação, e imutabilidade do snapshot do payload de preparação.
"""

import re
import shlex
import unittest
from pathlib import Path

from council.helpers import find_campaign, parse_regras_manifest
from council.ssot import parse_ficha_md
from council.narrator import parse_npcs_md
import lazy_turn


class TestBoundaryContracts(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.parser = lazy_turn.build_cli()
        self.campaign_ids = ["dinastia_cinzas", "imperio_valiria", "perpetuos_terra_incognita"]

    def get_skill_files(self):
        """Retorna todos os arquivos de skills locais e globais."""
        files = list((self.root_dir / ".agents" / "skills").rglob("*.md"))
        global_skills = Path.home() / ".gemini" / "config" / "skills"
        if global_skills.exists():
            for g_file in global_skills.rglob("rpg*/**/*.md"):
                files.append(g_file)
        return files

    def test_boundary_no_diegetic_noun_leakage(self):
        """Fronteira 1: Garante que as skills universais não contêm substantivos próprios ou termos diegéticos de nenhuma campanha."""
        # Palavras funcionais / comuns da língua que não são vazamento diegético
        stop_words = {
            "lorde", "capitão", "capitao", "guarda",
            "conselho", "mundo", "nenhum", "todas", "sobre", "para",
            "como", "ouro", "ferro", "comandante",
            "protagonista", "personagem", "aliado", "mentor", "rival", "inimigo",
            "antigo", "livro", "muralha", "senhora"
        }

        # Extrai substantivos e termos característicos das 3 campanhas
        diegetic_nouns = {}
        for cid in self.campaign_ids:
            info = find_campaign(cid)
            self.assertIsNotNone(info, f"Campanha {cid} não encontrada.")

            # 1. Protagonista
            ficha = parse_ficha_md(info["ficha"])
            protagonist_name = ficha.get("name", "")
            for token in re.split(r"[\s(),&_-]+", protagonist_name):
                tok_clean = token.strip()
                if len(tok_clean) >= 4 and tok_clean.lower() not in stop_words and tok_clean[0].isupper():
                    diegetic_nouns[tok_clean] = cid

            # 2. NPCs registrados
            npcs = parse_npcs_md(info["npcs"])
            for npc in npcs:
                for token in re.split(r"[\s(),&_-]+", npc.get("name", "")):
                    tok_clean = token.strip()
                    if len(tok_clean) >= 4 and tok_clean.lower() not in stop_words and tok_clean[0].isupper():
                        diegetic_nouns[tok_clean] = cid

        # Nomes adicionais icônicos diegéticos das 3 campanhas
        curated_specifics = {
            "Kon-El": "imperio_valiria",
            "Kallista": "imperio_valiria",
            "Krypton": "imperio_valiria",
            "Valíria": "imperio_valiria",
            "Valiria": "imperio_valiria",
            "Torquasm": "imperio_valiria",
            "Aemon": "dinastia_cinzas",
            "Vespera": "dinastia_cinzas",
            "Malakor": "dinastia_cinzas",
            "Sylvia": "dinastia_cinzas",
            "Cinzas": "dinastia_cinzas",
            "Morpheus": "perpetuos_terra_incognita",
            "Coríntio": "perpetuos_terra_incognita",
            "Corintio": "perpetuos_terra_incognita",
            "Lucien": "perpetuos_terra_incognita",
            "Desconhecido": "perpetuos_terra_incognita",
        }
        diegetic_nouns.update(curated_specifics)

        skill_files = self.get_skill_files()
        self.assertGreater(len(skill_files), 0, "Nenhum arquivo de skill localizado para teste de fronteira.")

        leaks = []
        for s_file in skill_files:
            text = s_file.read_text(encoding="utf-8")
            for noun, originating_camp in diegetic_nouns.items():
                # Busca palavra isolada
                pattern = rf"\b{re.escape(noun)}\b"
                if re.search(pattern, text, re.IGNORECASE):
                    leaks.append({
                        "file": str(s_file.relative_to(self.root_dir) if s_file.is_relative_to(self.root_dir) else s_file),
                        "noun": noun,
                        "campaign": originating_camp,
                    })

        self.assertEqual(
            leaks,
            [],
            f"Vazamento diegético detectado nas skills universais ({len(leaks)} ocorrências): {leaks}",
        )

    def test_boundary_cli_docs_contract(self):
        """Fronteira 2: Garante que todos os comandos 'python lazy_turn.py' nos documentos passam no parser da CLI."""
        doc_candidates = [
            self.root_dir / "README.md",
            self.root_dir / "DECISOES_ARQUITETURA.md",
        ]
        doc_candidates.extend(self.get_skill_files())

        commands_found = []
        for doc in doc_candidates:
            if not doc.exists():
                continue
            content = doc.read_text(encoding="utf-8")

            # 1. Comandos em blocos cercados (```bash ... ```)
            for block in re.findall(r"```(?:bash|sh|powershell|text|zsh)?\s*\n(.*?)```", content, re.DOTALL):
                normalized = re.sub(r"\\\s*\n\s*", " ", block)
                normalized = re.sub(r"`\s*\n\s*", " ", normalized)
                for line in normalized.splitlines():
                    line = line.strip()
                    if line.startswith("python lazy_turn.py"):
                        cmd = line.replace("python lazy_turn.py", "", 1).strip()
                        commands_found.append((doc.name, cmd))

            # 2. Comandos inline em crases simples
            for inline in re.findall(r"`python lazy_turn\.py\s+([^`]+)`", content):
                normalized = re.sub(r"\\\s*\n\s*", " ", inline)
                normalized = re.sub(r"`\s*\n\s*", " ", normalized)
                commands_found.append((doc.name, normalized.strip()))

        self.assertGreater(len(commands_found), 0, "Nenhum comando documentado encontrado para teste de contrato.")

        parse_errors = []
        for doc_name, cmd_str in commands_found:
            clean = cmd_str.split("#")[0].strip()
            # Trata parâmetros opcionais documentados como [--flag <val>]
            clean = re.sub(r"\[--dc\s+<[^>]+>\]", "--dc 15", clean)
            clean = re.sub(r"\[--[a-zA-Z0-9_\-]+(?:\s+[^\]]+)?\]", "", clean)
            clean = re.sub(r"--stakes\s+<[^>]+>", "--stakes normal", clean)
            clean = re.sub(r"--stakes\s+dummy_val", "--stakes normal", clean)
            clean = re.sub(r"--scene-type\s+[^ \t]+", "--scene-type standard", clean)
            clean = re.sub(r"--variant\s+<[^>]+>", "--variant normal", clean)
            clean = re.sub(r"--variant\s+dummy_val", "--variant normal", clean)
            clean = re.sub(r"<[^>]+>", "dummy_val", clean)
            clean = clean.replace('"dummy_val"', "dummy_val").replace("'dummy_val'", "dummy_val")
            clean = clean.rstrip("\\` ")

            try:
                tokens = shlex.split(clean)
                parsed = self.parser.parse_args(tokens)
                self.assertIsNotNone(parsed.cmd)
            except (SystemExit, Exception) as exc:
                parse_errors.append((doc_name, cmd_str, clean, str(exc)))

        self.assertEqual(
            parse_errors,
            [],
            f"Comandos documentados falharam na validação contra o argparse ({len(parse_errors)} falhas): {parse_errors}",
        )

    def test_boundary_prepare_payload_snapshot(self):
        """Fronteira 3: Garante que o payload gerado por lazy_turn.cmd_prepare respeita estritamente o snapshot de contrato."""
        payload = lazy_turn.cmd_prepare(
            campaign_id="dinastia_cinzas",
            action="Inspecionar aposentos reais",
            no_roll=True,
            scene_type="standard",
        )

        # 1. Chaves de Topo Obrigatórias
        required_top_keys = {
            "campaign",
            "system",
            "operation_mode",
            "next_turn_number",
            "canonical_header",
            "scene_type",
            "stakes",
            "is_critical_turn",
            "situational_pacing",
            "protagonist",
            "step_1_gm_arbitration",
            "step_2_narrator_briefing",
            "step_3_writer_mandate",
            "step_4_post_turn_commit_template",
        }
        for k in required_top_keys:
            self.assertIn(k, payload, f"Chave de topo '{k}' ausente no payload de prepare")

        self.assertEqual(payload["campaign"], "dinastia_cinzas")
        self.assertEqual(payload["system"], "d20_3gates")
        self.assertEqual(payload["operation_mode"], "gm")
        self.assertEqual(payload["scene_type"], "standard")

        # 2. Step 1: GM Arbitration Snapshot
        step_1 = payload["step_1_gm_arbitration"]
        self.assertIn("ruleset", step_1)
        self.assertIn("dc_ladder", step_1)
        self.assertIn("overrides", step_1)
        self.assertIn("dice_resolution", step_1)
        self.assertIn("cost_directive", step_1)

        # Valida tipagem dos overrides
        self.assertIsInstance(step_1["overrides"], list)
        self.assertGreater(len(step_1["overrides"]), 0)
        for ov in step_1["overrides"]:
            for field in ["id", "type", "target", "value", "condition"]:
                self.assertIn(field, ov, f"Campo '{field}' ausente no override: {ov}")

        # 3. Step 2: Narrator Briefing Snapshot
        step_2 = payload["step_2_narrator_briefing"]
        self.assertIn("focal_npcs", step_2)
        self.assertIn("background_cast", step_2)
        self.assertIn("scene_relational_matrix", step_2)
        self.assertIn("triangulation_mandate", step_2)
        self.assertIn("epistemic_barrier", step_2)

        # 4. Step 3: Writer Mandate Snapshot
        step_3 = payload["step_3_writer_mandate"]
        self.assertIsInstance(step_3, dict)
        self.assertIn("scene_type", step_3)
        self.assertIn("dialogue_and_style", step_3)

        # 5. Step 4: Post Turn Commit Template Snapshot
        step_4 = payload["step_4_post_turn_commit_template"]
        self.assertIn("command_template", step_4)
        self.assertIn("mandatory_npc_updates", step_4)
        self.assertIn("item_and_inventory_rule", step_4)
        self.assertIn("milestone_rule", step_4)
        self.assertTrue(
            step_4["command_template"].startswith("python lazy_turn.py commit"),
            f"Template de commit inválido: {step_4['command_template']}",
        )


if __name__ == "__main__":
    unittest.main()
