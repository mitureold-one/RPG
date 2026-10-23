"""Criação de campanha nova a partir dos templates oficiais."""

import os
from pathlib import Path

from adapters.persistence.files import atomic_write_text
from campaign import locator

TEMPLATES_DIR = Path(os.environ.get("RPGPRO_TEMPLATES_DIR", str(locator.BASE_DIR / "templates")))


def init_campaign_from_templates(
    campaign_id: str,
    title: str = "",
    protagonist_name: str = "Protagonista",
    start_date: str = "01 de Outubro de 2026, 12:00",
    start_loc: str = "Local Inicial",
) -> dict:
    """Inicializa os 5 arquivos canônicos em campaigns/<campaign_id>/ a partir dos templates oficiais."""
    dirs = locator._get_campaign_dirs()
    if not dirs or not dirs[0].exists():
        return {"error": "Diretório de campanhas não encontrado."}

    camp_dir = dirs[0] / campaign_id
    if camp_dir.exists():
        return {"error": f"A campanha '{campaign_id}' já existe em {camp_dir}."}

    if not TEMPLATES_DIR.exists():
        return {"error": f"Diretório de templates não encontrado em {TEMPLATES_DIR}."}

    camp_dir.mkdir(parents=True, exist_ok=True)
    clean_title = title.strip() or campaign_id.replace("_", " ").title()

    replacements = {
        "{{TITULO_CAMPANHA}}": clean_title,
        "{{NOME_PROTAGONISTA}}": protagonist_name.strip() or "Protagonista",
        "{{DATA_HORA_INICIAL}}": start_date.strip(),
        "{{LOCAL_INICIAL}}": start_loc.strip(),
        "{{NOME_CENA_INICIAL}}": "Prólogo / Incidente Inicial",
        "{{NPCS_PRESENTES_INICIAIS}}": "Aliado Inicial",
        "{{HP_MAX}}": "25",
        "{{STAMINA_MAX}}": "20",
        "{{ENERGIA_MAX}}": "30",
        "{{CLASSIFICACAO_OU_ARQUETIPO}}": "Especialista Tático",
        "{{DESCRICAO_FISICA_E_PRESENCA}}": "Postura alerta, físico condicionado e olhos vigilantes.",
        "{{ORIGEM_E_TRAUMA_CENTRAL}}": "Passado marcado por desafios que forjaram sua disciplina.",
        "{{DESCRICAO_DA_HABILIDADE_INATA}}": "Capacidade refinada de leitura tática sob estresse.",
        "{{DESCRICAO_DO_ESTILO_DE_LUTA}}": "Combate pragmático visando controle de espaço e neutralização rápida.",
        "{{ITEM_1}}": "Arma principal de combate",
        "{{ITEM_2}}": "Uniforme reforçado de viagem",
        "{{ITEM_3}}": "Kit de suprimentos de campo",
        "{{RESUMO_DO_INCIDENTE_INICIAL_E_OBJETIVO_DA_CENA}}": "A calmaria inicial é rompida por um acontecimento que exige reação imediata.",
        "{{NOME_DO_RELOGIO}}": "Ameaça Iminente",
        "{{EVENTO_DE_RUPTURA_AO_COMPLETAR}}": "Invasão ou colapso da posição atual",
        "{{NOME_MISSAO_PRINCIPAL}}": f"Estabelecer Posição em {clean_title}",
        "{{CONTRATANTE_OU_FACCAO}}": "Liderança Local",
        "{{PRIMEIRO_OBJETIVO_DA_MISSAO}}": "Reconhecer o perímetro e identificar ameaças imediatas",
        "{{SEGUNDO_OBJETIVO_DA_MISSAO}}": "Firmar contato com o Aliado Inicial e assegurar suprimentos",
        "{{TITULO_DO_ARCO_ATUAL}}": f"Arco 1: O Despertar de {clean_title}",
        "{{DILEMA_OU_CONFLITO_CENTRAL_DO_ARCO}}": "Como estabelecer uma base segura diante da resistência inicial?",
        "{{RESUMO_FACTUAL_DA_PRIMEIRA_RESOLUCAO}}": "Início da jornada e reconhecimento inicial do perímetro",
        "{{PRIMEIRA_MUDANCA_CONCRETA_DE_ESTADO_NO_TABULEIRO}}": "Posição inicial estabelecida; primeiro contato registrado",
        "{{NOME_NPC_1}}": "Aliado Inicial",
        "{{GRAU_OU_POSICAO_SOCIAL}}": "Combatente Veterano",
        "{{PAPEL_NARRATIVO_MENTOR_RIVAL_INFORMANTE}}": "Guia / Apoio Tático",
        "{{PAPEL_NARRATIVO}}": "Oposição Local",
        "{{ESTADO_EMOCIONAL_E_POSTURA_IMEDIATA}}": "Em guarda, avaliando o ambiente",
        "{{MICRO_EXPRESSAO_AO_SER_CONTRARIADO_OU_PRESSIONADO}}": "cerra os maxilares e desvia o olhar com desconfiança",
        "{{MICRO_EXPRESSAO_AO_SER_CONTRARIADO}}": "sorriso tenso e respiração contida",
        "{{O_QUE_BUSCA_PARA_SI_INDEPENDENTE_DO_PROTAGONISTA}}": "Proteger os seus e garantir recursos para a sobrevivência",
        "{{O_QUE_BUSCA_PARA_SI}}": "Expandir sua área de influência",
        "{{VULNERABILIDADE_EMOCIONAL_OU_FALHA_TATICA}}": "Teimosia em admitir erros e excesso de confiança",
        "{{FRAQUEZAS_E_PONTOS_CEGOS}}": "Subestimar adversários novos",
        "{{LACOS_E_RIVALIDADES_COM_OUTROS_PERSONAGENS}}": "Mantém trégua cautelosa com as autoridades locais",
        "{{ATRIGOS_E_LACOS}}": "Competição por recursos com o Aliado Inicial",
        "{{VESTIMENTAS_SILHUETA_E_TOM_DE_VOZ}}": "Roupas escuras funcionais, silhueta firme e voz áspera",
        "{{APARENCIA_E_VOZ}}": "Postura imponente e tom autoritário",
        "{{NOME_NPC_2}}": "Rival Inicial",
        "{{DESCRICAO_DO_MUNDO_ATMOSFERA_E_PREMISSA}}": f"O universo de {clean_title} é marcado por conflitos territoriais e tensões veladas.",
        "{{EVENTOS_HISTORICOS_CONSOLIDADOS_QUE_MOLDARAM_O_MUNDO}}": "Guerras passadas deixaram cicatrizes profundas nas instituições atuais.",
        "{{EVENTOS_OU_CRISES_AGENDADAS_NO_MUNDO_AINDA_DESCONHECIDAS_PELO_PROTAGONISTA}}": "Uma facção nas sombras prepara uma ruptura na ordem estabelecida.",
        "{{LOCAL_1}}": start_loc.strip(),
        "{{DESCRICAO_DO_LOCAL_1_E_IMPORTANCIA}}": "Ponto nevrálgico onde os acontecimentos iniciais convergem.",
        "{{LOCAL_2}}": "Posto Avançado",
        "{{DESCRICAO_DO_LOCAL_2_E_IMPORTANCIA}}": "Área de fronteira frequentemente disputada.",
        "{{FACCAO_1}}": "Ordem Estabelecida",
        "{{OBJETIVOS_E_INFLUENCIA_DA_FACCAO_1}}": "Manter o controle institucional a qualquer preço.",
        "{{FACCAO_2}}": "Insurgentes das Sombras",
        "{{OBJETIVOS_E_INFLUENCIA_DA_FACCAO_2}}": "Desestabilizar o poder local.",
        "{{LEI_OU_TABU_CULTURAL_1}}": "Quebrar um pacto formal acarreta desonra ou punição irrevogável.",
        "{{LEI_OU_TABU_CULTURAL_2}}": "Conflitos armados em solo neutro são estritamente proibidos.",
        "{{CALIBRACAO_FAIXA_10}}": "Perceber emboscadas óbvias ou negociar cooperação com aliados pragmáticos sob tensão inicial.",
        "{{CALIBRACAO_FAIXA_15}}": "Manobras táticas sob fogo cruzado, infiltração em perímetros vigiados ou persuasão de suspeitos relutantes.",
        "{{CALIBRACAO_FAIXA_20}}": "Superar combatentes de elite ou resistir a venenos/feitiços potentes.",
        "{{CALIBRACAO_FAIXA_25}}": "Feitos lendários contra calamidades ou anomalias supremas.",
        "{{RECURSO_ESPECIAL}}": "Energia Especial",
        "{{DESCRICAO_E_CUSTOS_DE_HABILIDADES_ESPECIAIS}}": "Consumido ao ativar técnicas superiores.",
        "{{REGRA_ESPECIAL_DO_UNIVERSO_1}}": "O esforço extremo sem descanso gera exaustão imediata.",
        "{{REGRA_ESPECIAL_DO_UNIVERSO_2}}": "Habilidades ativas exigem concentração ou gestos específicos.",
        "{{ALIADO_INICIAL}}": "Aliado Inicial",
        "{{RELACAO_E_DIVIDA}}": "Relação de respeito forjada em combate e confiança mútua",
        "{{RIVAL_INICIAL}}": "Rival Inicial",
        "{{MOTIVO_DO_ATRITO}}": "Divergência de métodos e objetivos em rota de colisão",
        "{{FACCAO_OU_AFILIACAO_OU_INDEPENDENTE}}": "Independente",
        "{{MARCO_INICIAL_PROTAGONISTA}}": "Assumiu a liderança do destacamento e superou o incidente inicial",
        "{{RELACAO_NPC_1_COM_PROTAGONISTA}}": "Confiança +1 (Respeito cauteloso e cooperação tática em campo)",
        "{{RELACAO_NPC_2_COM_PROTAGONISTA}}": "Confiança -1 (Desdém velado e postura desafiadora)",
        "{{DINAMICA_INTER_FACCOES}}": "Guerra fria ideológica e disputa clandestina por influência territorial",
        "{{ANTAGONISTAS_OU_RIVAIS}}": "Facção Opositora",
        "{{CONSPIRACAO_OU_AVANCO_DE_BASTIDORES_SEM_PROTAGONISTA}}": "Movimentação estratégica nos bastidores para consolidação de poder territorial",
        "{{PRIMEIRO_MARCO_DECISIVO_DO_ARCO}}": "Consolidação da primeira vitória tática e revelação de segredo oculto",
    }

    files_map = {
        "ficha.md": TEMPLATES_DIR / "ficha.template.md",
        "diario.md": TEMPLATES_DIR / "diario.template.md",
        "npcs.md": TEMPLATES_DIR / "npcs.template.md",
        "mundo.md": TEMPLATES_DIR / "mundo.template.md",
        "regras.md": TEMPLATES_DIR / "regras.template.md",
    }

    created = []
    for target_name, tmpl_path in files_map.items():
        if tmpl_path.exists():
            content = tmpl_path.read_text(encoding="utf-8")
            for placeholder, val in replacements.items():
                content = content.replace(placeholder, val)
            atomic_write_text(camp_dir / target_name, content)
            created.append(target_name)

    return {
        "status": "ok",
        "campaign": campaign_id,
        "path": str(camp_dir),
        "title": clean_title,
        "created_files": created,
    }
