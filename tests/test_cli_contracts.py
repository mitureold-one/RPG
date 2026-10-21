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

    def get_skill_roots(self):
        """Retorna as raízes de skills a auditar (raiz local do workspace e raiz global da máquina)."""
        roots = [self.root_dir / ".agents" / "skills"]
        global_skills = Path.home() / ".gemini" / "config" / "skills"
        if global_skills.exists():
            roots.append(global_skills)
        return roots

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
        """Verifica se os comandos documentados no SKILL.md do showrunner executam parse seco com sucesso em todas as raízes."""
        for s_root in self.get_skill_roots():
            showrunner_skill = s_root / "rpg-showrunner" / "SKILL.md"
            if not showrunner_skill.exists():
                continue

            content = showrunner_skill.read_text(encoding="utf-8")
            bash_blocks = re.findall(r"```bash(.*?)```", content, re.DOTALL)
            self.assertGreater(len(bash_blocks), 0, f"Nenhum bloco bash encontrado em {showrunner_skill}")

            commands = []
            for block in bash_blocks:
                normalized_block = re.sub(r"\\\s*\n\s*", " ", block)
                for line in normalized_block.splitlines():
                    line = line.strip()
                    if line.startswith("python lazy_turn.py"):
                        cmd = line.replace("python lazy_turn.py", "").strip()
                        commands.append(cmd)

            self.assertGreater(len(commands), 0, f"Nenhum comando 'python lazy_turn.py' em {showrunner_skill}")

            for cmd in commands:
                clean_cmd = re.sub(r"<[^>]+>", "dummy_val", cmd)
                clean_cmd = clean_cmd.replace("dummy_val|dummy_val", "dummy_val")
                tokens = shlex.split(clean_cmd)

                try:
                    parsed = self.parser.parse_args(tokens)
                    self.assertIn(parsed.cmd, ["plan", "clock", "arc", "review", "commit", "prepare"])
                except SystemExit:
                    self.fail(f"Comando documentado em {showrunner_skill} falhou no parse: {cmd}")

    def test_no_hardcoded_machine_paths(self):
        """Garante que não existem caminhos absolutos locais nas skills ou em council em todas as raízes."""
        search_dirs = list(self.get_skill_roots())
        search_dirs.append(self.root_dir / "council")
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
        """Garante que o showrunner não se auto-ativa em todo turno em todas as raízes."""
        for s_root in self.get_skill_roots():
            showrunner_skill = s_root / "rpg-showrunner" / "SKILL.md"
            if showrunner_skill.exists():
                text = showrunner_skill.read_text(encoding="utf-8")
                self.assertNotIn(
                    "Ativa-se automaticamente",
                    text,
                    f"Auto-ativação indevida encontrada em {showrunner_skill}",
                )

    def test_p1_agents_md_router_contract(self):
        """P1: Garante que AGENTS.md opera como roteador enxuto (<= 15 linhas) sem regras de prosa."""
        agents_file = self.root_dir / "AGENTS.md"
        self.assertTrue(agents_file.exists(), "AGENTS.md não encontrado na raiz")
        lines = agents_file.read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(
            len(lines),
            15,
            f"AGENTS.md possui {len(lines)} linhas; deve ter no máximo 15 linhas como roteador minimalista.",
        )

        content = "\n".join(lines)
        forbidden_prose_keywords = ["travessão", "script teatral", "Linha 1 Obrigatória", "4 Batidas"]
        for kw in forbidden_prose_keywords:
            self.assertNotIn(
                kw,
                content,
                f"Regra de prosa redundante '{kw}' encontrada em AGENTS.md (deve pertencer apenas ao writer payload).",
            )

        # Checar se os elementos canônicos do roteador estão presentes
        self.assertIn("RPGPRO Sovereign Router", content)
        self.assertIn("Grau 1", content)
        self.assertIn("Grau 2", content)
        self.assertIn("Grau 3", content)
        self.assertIn("rpg-narrative-engine", content)
        self.assertIn("rpg-showrunner", content)
        self.assertIn("step_3_writer_mandate", content)

    def test_p1_module_3_no_cli_execution_blocks(self):
        """P1: Garante que o Módulo 3 não replica comandos CLI de relógio/plano em todas as raízes."""
        for s_root in self.get_skill_roots():
            mod3_file = s_root / "rpg-narrative-engine" / "references" / "3_campaign_crud_and_state.md"
            if not mod3_file.exists():
                continue
            content = mod3_file.read_text(encoding="utf-8")

            self.assertNotIn(
                "python lazy_turn.py clock",
                content,
                f"Comando executável 'python lazy_turn.py clock' duplicado em {mod3_file}",
            )
            self.assertNotIn(
                "python lazy_turn.py plan",
                content,
                f"Comando executável 'python lazy_turn.py plan' duplicado em {mod3_file}",
            )

    def test_p1_narrative_skill_table_sovereignty(self):
        """P1: Garante que no SKILL.md a linha do Módulo 3 não reivindica autoridade de execução sobre relógios/fila."""
        for s_root in self.get_skill_roots():
            skill_file = s_root / "rpg-narrative-engine" / "SKILL.md"
            if not skill_file.exists():
                continue
            content = skill_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if "3_campaign_crud_and_state.md" in line:
                    self.assertNotIn("via lazy_turn.py clock", line, f"Soberania dupla de relógios em {skill_file}")
                    self.assertNotIn("lazy_turn.py plan", line, f"Soberania dupla de plano em {skill_file}")
                    self.assertIn("rpg-showrunner", line, f"Falta ponteiro para rpg-showrunner em {skill_file}")

    def test_p1_campaigns_no_generic_dc_ladder(self):
        """P1: Garante que nenhuma campanha ativa ou template repete a escada genérica universal de DC e contém yaml:mechanics."""
        regras_files = list((self.root_dir / "campaigns").glob("*/regras.md"))
        regras_files.append(self.root_dir / "templates" / "regras.template.md")

        self.assertGreater(len(regras_files), 1, "Nenhum arquivo de regras de campanha encontrado")
        forbidden_dc_needle = "DC 10 (Ação Básica sob Pressão)"
        ladder_pattern = re.compile(
            r"\*\*DC\s*10\b[\s\S]{0,300}\*\*DC\s*15\b[\s\S]{0,300}\*\*DC\s*20\b[\s\S]{0,300}\*\*DC\s*25\b",
            re.IGNORECASE,
        )

        for r_file in regras_files:
            content = r_file.read_text(encoding="utf-8")
            self.assertNotIn(
                forbidden_dc_needle,
                content,
                f"Escada genérica de DC duplicada encontrada em {r_file.relative_to(self.root_dir)}",
            )
            self.assertFalse(
                ladder_pattern.search(content),
                f"Padrão estrutural de escada mecânica de DC duplicado em {r_file.relative_to(self.root_dir)}",
            )
            self.assertIn(
                "```yaml:mechanics",
                content,
                f"Bloco estruturado ```yaml:mechanics ausente em {r_file.relative_to(self.root_dir)}",
            )


if __name__ == "__main__":
    unittest.main()
