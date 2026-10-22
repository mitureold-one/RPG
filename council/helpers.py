"""council.helpers: Constantes universais, localização de campanhas e manipulação de tempo."""

import contextlib
import datetime
import os
import re
import shutil
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

CAMPAIGN_DIRS = [
    Path(os.environ.get("RPGPRO_CAMPAIGNS_DIR", str(BASE_DIR / "campaigns"))),
]

AIMEMORY_BIN = os.path.expandvars(r"%LOCALAPPDATA%\ai-memory\ai-memory.exe")

MONTHS_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

MONTHS_MAP = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}


TEMPLATES_DIR = Path(os.environ.get("RPGPRO_TEMPLATES_DIR", str(BASE_DIR / "templates")))


CURRENT_SCHEMA_VERSION = 1
DEFAULT_RULESET = "d20_3gates"


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Grava um arquivo de forma atômica no mesmo diretório.

    A escrita ocorre em um temporário exclusivo; o arquivo final só é
    substituído por ``os.replace`` depois que todo o conteúdo foi gravado e
    sincronizado. Assim, uma falha no meio da operação não trunca o SSOT.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with open(tmp, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            try:
                shutil.copymode(target, tmp)
            except OSError:
                pass
        # No Windows, um leitor concorrente (por exemplo, o sync_daemon)
        # pode manter o arquivo aberto por alguns milissegundos.
        for attempt in range(5):
            try:
                os.replace(tmp, target)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


@contextlib.contextmanager
def campaign_lock(campaign_dir: Path, timeout: float = 10.0):
    """Serializa escritores de uma campanha usando um lock de arquivo.

    O lock é cooperativo: protege apenas processos que usam esta função.
    Em Windows usa ``msvcrt.locking``; em POSIX usa ``fcntl.flock``.
    """
    lock_path = Path(campaign_dir) / ".campaign.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+", encoding="utf-8")
    acquired = False
    try:
        # Windows não consegue travar um byte além do EOF; garante 1 byte.
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write("0")
            handle.flush()
        deadline = time.monotonic() + max(0.1, float(timeout))
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Não foi possível obter o lock da campanha '{campaign_dir}' em {timeout}s."
                    ) from exc
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def get_available_rulesets() -> list[str]:
    """Lista todos os rulesets disponíveis no diretório rulesets/."""
    rulesets_dir = BASE_DIR / "rulesets"
    if not rulesets_dir.is_dir():
        return [DEFAULT_RULESET]
    return sorted(p.stem for p in rulesets_dir.glob("*.py") if p.stem != "__init__")


def load_ruleset(system_name: str = DEFAULT_RULESET):
    """Carrega dinamicamente o módulo de regras do sistema indicado. Falha alto se não existir."""
    clean_name = (system_name or DEFAULT_RULESET).strip().lower()
    if clean_name == "default":
        clean_name = DEFAULT_RULESET
    try:
        import importlib
        return importlib.import_module(f"rulesets.{clean_name}")
    except ModuleNotFoundError:
        available = get_available_rulesets()
        raise ValueError(
            f"Ruleset '{clean_name}' não encontrado. Disponíveis: {', '.join(available)}"
        )


def _normalize_calendar(raw) -> dict:
    """Normaliza o bloco ``calendar:`` do manifesto de regras.md.

    Formato aceito::

        calendar:
          months: ["Ventania", "Geada", "..."]
          days_per_month: 30          # int ou lista alinhada a months
    """
    if not isinstance(raw, dict):
        return {}
    raw_months = raw.get("months")
    if not isinstance(raw_months, list):
        return {}
    months = [str(m).strip() for m in raw_months if str(m).strip()]
    if not months:
        return {}

    raw_days = raw.get("days_per_month", 30)
    if isinstance(raw_days, int):
        days = [max(1, raw_days)] * len(months)
    elif isinstance(raw_days, list):
        days = []
        for value in raw_days[: len(months)]:
            try:
                days.append(max(1, int(value)))
            except (TypeError, ValueError):
                days.append(30)
        days.extend([30] * (len(months) - len(days)))
    else:
        days = [30] * len(months)
    return {"months": months, "days_per_month": days}


def parse_regras_manifest(regras_path: Path) -> dict:
    """Extrai e parseia o manifesto de mecânica e overrides tipados de regras.md."""
    manifest = {
        "system": DEFAULT_RULESET,
        "ruleset": DEFAULT_RULESET,
        "overrides": [],
        "calendar": {},
    }
    if not regras_path or not regras_path.is_file():
        return manifest

    text = regras_path.read_text(encoding="utf-8")
    m = re.search(r"```yaml(?:[:a-zA-Z_-]*)\n(.*?)\n```", text, re.DOTALL)
    if not m:
        m_sys = re.search(r"system:\s*([a-zA-Z0-9_\-]+)", text)
        if m_sys:
            manifest["system"] = m_sys.group(1).strip()
            manifest["ruleset"] = m_sys.group(1).strip()
        return manifest

    yaml_content = m.group(1)
    parsed = None
    try:
        import yaml
        parsed = yaml.safe_load(yaml_content)
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        if "system" in parsed:
            manifest["system"] = str(parsed["system"]).strip()
        if "ruleset" in parsed:
            manifest["ruleset"] = str(parsed["ruleset"]).strip()
        else:
            manifest["ruleset"] = manifest["system"]
        if "overrides" in parsed and isinstance(parsed["overrides"], list):
            valid_overrides = []
            for item in parsed["overrides"]:
                if isinstance(item, dict):
                    ov = {
                        "id": str(item.get("id", "custom_override")).strip(),
                        "type": str(item.get("type", "custom")).strip(),
                        "target": str(item.get("target", "general")).strip(),
                        "value": item.get("value", True),
                        "condition": str(item.get("condition", item.get("effect", ""))).strip(),
                    }
                    valid_overrides.append(ov)
            manifest["overrides"] = valid_overrides
        manifest["calendar"] = _normalize_calendar(parsed.get("calendar"))
    else:
        # Fallback minimalista de chave-valor nativo (stdlib)
        m_sys = re.search(r"system:\s*([a-zA-Z0-9_\-]+)", yaml_content)
        if m_sys:
            manifest["system"] = m_sys.group(1).strip()
            manifest["ruleset"] = m_sys.group(1).strip()
        override_blocks = re.findall(r"-\s*id:\s*([^\n]+)(.*?)(?=\n\s*-\s*id:|\Z)", yaml_content, re.DOTALL)
        for ov_id, ov_body in override_blocks:
            def _extract_field(field_name, default=""):
                mf = re.search(rf"{field_name}:\s*([^\n]+)", ov_body)
                return mf.group(1).strip().strip('"\'') if mf else default
            manifest["overrides"].append({
                "id": ov_id.strip().strip('"\''),
                "type": _extract_field("type", "custom"),
                "target": _extract_field("target", "general"),
                "value": _extract_field("value", True),
                "condition": _extract_field("condition", _extract_field("effect", "")),
            })

    return manifest


def get_campaign_overrides(campaign_id: str) -> list:
    """Retorna a lista de overrides mecânicos tipados de regras.md da campanha."""
    for base in CAMPAIGN_DIRS:
        if not base.exists():
            continue
        regras_path = base / campaign_id / "regras.md"
        if regras_path.is_file():
            manifest = parse_regras_manifest(regras_path)
            return manifest.get("overrides", [])
    return []


def get_campaign_system(campaign_id: str) -> str:
    """Extrai o identificador de sistema de resolução declarado em regras.md."""
    for base in CAMPAIGN_DIRS:
        if not base.exists():
            continue
        regras_path = base / campaign_id / "regras.md"
        if regras_path.is_file():
            manifest = parse_regras_manifest(regras_path)
            return manifest.get("system", DEFAULT_RULESET)
    return DEFAULT_RULESET


def find_campaign(campaign_id: str):
    """Localiza e valida a pasta da campanha em Markdown (SSOT).
    
    Falha alto (raise FileNotFoundError / ValueError) se a campanha existir mas for inválida,
    ausente de diario.md, sem schema_version declarado ou com ruleset desconhecido.
    Retorna None se o diretório da campanha não existir.
    """
    for base in CAMPAIGN_DIRS:
        if not base.exists():
            continue
        camp_dir = base / campaign_id
        if camp_dir.is_dir():
            diario_path = camp_dir / "diario.md"
            if not diario_path.is_file():
                raise FileNotFoundError(
                    f"Campanha '{campaign_id}' corrompida: 'diario.md' não encontrado em {camp_dir}."
                )
            diario_text = diario_path.read_text(encoding="utf-8")
            m_schema = re.search(r"schema_version:\s*(\d+)", diario_text)
            if not m_schema:
                m_schema = re.search(r"<!--\s*schema_version:\s*(\d+)\s*-->", diario_text)
            if not m_schema:
                raise ValueError(
                    f"Campanha '{campaign_id}' inválida: 'diario.md' não declara 'schema_version' (ex: 'schema_version: 1')."
                )
            version = int(m_schema.group(1))
            if version > CURRENT_SCHEMA_VERSION:
                raise ValueError(
                    f"Campanha '{campaign_id}' incompatível: schema_version {version} é superior à versão suportada pelo motor ({CURRENT_SCHEMA_VERSION})."
                )
            manifest = parse_regras_manifest(camp_dir / "regras.md")
            system_name = manifest.get("system", DEFAULT_RULESET)
            load_ruleset(system_name)
            return {
                "id": campaign_id,
                "type": "markdown",
                "dir": camp_dir,
                "ficha": camp_dir / "ficha.md",
                "diario": diario_path,
                "npcs": camp_dir / "npcs.md",
                "mundo": camp_dir / "mundo.md",
                "regras": camp_dir / "regras.md",
                "schema_version": version,
                "system": system_name,
                "overrides": manifest.get("overrides", []),
                "calendar": manifest.get("calendar", {}),
            }
    return None


def init_campaign_from_templates(
    campaign_id: str,
    title: str = "",
    protagonist_name: str = "Protagonista",
    start_date: str = "01 de Outubro de 2026, 12:00",
    start_loc: str = "Local Inicial",
) -> dict:
    """Inicializa os 5 arquivos canônicos em campaigns/<campaign_id>/ a partir dos templates oficiais."""
    if not CAMPAIGN_DIRS or not CAMPAIGN_DIRS[0].exists():
        return {"error": "Diretório de campanhas não encontrado."}

    camp_dir = CAMPAIGN_DIRS[0] / campaign_id
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


def parse_time_increment(val_str: str) -> int:
    """Converte incrementos como '+60d', '+2mo', '+1y', '+2h' e '+30m' em minutos.

    ``m`` é sempre minuto; meses usam ``mo``/``mes``/``meses``.
    """
    clean = val_str.strip().lstrip("+").lower()
    m = re.match(r"^(\d+)\s*([a-zçã]+)?$", clean)
    if not m:
        return 0
    num = int(m.group(1))
    unit = (m.group(2) or "m").lower()
    if unit in ("m", "min", "mins", "minuto", "minutos"):
        return num
    elif unit in ("h", "hr", "hrs", "hora", "horas"):
        return num * 60
    elif unit in ("d", "dia", "dias"):
        return num * 1440
    elif unit in ("w", "sem", "semana", "semanas"):
        return num * 1440 * 7
    elif unit in ("mo", "mes", "mês", "meses"):
        return num * 1440 * 30
    elif unit in ("y", "a", "ano", "anos"):
        return num * 1440 * 365
    return num


def advance_time_str(dt_str: str, minutes: int, calendar: dict | None = None) -> str:
    """Avança data e hora respeitando dias, meses, anos ou horários simples.

    ``calendar`` é o bloco opcional ``calendar:`` de ``regras.md`` com
    ``months`` e ``days_per_month``. Sem calendário, aceita meses gregorianos
    e anos de 1 a 4 dígitos. Datas com mês desconhecido levantam ``ValueError``
    em vez de serem convertidas silenciosamente para Janeiro.
    """
    if minutes == 0:
        return dt_str

    cal = calendar or {}
    months = cal.get("months") or []
    days_per_month = cal.get("days_per_month") or []

    # Padrão A: 'DD de Mês de YYYY, HH:MM' ou 'DD de Mês de YYYY'
    m_full = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçÇãÃõÕéÉêÊíÍóÓúÚ]+)\s+de\s+(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?",
        dt_str,
        re.IGNORECASE,
    )
    if m_full:
        day = int(m_full.group(1))
        m_name = m_full.group(2)
        year = int(m_full.group(3))
        h = int(m_full.group(4)) if m_full.group(4) else 12
        mins = int(m_full.group(5)) if m_full.group(5) else 0
        has_time = bool(m_full.group(4))

        if months:
            month_idx = next(
                (i for i, name in enumerate(months) if name.casefold() == m_name.casefold()),
                None,
            )
            if month_idx is None:
                raise ValueError(
                    f"Mês '{m_name}' não consta no calendário da campanha. "
                    f"Declare 'calendar.months' em regras.md."
                )
            total = h * 60 + mins + minutes
            day_delta = total // 1440
            rem = total % 1440
            new_day = day + day_delta
            new_idx = month_idx
            if isinstance(days_per_month, int):
                days = [max(1, days_per_month)] * len(months)
            else:
                days = list(days_per_month or [])
                if len(days) < len(months):
                    days.extend([30] * (len(months) - len(days)))
            while new_day > days[new_idx]:
                new_day -= days[new_idx]
                new_idx += 1
                if new_idx >= len(months):
                    new_idx = 0
                    year += 1
            new_h, new_m = divmod(rem, 60)
            formatted = f"{new_day} de {months[new_idx]} de {year}"
            if has_time:
                formatted += f", {new_h:02d}:{new_m:02d}"
            return dt_str[:m_full.start()] + formatted + dt_str[m_full.end():]

        month_num = MONTHS_MAP.get(m_name.lower())
        if not month_num:
            # Fallback conservador para calendários diegéticos ainda não
            # declarados: permite avanços que permaneçam no mesmo mês (30 dias)
            # sem inventar nomes de meses vizinhos. Qualquer travessia de mês
            # exige o bloco calendar em regras.md.
            total = h * 60 + mins + minutes
            day_delta = total // 1440
            rem = total % 1440
            new_day = day + day_delta
            if 1 <= new_day <= 30:
                new_h, new_m = divmod(rem, 60)
                formatted = f"{new_day} de {m_name} de {year}"
                if has_time:
                    formatted += f", {new_h:02d}:{new_m:02d}"
                return dt_str[:m_full.start()] + formatted + dt_str[m_full.end():]
            raise ValueError(
                f"Mês '{m_name}' não é gregoriano e o avanço ultrapassa o mês. "
                f"Declare 'calendar.months' em regras.md para atravessar meses."
            )
        try:
            cur_dt = datetime.datetime(year, month_num, day, h, mins)
        except ValueError as exc:
            raise ValueError(f"Data inválida '{dt_str}': {exc}") from exc
        new_dt = cur_dt + datetime.timedelta(minutes=minutes)
        new_month_name = MONTHS_PT[new_dt.month]
        if has_time:
            formatted = f"{new_dt.day} de {new_month_name} de {new_dt.year}, {new_dt.hour:02d}:{new_dt.minute:02d}"
        else:
            formatted = f"{new_dt.day} de {new_month_name} de {new_dt.year}"
        return dt_str[:m_full.start()] + formatted + dt_str[m_full.end():]

    # Padrão B: 'DD/MM/YYYY, HH:MM'
    m_slash = re.search(r"(\d{1,2})/(\d{1,2})/(\d{1,4})(?:,\s*(\d{1,2}):(\d{2}))?", dt_str)
    if m_slash:
        day, month, year = int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3))
        h = int(m_slash.group(4)) if m_slash.group(4) else 12
        mins = int(m_slash.group(5)) if m_slash.group(5) else 0
        has_time = bool(m_slash.group(4))
        try:
            cur_dt = datetime.datetime(year, month, day, h, mins)
        except ValueError as exc:
            raise ValueError(f"Data inválida '{dt_str}': {exc}") from exc
        new_dt = cur_dt + datetime.timedelta(minutes=minutes)
        if has_time:
            formatted = f"{new_dt.day:02d}/{new_dt.month:02d}/{new_dt.year}, {new_dt.hour:02d}:{new_dt.minute:02d}"
        else:
            formatted = f"{new_dt.day:02d}/{new_dt.month:02d}/{new_dt.year}"
        return dt_str[:m_slash.start()] + formatted + dt_str[m_slash.end():]

    # Padrão C: 'Dia X, HH:MM'
    m_dia = re.search(r"Dia\s+(\d+)(?:,\s*(\d{1,2}):(\d{2}))?", dt_str, re.IGNORECASE)
    if m_dia:
        day_num = int(m_dia.group(1))
        h = int(m_dia.group(2)) if m_dia.group(2) else 12
        mins = int(m_dia.group(3)) if m_dia.group(3) else 0
        total_mins = h * 60 + mins + minutes
        days_added = total_mins // 1440
        rem_mins = total_mins % 1440
        new_day = day_num + days_added
        new_h = rem_mins // 60
        new_m = rem_mins % 60
        has_time = bool(m_dia.group(2))
        if has_time:
            formatted = f"Dia {new_day}, {new_h:02d}:{new_m:02d}"
        else:
            formatted = f"Dia {new_day}"
        return dt_str[:m_dia.start()] + formatted + dt_str[m_dia.end():]

    # Fallback D: apenas HH:MM (sem data; não inventa dia)
    m_time = re.search(r"(\d{1,2}):(\d{2})", dt_str)
    if m_time:
        h, mins = int(m_time.group(1)), int(m_time.group(2))
        total = h * 60 + mins + minutes
        new_h = (total // 60) % 24
        new_m = total % 60
        return dt_str[:m_time.start()] + f"{new_h:02d}:{new_m:02d}" + dt_str[m_time.end():]

    raise ValueError(
        f"Formato de data não reconhecido: '{dt_str}'. Use 'DD de Mês de YYYY, HH:MM', "
        f"'DD/MM/YYYY, HH:MM', 'Dia X, HH:MM' ou configure 'calendar' em regras.md."
    )
