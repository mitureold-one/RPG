"""Localização, validação e manifesto (regras.md) das campanhas em Markdown."""

import os
import re
from pathlib import Path

from temporal.calendar import _normalize_calendar

BASE_DIR = Path(__file__).resolve().parent.parent

CAMPAIGN_DIRS = [
    Path(os.environ.get("RPGPRO_CAMPAIGNS_DIR", str(BASE_DIR / "campaigns"))),
]

CURRENT_SCHEMA_VERSION = 1
DEFAULT_RULESET = "d20_3gates"
CAMPAIGN_ID_REGEX = re.compile(r"^[a-z0-9_][a-z0-9_-]*$")


def validate_campaign_id(campaign_id: str) -> str:
    """Valida o identificador de campanha contra directory traversal e caracteres proibidos."""
    if not isinstance(campaign_id, str) or not CAMPAIGN_ID_REGEX.match(campaign_id.strip()):
        raise ValueError(
            f"ID de campanha inválido: '{campaign_id}'. "
            f"Deve conter apenas letras minúsculas, dígitos, '_' ou '-', e não pode conter caminhos ou pontos."
        )
    return campaign_id.strip()


def _get_campaign_dirs() -> list[Path]:
    """Recupera a lista de diretórios de campanha ativa, respeitando patches em council.helpers."""
    import sys
    mod = sys.modules.get("council.helpers")
    if mod is not None and hasattr(mod, "CAMPAIGN_DIRS"):
        return mod.CAMPAIGN_DIRS
    return CAMPAIGN_DIRS


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
        m_cal = re.search(r"calendar:\s*\n(.*?)(?=\n[a-z_]+:|\Z)", yaml_content, re.DOTALL)
        if m_cal:
            cal_body = m_cal.group(1)
            m_months = re.search(r"months:\s*\[(.*?)\]", cal_body)
            if m_months:
                months_list = [m.strip().strip('"\'') for m in m_months.group(1).split(",") if m.strip()]
            else:
                months_list = [m.strip().strip('"\'') for m in re.findall(r"-\s*([^\n]+)", cal_body)]
            m_days = re.search(r"days_per_month:\s*(\d+)", cal_body)
            days_val = int(m_days.group(1)) if m_days else 30
            manifest["calendar"] = _normalize_calendar({"months": months_list, "days_per_month": days_val})
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
    try:
        clean_id = validate_campaign_id(campaign_id)
    except ValueError:
        return []
    for base in _get_campaign_dirs():
        if not base.exists():
            continue
        regras_path = base / clean_id / "regras.md"
        if regras_path.is_file():
            manifest = parse_regras_manifest(regras_path)
            return manifest.get("overrides", [])
    return []


def get_campaign_system(campaign_id: str) -> str:
    """Extrai o identificador de sistema de resolução declarado em regras.md."""
    try:
        clean_id = validate_campaign_id(campaign_id)
    except ValueError:
        return DEFAULT_RULESET
    for base in _get_campaign_dirs():
        if not base.exists():
            continue
        regras_path = base / clean_id / "regras.md"
        if regras_path.is_file():
            manifest = parse_regras_manifest(regras_path)
            return manifest.get("system", DEFAULT_RULESET)
    return DEFAULT_RULESET


def find_campaign(campaign_id: str, *, allow_missing_projections: bool = False):
    """Localiza e valida a pasta da campanha em Markdown (SSOT).
    
    Falha alto (raise FileNotFoundError / ValueError) se a campanha existir mas for inválida,
    ausente de diario.md, sem schema_version declarado ou com ruleset desconhecido.
    Quando allow_missing_projections=True (ex: rebuild), permite localizar a campanha a partir
    de projections/diario.md ou events/*.jsonl mesmo que diario.md tenha sido removido da raiz.
    Retorna None se o diretório da campanha não existir.
    """
    clean_id = validate_campaign_id(campaign_id)
    for base in _get_campaign_dirs():
        if not base.exists():
            continue
        base_resolved = base.resolve()
        camp_dir = (base / clean_id).resolve()
        if camp_dir.parent != base_resolved:
            raise ValueError(f"Caminho da campanha fora do diretório permitido: '{campaign_id}'.")
        if camp_dir.is_dir():
            diario_path = camp_dir / "diario.md"
            version = CURRENT_SCHEMA_VERSION
            if diario_path.is_file():
                diario_text = diario_path.read_text(encoding="utf-8")
                m_schema = re.search(r"schema_version:\s*(\d+)", diario_text)
                if not m_schema:
                    m_schema = re.search(r"<!--\s*schema_version:\s*(\d+)\s*-->", diario_text)
                if not m_schema:
                    raise ValueError(
                        f"Campanha '{clean_id}' inválida: 'diario.md' não declara 'schema_version' (ex: 'schema_version: 1')."
                    )
                version = int(m_schema.group(1))
            elif allow_missing_projections:
                proj_diario = camp_dir / "projections" / "diario.md"
                events_dir = camp_dir / "events"
                has_events = events_dir.is_dir() and any(
                    p.is_file() and p.stat().st_size > 0 for p in events_dir.glob("*.jsonl")
                )
                if proj_diario.is_file():
                    proj_text = proj_diario.read_text(encoding="utf-8")
                    m_schema = re.search(r"schema_version:\s*(\d+)", proj_text)
                    version = int(m_schema.group(1)) if m_schema else CURRENT_SCHEMA_VERSION
                elif has_events:
                    version = CURRENT_SCHEMA_VERSION
                else:
                    raise FileNotFoundError(
                        f"Campanha '{clean_id}' corrompida: 'diario.md' e 'events/' não encontrados em {camp_dir}."
                    )
            else:
                raise FileNotFoundError(
                    f"Campanha '{clean_id}' corrompida: 'diario.md' não encontrado em {camp_dir}."
                )
            if version > CURRENT_SCHEMA_VERSION:
                raise ValueError(
                    f"Campanha '{clean_id}' incompatível: schema_version {version} é superior à versão suportada pelo motor ({CURRENT_SCHEMA_VERSION})."
                )
            manifest = parse_regras_manifest(camp_dir / "regras.md")
            system_name = manifest.get("system", DEFAULT_RULESET)
            load_ruleset(system_name)
            return {
                "id": clean_id,
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
