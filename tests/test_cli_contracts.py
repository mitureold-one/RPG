"""tests/test_cli_contracts.py: Suíte de validação de contratos de CLI, mandates e portabilidade.

Garante que nenhuma divergência de flags, caminhos ou tipos de cena seja reintroduzida.
"""

import re
import shlex
import unittest
from pathlib import Path

from council.writer import STRUCTURAL_SCENE_MANDATES
import lazy_turn


class TestCLIContracts(unittest.TestCase):
    def setUp(self):
        self.parser = lazy_turn.build_cli()
        self.root_dir = Path(__file__).resolve().parent.parent

    def test_structural_scene_mandates_coverage(self):
        """Verifica se os 10 tipos de cena suportados possuem mandato estrutural correspondente."""
        expected_types = {
            "standard",
            "interlude",
            "parallel",
            "timeskip",
            "dossier",
            "flashback",
            "prologue",
            "epilogue",
            "post_credits",
            "fade_to_black",
        }
        mandate_types = set(STRUCTURAL_SCENE_MANDATES.keys())
        self.assertEqual(
            mandate_types,
            expected_types,
            f"Divergência nos mandatos estruturais: faltam {expected_types - mandate_types}, excedentes: {mandate_types - expected_types}",
        )

        # Checar se os subparsers contêm as mesmas choices
        for subparser_name in ["prepare", "commit", "plan"]:
            sub_action = None
            for action in self.parser._actions:
                if action.dest == "cmd":
                    sub_action = action.choices.get(subparser_name)
                    break
            self.assertIsNotNone(sub_action, f"Subparser {subparser_name} não encontrado.")
            scene_arg = next((a for a in sub_action._actions if a.dest == "scene_type"), None)
            self.assertIsNotNone(scene_arg, f"--scene-type ausente em {subparser_name}")
            self.assertEqual(
                set(scene_arg.choices),
                expected_types,
                f"Choices de --scene-type em {subparser_name} não cobrem todos os 10 tipos.",
            )

    def test_commit_hint_matches_argparse(self):
        """Garante que o hint de commit emitido pelo prepare é parseável sem erro pelo argparse."""
        prep_payload = lazy_turn.cmd_prepare(
            campaign_id="imperio_valiria",
            action="Inspecionar área",
            no_roll=True,
            scene_type="prologue",
        )
        commit_template = prep_payload["step_4_post_turn_commit_template"]["command_template"]
        self.assertTrue(commit_template.startswith("python lazy_turn.py commit"))

        # Extrair os argumentos após 'lazy_turn.py'
        cmd_tokens = shlex.split(commit_template.replace("python lazy_turn.py ", ""))
        try:
            parsed = self.parser.parse_args(cmd_tokens)
            self.assertEqual(parsed.cmd, "commit")
            self.assertEqual(parsed.campaign, "imperio_valiria")
            self.assertEqual(parsed.scene_type, "prologue")
            self.assertIsNotNone(parsed.npc_updates)
        except SystemExit:
            self.fail(f"Falha ao parsear o commit_template gerado pelo engine: {commit_template}")

    def test_showrunner_documented_commands_parse(self):
        """Verifica se os comandos documentados no SKILL.md do showrunner executam parse seco com sucesso."""
        showrunner_skill = self.root_dir / ".agents" / "skills" / "rpg-showrunner" / "SKILL.md"
        self.assertTrue(showrunner_skill.exists(), "rpg-showrunner/SKILL.md não encontrado")

        content = showrunner_skill.read_text(encoding="utf-8")
        # Extrair blocos ```bash ... ```
        bash_blocks = re.findall(r"```bash(.*?)```", content, re.DOTALL)
        self.assertGreater(len(bash_blocks), 0, "Nenhum bloco bash encontrado no SKILL.md")

        commands = []
        for block in bash_blocks:
            # Unir linhas continuadas com contra-barra
            normalized_block = re.sub(r"\\\s*\n\s*", " ", block)
            for line in normalized_block.splitlines():
                line = line.strip()
                if line.startswith("python lazy_turn.py"):
                    cmd = line.replace("python lazy_turn.py", "").strip()
                    commands.append(cmd)

        self.assertGreater(len(commands), 0, "Nenhum comando 'python lazy_turn.py' encontrado")

        for cmd in commands:
            # Substituir placeholders <...> por valores fictícios para teste de parse
            clean_cmd = re.sub(r"<[^>]+>", "dummy_val", cmd)
            clean_cmd = clean_cmd.replace("dummy_val|dummy_val", "dummy_val")
            tokens = shlex.split(clean_cmd)

            # Validar que o comando faz parse sem erro
            try:
                parsed = self.parser.parse_args(tokens)
                self.assertIn(parsed.cmd, ["plan", "clock", "arc", "review", "commit", "prepare"])
            except SystemExit:
                self.fail(f"Comando documentado em SKILL.md falhou no parse: {cmd}")

    def test_no_hardcoded_machine_paths(self):
        """Garante que não existem caminhos absolutos locais nas skills ou em council."""
        search_dirs = [
            self.root_dir / ".agents" / "skills",
            self.root_dir / "council",
        ]
        forbidden_patterns = [r"file:///C:", r"c:\\Users\\Konor", r"C:/Users/Konor"]

        for s_dir in search_dirs:
            for f_path in s_dir.rglob("*.*"):
                if f_path.suffix not in [".py", ".md"]:
                    continue
                text = f_path.read_text(encoding="utf-8")
                for pat in forbidden_patterns:
                    self.assertFalse(
                        re.search(pat, text, re.IGNORECASE),
                        f"Caminho absoluto proibido '{pat}' encontrado em {f_path}",
                    )

    def test_no_auto_activation_in_showrunner(self):
        """Garante que o showrunner não se auto-ativa em todo turno."""
        showrunner_skill = self.root_dir / ".agents" / "skills" / "rpg-showrunner" / "SKILL.md"
        text = showrunner_skill.read_text(encoding="utf-8")
        self.assertNotIn("Ativa-se automaticamente", text)


if __name__ == "__main__":
    unittest.main()
