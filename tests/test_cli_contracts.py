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
                "```yaml",
                content,
                f"Bloco estruturado ```yaml ausente em {r_file.relative_to(self.root_dir)}",
            )

    def test_p2_ruleset_d20_3gates_extraction(self):
        """P2: Garante que rulesets/d20_3gates.py é independente, executável e reexportado por council.gm."""
        import rulesets.d20_3gates as d20
        from council import gm

        roll = d20.roll_3_gates("Ataque", variant="normal", dc=15, stat_name="FOR", stat_val=14)
        self.assertEqual(roll["dc"], 15)
        self.assertEqual(roll["modifier"], 2)
        self.assertEqual(roll["stat"], "FOR")
        self.assertIn("total", roll)

        contest = d20.roll_contest("PC", "FOR", 14, "NPC", "Composure", 2)
        self.assertIn("winner", contest)
        self.assertIn("delta", contest)

        # Checa reexportação e paridade em council.gm
        self.assertIs(gm.roll_3_gates, d20.roll_3_gates)
        self.assertIs(gm.roll_contest, d20.roll_contest)
        self.assertIs(gm.extract_npc_contest_modifier, d20.extract_npc_contest_modifier)

        # Checa que prepare expõe system e dc_ladder no payload (R2 & R5)
        prep = lazy_turn.cmd_prepare("dinastia_cinzas", "Observar o ambiente", no_roll=True)
        self.assertEqual(prep.get("system"), "d20_3gates")
        self.assertEqual(prep.get("step_1_gm_arbitration", {}).get("ruleset"), "d20_3gates")
        self.assertIn("Fácil", prep.get("step_1_gm_arbitration", {}).get("dc_ladder", {}))

    def test_p2_schema_version_and_loud_failures(self):
        """P2: Garante que find_campaign falha alto (FileNotFoundError / ValueError) em esquemas corrompidos ou ruleset desconhecido."""
        import tempfile
        from unittest.mock import patch
        import council.helpers as helpers
        from council.helpers import find_campaign, CURRENT_SCHEMA_VERSION

        SCRATCH_ROOT = Path(__file__).resolve().parent.parent / ".tmp" / "test_scratch"
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(SCRATCH_ROOT)) as tmp_dir:
            temp_path = Path(tmp_dir)
            temp_camp = temp_path / "_test_p2_fail_loud"
            temp_camp.mkdir(parents=True, exist_ok=True)

            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                # 1. Ausência de diario.md -> FileNotFoundError
                with self.assertRaises(FileNotFoundError) as ctx_fnf:
                    find_campaign("_test_p2_fail_loud")
                self.assertIn("diario.md", str(ctx_fnf.exception))

                # 2. diario.md sem schema_version -> ValueError
                (temp_camp / "diario.md").write_text("# Diário sem versão", encoding="utf-8")
                with self.assertRaises(ValueError) as ctx_no_ver:
                    find_campaign("_test_p2_fail_loud")
                self.assertIn("schema_version", str(ctx_no_ver.exception))

                # 3. schema_version incompatível (superior) -> ValueError
                (temp_camp / "diario.md").write_text("---\nschema_version: 999\n---\n# Diário Futuro", encoding="utf-8")
                with self.assertRaises(ValueError) as ctx_future:
                    find_campaign("_test_p2_fail_loud")
                self.assertIn("superior à versão suportada", str(ctx_future.exception))

                # 4. R1: ruleset desconhecido falha alto -> ValueError
                (temp_camp / "diario.md").write_text("---\nschema_version: 1\n---\n# Diário Válido", encoding="utf-8")
                (temp_camp / "regras.md").write_text("```yaml\nsystem: nao_existe_sistema\n```", encoding="utf-8")
                with self.assertRaises(ValueError) as ctx_sys:
                    find_campaign("_test_p2_fail_loud")
                self.assertIn("nao_existe_sistema", str(ctx_sys.exception))

        # 5. Todas as campanhas canônicas reais carregam com sucesso e schema_version == 1
        for cid in ["dinastia_cinzas", "imperio_valiria", "perpetuos_terra_incognita"]:
            info = find_campaign(cid)
            self.assertIsNotNone(info, f"Campanha {cid} não foi localizada")
            self.assertEqual(info["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertEqual(info["system"], "d20_3gates")

    def test_p2_campaign_manifest_and_template_system(self):
        """P2: Garante que templates e campanhas ativas declaram system: d20_3gates e schema_version: 1."""
        diario_template = self.root_dir / "templates" / "diario.template.md"
        self.assertTrue(diario_template.exists())
        self.assertIn("schema_version: 1", diario_template.read_text(encoding="utf-8"))

        regras_template = self.root_dir / "templates" / "regras.template.md"
        self.assertTrue(regras_template.exists())
        self.assertIn("system: d20_3gates", regras_template.read_text(encoding="utf-8"))

        for cid in ["dinastia_cinzas", "imperio_valiria", "perpetuos_terra_incognita"]:
            camp_dir = self.root_dir / "campaigns" / cid
            regras_text = (camp_dir / "regras.md").read_text(encoding="utf-8")
            diario_text = (camp_dir / "diario.md").read_text(encoding="utf-8")
            self.assertIn("system: d20_3gates", regras_text, f"system: d20_3gates ausente em {cid}/regras.md")
            self.assertIn("schema_version: 1", diario_text, f"schema_version: 1 ausente em {cid}/diario.md")

    def test_p2_cli_sanitization_no_franchise_leaks(self):
        """P2: Garante que lazy_turn.py e seus subparsers não contêm nomes de campanhas ou franquias específicas no --help."""
        forbidden_terms = ["Shinjuku", "Kenjaku", "Fleur", "Cedric", "Krum", "cyber_neo_tokyo"]

        # 1. Help raiz
        root_help = self.parser.format_help()
        for term in forbidden_terms:
            self.assertNotIn(term, root_help, f"Termo proibido '{term}' encontrado no help raiz da CLI")

        # 2. Subparsers
        for action in self.parser._actions:
            if action.dest == "cmd" and hasattr(action, "choices"):
                for sub_name, sub_parser in action.choices.items():
                    sub_help = sub_parser.format_help()
                    for term in forbidden_terms:
                        self.assertNotIn(term, sub_help, f"Termo proibido '{term}' encontrado no help de '{sub_name}'")

    def test_p3_prose_lints_in_reviewer(self):
        """P3: Garante que check_prose_lints detecta emojis, formato teatral e perguntas de 4ª parede com zero falsos positivos."""
        from council.reviewer import check_prose_lints, cmd_review

        # 1. Prosa literária canônica limpa com travessão e diálogo integrado -> 0 issues
        clean_text = (
            "Aemon ergueu o cálice sob a penumbra da lareira e encarou Vespera.\n"
            "— Se os cavaleiros de ferro cruzarem o fosso — murmurou ele —, não haverá conselho que os salve."
        )
        self.assertEqual(check_prose_lints(clean_text), [])

        # 2. Detecção de Emojis
        emoji_samples = [
            "O golpe acertou em cheio no escudo! 🔥",
            "A espada de aço brilhou na escuridão ⚔️.",
            "Um brilho misterioso surgiu na sala ✨",
        ]
        for sample in emoji_samples:
            issues = check_prose_lints(sample)
            issue_types = [i["type"] for i in issues]
            self.assertIn("EMOJI_DETECTED", issue_types, f"Emoji não detectado em: {sample}")

        # 3. Detecção de Formato Teatral ([Nome]: ou Nome: "fala")
        script_samples = [
            "[Aemon]: Não recue agora!",
            "Vespera: \"O castelo cairá antes da meia-noite.\"",
            "   [Cavaleiro Negro]: Às armas!",
            "Sylvia: “O vinho está pronto.”",
            "Vespera: O trono é meu por direito de sangue.",  # Sem aspas (R3) com known_speakers
        ]
        for sample in script_samples:
            issues = check_prose_lints(sample, known_speakers={"Vespera", "Aemon", "Sylvia"})
            issue_types = [i["type"] for i in issues]
            self.assertIn("SCRIPT_FORMAT_DETECTED", issue_types, f"Formato script não detectado em: {sample}")

        # 3b. Imunidade a Falsos Positivos em metadados e cláusulas de diálogo (R2)
        valid_prose_and_metadata = [
            "Ela disse: 'não devia estar aqui'.",
            "Vanya respondeu: \"o trono é meu\".",
            "Atitude: \"fria e calculista\"",
            "Relação: \"distante e cautelosa\"",
            "Local: \"Fortaleza de Cinzas\"",
            "Resumo: \"o herói venceu a guarda\"",
            "Custo: \"HP -2, Stamina -3\"",
            "Item: \"espada longa de aço\"",
            "Tempo: \"+2h\"",
        ]
        for sample in valid_prose_and_metadata:
            issues = check_prose_lints(sample, known_speakers={"Vespera", "Aemon", "Sylvia"})
            self.assertEqual(issues, [], f"Falso positivo incorretamente disparado em: {sample}")

        # 4. Detecção de Perguntas Clichês de Quarta Parede
        cliche_samples = [
            "A fumaça cobre o pátio. O que você faz?",
            "Os guardas cercam a torre. O que fará a seguir?",
            "A lâmina está a centímetros da garganta. Qual a sua ação?",
            "As portas foram trancadas. Como você reage?",
        ]
        for sample in cliche_samples:
            issues = check_prose_lints(sample)
            issue_types = [i["type"] for i in issues]
            self.assertIn("FOURTH_WALL_QUESTION", issue_types, f"Pergunta de 4ª parede não detectada em: {sample}")

        # 5. Sanidade das campanhas canônicas reais no review
        for cid in ["dinastia_cinzas", "imperio_valiria", "perpetuos_terra_incognita"]:
            rev = cmd_review(cid)
            prose_issues = [i for i in rev.get("issues", []) if i["type"] in ("EMOJI_DETECTED", "SCRIPT_FORMAT_DETECTED", "FOURTH_WALL_QUESTION")]
            self.assertEqual(prose_issues, [], f"Campanha canônica {cid} possui violação de prosa: {prose_issues}")

    def test_p3_machine_readable_overrides(self):
        """P3: Garante que o bloco overrides em regras.md é parseado como lista de dicionários tipados e exposto no prepare."""
        from council.helpers import parse_regras_manifest, get_campaign_overrides, find_campaign

        for cid in ["dinastia_cinzas", "imperio_valiria", "perpetuos_terra_incognita"]:
            info = find_campaign(cid)
            self.assertIn("overrides", info, f"overrides ausente no retorno de find_campaign para {cid}")
            self.assertIsInstance(info["overrides"], list)
            self.assertGreater(len(info["overrides"]), 0, f"{cid} deve possuir ao menos 1 override tipado")

            for ov in info["overrides"]:
                self.assertIn("id", ov)
                self.assertIn("type", ov)
                self.assertIn("target", ov)
                self.assertIn("value", ov)
                self.assertIn("condition", ov)
                self.assertIsInstance(ov["id"], str)
                self.assertIsInstance(ov["type"], str)

            # Verifica exposição em prepare
            prep = lazy_turn.cmd_prepare(cid, "Ação de teste", no_roll=True)
            prep_overrides = prep.get("step_1_gm_arbitration", {}).get("overrides")
            self.assertIsNotNone(prep_overrides, f"overrides ausente em step_1_gm_arbitration para {cid}")
            self.assertEqual(prep_overrides, info["overrides"])


    def test_p3_check_prose_cli_and_commit_enforcement(self):
        """P3: Garante que check-prose e commit --prose auditam a prosa e recusam violações (R1)."""
        import tempfile
        import shutil
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_check_prose, cmd_commit

        # 1. check-prose em texto limpo -> CLEAN
        clean_res = cmd_check_prose(text="Aemon sacou a espada de ferro.\n— Recuem — ordenou ele.")
        self.assertEqual(clean_res["status"], "CLEAN")
        self.assertFalse(clean_res["has_violations"])

        # 2. check-prose em texto com violação -> FAILED
        bad_res = cmd_check_prose(text="[Aemon]: Vamos avançar! 🔥 O que você faz?")
        self.assertTrue(bad_res["has_violations"])
        bad_types = [i["type"] for i in bad_res["issues"]]
        self.assertIn("EMOJI_DETECTED", bad_types)
        self.assertIn("SCRIPT_FORMAT_DETECTED", bad_types)
        self.assertIn("FOURTH_WALL_QUESTION", bad_types)

        # 3 e 4 em diretório temporário para não mutar as campanhas canônicas reais
        SCRATCH_ROOT = Path(__file__).resolve().parent.parent / ".tmp" / "test_scratch"
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(SCRATCH_ROOT)) as tmp_dir:
            temp_path = Path(tmp_dir)
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                # commit com prosa violando estilo é recusado sem --force
                reject_res = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon inspeciona a câmara.",
                    prose="Vespera: 'Não confie nos mensageiros.'",
                    force=False,
                )
                self.assertEqual(reject_res.get("prose_status"), "REJECTED")
                self.assertIn("SCRIPT_FORMAT_DETECTED", [i["type"] for i in reject_res.get("issues", [])])

                # commit com --force passa com sucesso
                force_res = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon inspeciona a câmara sob vigília.",
                    prose="Vespera: 'Não confie nos mensageiros.'",
                    force=True,
                )
                self.assertEqual(force_res.get("status"), "ok")

    def test_cmd_commit_quest_flags_execution(self):
        """P0-1: Garante que cmd_commit com --quest-complete, --quest-progress e --quest-fail roda sem UnboundLocalError."""
        import tempfile
        import shutil
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_commit, cmd_quest

        SCRATCH_ROOT = Path(__file__).resolve().parent.parent / ".tmp" / "test_scratch"
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(SCRATCH_ROOT)) as tmp_dir:
            temp_path = Path(tmp_dir)
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                cmd_quest(
                    campaign_id="dinastia_cinzas",
                    add_title="Proteger o Conselho",
                    quest_type="main",
                    objective="Vigiar os portões",
                )

                prg_res = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon reforça os portões da fortaleza.",
                    quest_progress="Q1:1",
                    force=True,
                )
                self.assertEqual(prg_res.get("status"), "ok")

                cmp_res = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon assegura a integridade do conselho.",
                    quest_complete="Q1",
                    force=True,
                )
                self.assertEqual(cmp_res.get("status"), "ok")
                self.assertTrue(any("Missão Concluída" in up for up in cmp_res.get("updates", [])))


if __name__ == "__main__":
    unittest.main()
