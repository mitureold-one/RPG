"""council.writer.py: Módulo do Escritor, mandatos editoriais de prosa e estruturas de novelização."""

import os
import subprocess
from pathlib import Path
from council.helpers import AIMEMORY_BIN


def query_aimemory(campaign_id: str, query: str) -> list:
    """Consulta o servidor ai-memory para recuperar fatos e precedentes relevantes."""
    token_path = Path(os.path.expandvars(r"%LOCALAPPDATA%\ai-memory\auth-token"))
    env = os.environ.copy()
    if token_path.exists():
        try:
            env["AI_MEMORY_AUTH_TOKEN"] = token_path.read_text("utf-8").strip()
        except Exception:
            pass

    cmd = [AIMEMORY_BIN, "search", "--workspace", "rpg", "--project", campaign_id, query, "--limit", "3"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, timeout=4)
        if proc.returncode == 0:
            lines = [
                l.strip()
                for l in proc.stdout.splitlines()
                if l.strip() and not l.startswith("INFO") and not l.startswith("2026-")
            ]
            return lines[:6]
    except Exception:
        pass
    return []


MODE_PROSE_MANDATES = {
    "gm": {
        "role": "Modo GM (Mestre de Jogo Interativo TTRPG)",
        "requires_commit": True,
        "rules": [
            "1. PRIMEIRA LINHA OBRIGATÓRIA: Cabeçalho canônico [Data, Hora] | [Local] | [Presentes] (estritamente sem emojis).",
            "2. MECÂNICA DE 3 PORTÕES: Aplique rigorosamente o resultado do dado ('dice_resolution') e deduza custos reais dos recursos da ficha.",
            "3. PROSA LITERÁRIA DE ROMANCE (SEM TETO ARTIFICIAL DE PALAVRAS): Escreva em prosa literária imersiva e sensorial no tamanho que a cena precisar para concluir seu ciclo (sem travas arbitrárias de 450 palavras). É TERMINANTEMENTE PROIBIDO usar formato de roteiro/teatro com tags na frente da fala como '[**Nome**]: — \"Fala...\"' ou 'Nome: Fala'. Use discurso direto clássico com travessão ('— Fala... — disse Fulano') integrado à respiração, movimentos corporais e psicologia do falante. Cada fala ocupa seu próprio parágrafo.",
            "4. HIERARQUIA DE REGRAS & FIDELIDADE PSICOLÓGICA (GRAUS 1 A 3): O motor universal (Grau 1) arbitra a mecânica e a integridade. As leis sociais, políticas, morais e tabus da campanha ativa em regras.md e mundo.md (Grau 2) determinam os costumes e dinâmicas de poder do cenário. Toda atitude de NPC (Grau 3) DEVE ser filtrada pela Análise de Pesos de sua ficha em npcs.md (Hexágono: Drive, Diligence, Boldness, Warmth, Empathy, Composure, Vontade e Fraquezas). Pelo menos um NPC focal DEVE tomar iniciativa concreta no cenário com base em sua Vontade Própria. Se uma cena atingir o ápice de intimidade física, aplique o Protocolo de Fade to Black (--scene-type fade_to_black).",
            "5. MESTRE ATIVO, PRESSÃO DE MUNDO & SENSIBILIDADE SITUACIONAL: O Mestre conduz o mundo com iniciativa viva, impondo perigo imediato, dilemas morais, consequências duras, avanço de relógios de facção e atrito de bastidores. PROIBIDO ser um mero espelho passivo esperando comandos [OOC] do jogador para avançar a trama. A estrutura da cena (--scene-type standard|interlude|dossier|timeskip|flashback) deve nascer da SITUAÇÃO DRAMÁTICA: se antagonistas precisam reagir ou novas facções chegam, acione interlude/parallel; se houve escândalo ou repercussão pública, entregue um dossier; se o ciclo imediato terminou e o próximo atrito é distante, salte com timeskip. Trate a Fila de Cenas como um banco adaptativo de sementes dramáticas, conciliando a agência do jogador com a iniciativa do mundo.",
            "6. PESQUISA DE WIKI PARA NOVOS NPCS: Antes de introduzir um NPC novo de obra conhecida, consulte a Wiki dele via 'search_web' e cadastre seu perfil completo (Vontade, Fraquezas, Atritos) via 'lazy_turn.py upsert-npc'.",
            "7. BARREIRA EPISTÊMICA (ANTI-METAGAMING): NPCs e vilões SÓ sabem o que presenciaram ou descobriram em cena. PROIBIDO vazar spoilers do cânone ou conversas OOC do jogador para a mente/fala dos NPCs.",
            "8. FECHAMENTO COM GANCHO DRAMÁTICO ACIONÁVEL (ZERO CORTE NO VÁCUO): O turno DEVE concluir sua batida de forma lógica e aterrissar a pressão diretamente no protagonista (um NPC exigindo resposta, uma ameaça avançando sobre ele, um dilema urgente ou uma escolha tácita). PROIBIDO cortar no meio de descrições, explicações ou em conversas laterais de NPCs que deixam o jogador sem o que fazer. PROIBIDO terminar com muletas didáticas ('O que você faz?'); a urgência deve ser diegética no mundo.",
            "9. MUDANÇA DE ESTADO OBRIGATÓRIA (CICLO EM 5 FASES): Todo turno DEVE concluir entregando um avanço ou revés tangível (recurso gasto, posição perdida/conquistada, aliança abalada, relógio avançado ou fato revelado). É ESTRITAMENTE PROIBIDO deixar a cena no mesmo status quo inicial.",
            "10. COMMIT OBRIGATÓRIO: Execute lazy_turn.py commit com --state-shift ANTES de responder.",
        ],
    },
    "narrator": {
        "role": "Modo Narrador (Story Mode / Cinematográfico)",
        "requires_commit": True,
        "rules": [
            "1. PRIMEIRA LINHA OBRIGATÓRIA: Cabeçalho canônico [Data, Hora] | [Local] | [Presentes] (estritamente sem emojis).",
            "2. PROSA LITERÁRIA DE ROMANCE: Diálogos com travessão em parágrafo isolado integrados à ação. TERMINANTEMENTE PROIBIDO formato de roteiro '[**Nome**]: — \"Fala\"'.",
            "3. FLUIDEZ CINEMATOGRÁFICA & TRIANGULAÇÃO DE NPCS: Priorize diálogos cruzados e tensões entre os próprios NPCs, expondo seus desejos divergentes e fraquezas sem efeito claque.",
            "4. BARREIRA EPISTÊMICA: Respeite o calendário atual da cena e os limites de percepção dos NPCs (zero onisciência ou vazamento OOC).",
            "5. CORTE SECO OBRIGATÓRIO: Conclua a cena no ápice cinético/dramático sem 'O que você faz?' ou qualquer pergunta didática.",
            "6. MUDANÇA DE ESTADO OBRIGATÓRIA: Toda cena cinematográfica deve avançar o tabuleiro dramático ou de facções, registrando o novo estado no commit.",
            "7. COMMIT OBRIGATÓRIO: Execute lazy_turn.py commit com --state-shift para atualizar relógio, local, presentes e resumo do turno.",
        ],
    },
    "writer": {
        "role": "Modo Escritor (Novelização / Capítulo Literário)",
        "requires_commit": False,
        "rules": [
            "1. PROSA DE ROMANCE / LIGHT NOVEL: Transforme os turnos selecionados ('source_turns') ou o prompt em um capítulo literário contínuo, denso e imersivo.",
            "2. TIPOGRAFIA EDITORIAL DE DIÁLOGOS: Cada fala de personagem deve ter seu próprio parágrafo isolado, nunca espremida em blocos maciços de texto.",
            "3. FIDELIDADE CANÔNICA & PSICOLÓGICA: Destaque as tensões laterais entre os NPCs, suas ambições próprias e seus pontos cegos.",
            "4. FECHAMENTO LITERÁRIO: Conclua o capítulo sem perguntas didáticas, notas de rodapé ou menus de escolha.",
            "5. ZERO ALTERAÇÃO DE TURNO: Não rode lazy_turn.py commit no Modo Escritor (a menos que o usuário peça para avançar a história canônica simultaneamente).",
        ],
    },
    "reviewer": {
        "role": "Modo Revisor (Auditor de Cânone, SSOT & Qualidade Literária)",
        "requires_commit": False,
        "rules": [
            "1. AUDITORIA SSOT, TEMPORAL & PERFIS DE NPCS: Verifique o relatório 'issues' (sincronia de vitais, NPCs ausentes ou com perfil oco 'INCOMPLETE_NPC_PROFILE', contaminação de atitudes e paradoxos temporais).",
            "2. AUDITORIA ANTI-CLAQUE & ANTI-METAGAMING: Aponte se os NPCs estão reagindo todos iguais como um coro passivo para o protagonista ou se faltam atritos/conversas entre eles.",
            "3. PLANO DE SANEAMENTO: Apresente um diagnóstico direto e aplique as correções via 'upsert-npc' ou 'commit' se solicitado pelo usuário.",
        ],
    },
    "architect": {
        "role": "Modo Arquiteto (Sessão Zero, Pesquisa de Wiki & Worldbuilding)",
        "requires_commit": False,
        "rules": [
            "1. PESQUISA DE WIKI OBRIGATÓRIA PARA OBRAS E NPCS CONHECIDOS: Se a campanha ou um novo NPC vier de obra existente, execute obrigatoriamente 'search_web' / 'read_url_content' na Wiki do personagem/obra ANTES de criá-lo em npcs.md.",
            "2. ANATOMIA COMPLETA DO NPC: Todo NPC deve ser cadastrado com Vontade Própria (o que busca para si), Fraquezas & Pontos Cegos (falhas emocionais/táticas) e Atritos & Laços com Outros NPCs (usando 'lazy_turn.py upsert-npc').",
            "3. CRONOLOGIA & BARREIRA DE CONHECIMENTO: Garanta que a data inicial em diario.md seja anterior aos eventos futuros e registre o que cada NPC NÃO sabe.",
            "4. FORA DO LOOP DE TURNO: Não incremente o contador de turnos do diario.md enquanto estiver projetando lore ou ajustando setup.",
        ],
    },
    "director": {
        "role": "Modo Diretor (Showrunner / Roteiro, Ritmo & Planejamento de Cenas)",
        "requires_commit": False,
        "rules": [
            "1. VISÃO PANORÂMICA DA TRAMA: Avalie o arco atual, relógios narrativos ativos, fadiga de ritmo linear e o estado das facções no mundo.md.",
            "2. BANCO DE SEMENTES DRAMÁTICAS: Gerencie a Fila de Cenas em diario.md não como trilho fixo, mas como sementes táticas adaptáveis ao efeito borboleta do jogador.",
            "3. MATRIZ SITUACIONAL DE CENAS: Projete as próximas 2 a 4 batidas dramáticas intercalando perspectivas conforme a situação exigir (interlúdio de antagonistas reagindo, dossiês diegéticos de escândalos, saltos temporais de treino/viagem ou eventos simultâneos).",
            "4. INICIATIVA DO MESTRE ATIVO: É proibido manter o mundo passivo aguardando ordens do jogador. Force dilemas externos, relógios de facção que correm contra o protagonista e consequências de ações passadas.",
            "5. PERSISTÊNCIA EM DIARIO.MD: Atualize a seção 'Planejamento de Trama & Fila de Cenas' usando 'lazy_turn.py plan' e registre marcos do arco.",
        ],
    },
}
