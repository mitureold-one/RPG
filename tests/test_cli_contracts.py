"""tests/test_cli_contracts.py: Suíte de validação de contratos de CLI, mandates e portabilidade.

Garante que nenhuma divergência de flags, caminhos ou tipos de cena seja reintroduzida.
"""

import re
import shlex
import unittest
import uuid
import shutil
from pathlib import Path

from council.writer import STRUCTURAL_SCENE_MANDATES
import lazy_turn

SCRATCH_ROOT = Path(__file__).resolve().parent.parent / ".tmp" / "test_scratch"


def make_workspace_temp_dir(prefix: str = "test_cli_") -> Path:
    """Cria diretório temporário no workspace (.tmp/test_scratch) com permissões herdadas, sem ACL restritiva 0o700."""
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    p = SCRATCH_ROOT / f"{prefix}{uuid.uuid4().hex}"
    p.mkdir(parents=True, exist_ok=True)
    return p


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
        from unittest.mock import patch
        import council.helpers as helpers
        from council.helpers import find_campaign, CURRENT_SCHEMA_VERSION

        temp_path = make_workspace_temp_dir()
        try:
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
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

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
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_check_prose, cmd_commit

        # 1. check-prose em texto limpo -> CLEAN
        clean_res = cmd_check_prose(text="Aemon sacou a espada de ferro.\n— Recuem — ordenou ele.")
        self.assertEqual(clean_res["status"], "CLEAN")
        self.assertFalse(clean_res["has_violations"])

        # 1b. check-prose com arquivo inexistente -> FILE_NOT_FOUND
        missing_res = cmd_check_prose(file_path="arquivo_inexistente_rascunho.md")
        self.assertEqual(missing_res.get("status"), "FILE_NOT_FOUND")

        # 2. check-prose em texto com violação -> FAILED
        bad_res = cmd_check_prose(text="[Aemon]: Vamos avançar! 🔥 O que você faz?")
        self.assertTrue(bad_res["has_violations"])
        bad_types = [i["type"] for i in bad_res["issues"]]
        self.assertIn("EMOJI_DETECTED", bad_types)
        self.assertIn("SCRIPT_FORMAT_DETECTED", bad_types)
        self.assertIn("FOURTH_WALL_QUESTION", bad_types)

        # 3 e 4 em diretório temporário para não mutar as campanhas canônicas reais
        temp_path = make_workspace_temp_dir()
        try:
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                # commit com prose_file inexistente falha alto sem mutar SSOT
                missing_file_res = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon inspeciona a câmara.",
                    prose_file=str(temp_path / "prosa_fantasma.md"),
                )
                self.assertEqual(missing_file_res.get("status"), "FILE_NOT_FOUND")

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
                self.assertEqual(force_res.get("prose_status"), "PASSED")

                # commit com arquivo de prosa válido passa com status PASSED
                valid_prose_file = temp_path / "boa_prosa.md"
                valid_prose_file.write_text("Aemon manteve a espada embainhada.\n— Mantenham a guarda — sussurrou ele.", encoding="utf-8")
                pass_file_res = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon organiza a sentinela dos portões.",
                    prose_file=str(valid_prose_file),
                )
                self.assertEqual(pass_file_res.get("status"), "ok")
                self.assertEqual(pass_file_res.get("prose_status"), "PASSED")
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_cmd_commit_quest_flags_execution(self):
        """P0-1: Garante que cmd_commit com --quest-complete, --quest-progress e --quest-fail roda sem UnboundLocalError."""
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_commit, cmd_quest

        temp_path = make_workspace_temp_dir()
        try:
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
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_cmd_quest_cli_operations(self):
        """P3-16: Valida cobertura direta de operações CLI em cmd_quest (add, check, block, unblock, abandon, reopen, complete, list)."""
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_quest

        temp_path = make_workspace_temp_dir()
        try:
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                # 1. Add quest com objetivo
                add_res = cmd_quest(
                    campaign_id="dinastia_cinzas",
                    add_title="Explorar as Catacumbas",
                    quest_type="side",
                    objective="Mapear a cripta inferior",
                )
                self.assertEqual(add_res["action_result"]["action"], "quest_added")
                qid = add_res["action_result"]["quest_id"]
                self.assertEqual(qid, "Q1")

                # 2. Check objective
                chk_res = cmd_quest(
                    campaign_id="dinastia_cinzas",
                    check_target=f"{qid}:1",
                )
                self.assertEqual(chk_res["action_result"]["action"], "objective_checked")

                # 3. Block quest
                blk_res = cmd_quest(
                    campaign_id="dinastia_cinzas",
                    block_id=qid,
                    reason="Desabamento do túnel",
                )
                self.assertEqual(blk_res["action_result"]["action"], "quest_block")

                # 4. Unblock quest
                unblk_res = cmd_quest(
                    campaign_id="dinastia_cinzas",
                    unblock_id=qid,
                )
                self.assertEqual(unblk_res["action_result"]["action"], "quest_unblock")

                # 5. Abandon quest
                abn_res = cmd_quest(
                    campaign_id="dinastia_cinzas",
                    abandon_id=qid,
                    reason="Missão inviável diplomaticamente",
                )
                self.assertEqual(abn_res["action_result"]["action"], "quest_abandon")

                # 6. Reopen quest
                reop_res = cmd_quest(
                    campaign_id="dinastia_cinzas",
                    reopen_id=qid,
                    reason="Novas evidências encontradas",
                )
                self.assertEqual(reop_res["action_result"]["action"], "quest_reopen")

                # 7. Complete quest com evidência
                comp_res = cmd_quest(
                    campaign_id="dinastia_cinzas",
                    complete_id=qid,
                    evidence="Relatório cartográfico entregue ao lorde",
                )
                self.assertEqual(comp_res["action_result"]["action"], "quest_complete")
                self.assertIn("Relatório cartográfico", comp_res["action_result"]["evidence"])

                # 8. List quests
                list_res = cmd_quest(
                    campaign_id="dinastia_cinzas",
                    list_quests=True,
                )
                self.assertEqual(list_res["completed_count"], 1)
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_cmd_progress_cli_operations(self):
        """P3-16: Valida cobertura direta de operações CLI em cmd_progress (list, spend-attr, spend-ability, award)."""
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_progress

        temp_path = make_workspace_temp_dir()
        try:
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                # 1. Concede XP para viabilizar level up e pontos (award code/amount)
                award_res = cmd_progress(
                    campaign_id="dinastia_cinzas",
                    award="discovery",
                    reason="Ruína ancestral decifrada",
                )
                self.assertEqual(award_res["action_result"]["xp_granted"], 25)

                # Concede XP numérico para subir de nível
                award_lvl = cmd_progress(
                    campaign_id="dinastia_cinzas",
                    award="custom:500",
                    reason="Campanha de batalha vitoriosa",
                )
                self.assertTrue(award_lvl["action_result"]["level_up"])
                self.assertGreaterEqual(award_lvl["progression"]["attribute_points"], 1)

                # 2. Gasta ponto de atributo
                attr_res = cmd_progress(
                    campaign_id="dinastia_cinzas",
                    spend_attr="FOR",
                )
                self.assertEqual(attr_res["action_result"]["stat"], "FOR")

                # 3. Gasta ponto de habilidade com treino
                # Se level 2, ganha 1 ability point
                if award_lvl["progression"]["ability_points"] >= 1:
                    abil_res = cmd_progress(
                        campaign_id="dinastia_cinzas",
                        spend_ability="Lâmina de Ferro: Causa +2 de dano",
                        training="Treino matinal nos pátios com instrutor de armas",
                    )
                    self.assertIn("Lâmina de Ferro", abil_res["action_result"]["ability"])

                # 4. List progress
                list_res = cmd_progress(
                    campaign_id="dinastia_cinzas",
                    list_progress=True,
                )
                self.assertGreater(list_res["progression"]["level"], 1)
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_duplicate_quest_complete_alert_and_reviewer_lint(self):
        """P1-7: Garante que commit duplicado gera alerta persistido no diário e reviewer dispara QUEST_REWARD_PAID_TWICE."""
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_commit, cmd_quest, cmd_review

        temp_path = make_workspace_temp_dir()
        try:
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                cmd_quest(
                    campaign_id="dinastia_cinzas",
                    add_title="Resgatar os Reféns",
                    quest_type="main",
                    objective="Infiltrar no acampamento",
                )

                # Primeiro commit: conclui com sucesso
                res1 = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon liberta os prisioneiros e retorna ao forte.",
                    quest_complete="Q1",
                    force=True,
                )
                self.assertEqual(res1.get("status"), "ok")

                # Segundo commit: tentativa duplicada para a mesma missão
                res2 = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon tenta reivindicar novamente a mesma recompensa de reféns.",
                    quest_complete="Q1",
                    force=True,
                )
                self.assertEqual(res2.get("status"), "ok")

                # Verifica que o diário gravou o alerta no corpo do turno
                diario_content = (temp_path / "dinastia_cinzas" / "diario.md").read_text(encoding="utf-8")
                self.assertIn("Tentativa de pagamento duplicado de XP barrada", diario_content)

                # Executa review e verifica que o lint QUEST_REWARD_PAID_TWICE dispara com severidade CRITICAL
                rev = cmd_review("dinastia_cinzas")
                issue_types = [i["type"] for i in rev.get("issues", [])]
                self.assertIn("QUEST_REWARD_PAID_TWICE", issue_types)
                target_issue = next(i for i in rev["issues"] if i["type"] == "QUEST_REWARD_PAID_TWICE")
                self.assertEqual(target_issue["severity"], "CRITICAL")
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_clock_resolve_xp_and_ledger(self):
        """P1-4: Garante que --clock-resolve no commit e --resolve no clock concedem XP unlinked e registram no ledger."""
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_clock, cmd_commit
        from council.ssot import parse_progression_from_ficha, parse_xp_ledger_from_diario

        temp_path = make_workspace_temp_dir()
        try:
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                # Adiciona relógio desvinculado
                cmd_clock(campaign_id="dinastia_cinzas", add_name="Cerco dos Rebeldes", max_steps=4)

                # Resolve via cmd_commit --clock-resolve
                c_res = cmd_commit(
                    campaign_id="dinastia_cinzas",
                    summary="Aemon dissipa o cerco por completo.",
                    clock_resolve="Cerco dos Rebeldes",
                    force=True,
                )
                self.assertEqual(c_res.get("status"), "ok")

                ficha_file = temp_path / "dinastia_cinzas" / "ficha.md"
                diario_file = temp_path / "dinastia_cinzas" / "diario.md"
                prog = parse_progression_from_ficha(ficha_file)
                self.assertEqual(prog["xp"], 40)

                ledger = parse_xp_ledger_from_diario(diario_file)
                self.assertTrue(any("Cerco dos Rebeldes" in e["reason"] for e in ledger))

                # Adiciona outro relógio e resolve via cmd_clock --resolve
                cmd_clock(campaign_id="dinastia_cinzas", add_name="Infiltração Noturna", max_steps=4)
                clk_res = cmd_clock(campaign_id="dinastia_cinzas", resolve_name="Infiltração Noturna")
                self.assertEqual(clk_res["action_result"].get("xp_granted"), 40)

                prog2 = parse_progression_from_ficha(ficha_file)
                self.assertEqual(prog2["xp"], 80)
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_arc_milestone_xp_and_ledger(self):
        """P1-4: Garante que cmd_arc --milestone concede +80 XP e registra no ledger."""
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_arc
        from council.ssot import parse_progression_from_ficha, parse_xp_ledger_from_diario

        temp_path = make_workspace_temp_dir()
        try:
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                arc_res = cmd_arc(
                    campaign_id="dinastia_cinzas",
                    milestone="A Queda do Usurpador e a Coroação de Aemon",
                )
                self.assertEqual(arc_res["action_result"].get("arc_milestone_xp"), 80)

                ficha_file = temp_path / "dinastia_cinzas" / "ficha.md"
                diario_file = temp_path / "dinastia_cinzas" / "diario.md"
                prog = parse_progression_from_ficha(ficha_file)
                self.assertEqual(prog["xp"], 80)

                ledger = parse_xp_ledger_from_diario(diario_file)
                self.assertTrue(any("A Queda do Usurpador" in e["reason"] for e in ledger))
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_cmd_faction_cli_contracts(self):
        """009: Garante contratos de CLI para o subcomando faction e flags no commit."""
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_faction

        # Valida que o parser aceita todas as flags especificadas
        args_list = self.parser.parse_args(["faction", "--campaign", "dinastia_cinzas", "--list", "--json"])
        self.assertEqual(args_list.cmd, "faction")
        self.assertTrue(args_list.list)
        self.assertTrue(args_list.json)

        args_add = self.parser.parse_args([
            "faction", "--campaign", "dinastia_cinzas", "--add", "Ordem Solar",
            "--power", "4", "--scale", "regional", "--clock", "Cruzada Solar", "--desc", "Cavaleiros sagrados"
        ])
        self.assertEqual(args_add.add, "Ordem Solar")
        self.assertEqual(args_add.power, 4)
        self.assertEqual(args_add.scale, "regional")

        args_rep = self.parser.parse_args(["faction", "--campaign", "dinastia_cinzas", "--rep", "Ordem Solar:+1", "--reason", "Doação"])
        self.assertEqual(args_rep.rep, "Ordem Solar:+1")
        self.assertEqual(args_rep.reason, "Doação")

        args_tick = self.parser.parse_args(["faction", "--campaign", "dinastia_cinzas", "--tick"])
        self.assertTrue(args_tick.tick)

        # Valida flags no subcomando commit
        args_com = self.parser.parse_args([
            "commit", "--campaign", "dinastia_cinzas", "--summary", "Ação",
            "--faction-rep", "Ordem Solar:+1", "--faction-favor", "Ordem Solar:+1", "--faction-debt", "Ordem Solar:+0"
        ])
        self.assertEqual(args_com.faction_rep, "Ordem Solar:+1")
        self.assertEqual(args_com.faction_favor, "Ordem Solar:+1")
        self.assertEqual(args_com.faction_debt, "Ordem Solar:+0")

        # Executa em sandbox isolado
        temp_path = make_workspace_temp_dir()
        try:
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                res = cmd_faction(campaign_id="dinastia_cinzas", list_factions=True)
                self.assertEqual(res["campaign"], "dinastia_cinzas")
                self.assertIsInstance(res.get("factions"), list)

                add_res = cmd_faction(
                    campaign_id="dinastia_cinzas",
                    add_name="Fé Purificadora",
                    power=4,
                    scale="regional",
                    desc="Inquisidores devotos",
                )
                self.assertEqual(add_res["action_result"].get("action"), "faction_added")
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_fase_01_5_valiria_calendar_and_strict_faction_rep(self):
        """Fase 01.5: Calendário completo de Valíria (+30d avança mês) e faction --rep estrito com --create."""
        from unittest.mock import patch
        import council.helpers as helpers
        from lazy_turn import cmd_faction, cmd_commit
        from council.factions import parse_reputation_from_ficha

        temp_path = make_workspace_temp_dir()
        try:
            # 1. Calendário de Valíria com avanço de +30d atravessando de Ventania para Geada
            shutil.copytree(self.root_dir / "campaigns" / "imperio_valiria", temp_path / "imperio_valiria")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                res_time = cmd_commit(
                    campaign_id="imperio_valiria",
                    summary="Kon-El realiza patrulha estendida durante trinta dias.",
                    time_str="+30d",
                    force=True,
                )
                self.assertEqual(res_time.get("status"), "ok")
                # 04 de Ventania + 30 dias -> 4 de Geada de 304
                self.assertIn("4 de Geada de 304", res_time["canonical_header_for_response"])

            # 2. faction --rep estrito em dinastia_cinzas
            shutil.copytree(self.root_dir / "campaigns" / "dinastia_cinzas", temp_path / "dinastia_cinzas")
            with patch.object(helpers, "CAMPAIGN_DIRS", [temp_path]):
                # Facção conhecida em mundo.md (Conselho dos Lordes de Cinzas) -> passa sem --create
                res_known = cmd_faction("dinastia_cinzas", rep="Conselho dos Lordes de Cinzas:+1")
                self.assertEqual(res_known.get("action_result", {}).get("action"), "reputation_updated")

                # Typo / facção desconhecida sem --create -> erro estrito e não altera ficha
                res_typo = cmd_faction("dinastia_cinzas", rep="Conselhoo:+1")
                self.assertIn("error", res_typo)
                self.assertIn("não encontrada em mundo.md", res_typo["error"])

                ficha_reps = parse_reputation_from_ficha(temp_path / "dinastia_cinzas" / "ficha.md")
                self.assertNotIn("conselhoo", ficha_reps)

                # Com --create explícito -> permite cadastro intencional avulso
                res_create = cmd_faction("dinastia_cinzas", rep="Conselhoo:+1", create=True)
                self.assertEqual(res_create.get("action_result", {}).get("action"), "reputation_updated")
                ficha_reps_after = parse_reputation_from_ficha(temp_path / "dinastia_cinzas" / "ficha.md")
                self.assertIn("conselhoo", ficha_reps_after)
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
