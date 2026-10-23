"""Pré-validação do `commit`: entidades referenciadas e data resultante, sem I/O de escrita."""

from council import (
    parse_time_increment,
    advance_time_str,
    parse_clocks_from_diario,
    parse_quests_from_diario,
)
from council.factions import parse_factions_from_mundo


def _split_name_value(item: str) -> tuple:
    """Divide 'Nome:valor' pelo último ':' (nomes podem conter ':').

    Retorna (nome, valor). Se não houver valor, o segundo item é vazio.
    """
    raw = item.strip()
    if ":" not in raw:
        return raw, ""
    name, value = raw.rsplit(":", 1)
    return name.strip(), value.strip()


def _compute_commit_datetime(
    current_dt: str,
    time_str: str,
    time_advance_mins: int,
    calendar: dict | None,
) -> str:
    """Resolve a nova data/hora do commit antes de qualquer escrita.

    Levanta ``ValueError`` quando o formato é desconhecido ou o calendário da
    campanha não cobre o mês; o commit deve abortar sem tocar no SSOT.
    """
    if time_str:
        clean = time_str.strip()
        if clean.startswith("+"):
            rel_mins = parse_time_increment(clean)
            if rel_mins <= 0:
                raise ValueError(
                    f"Incremento de tempo inválido: '{time_str}'. Use '+30m', '+6h', '+14d', '+2mo' ou '+1y'."
                )
            return advance_time_str(current_dt, rel_mins, calendar=calendar)
        return clean
    if time_advance_mins > 0:
        return advance_time_str(current_dt, time_advance_mins, calendar=calendar)
    return current_dt


def validate_commit_entities(
    info: dict,
    clock_advance: str = "",
    clock_resolve: str = "",
    quest_progress: str = "",
    quest_complete: str = "",
    quest_fail: str = "",
    faction_rep: str = "",
    faction_favor: str = "",
    faction_debt: str = "",
) -> list:
    """Valida nomes de entidades antes de qualquer escrita do commit.

    Retorna uma lista de erros legíveis. O commit deve abortar sem tocar no
    SSOT quando a lista não estiver vazia. Isso impede relógios, missões e
    facções fantasma criados por erro de digitação.
    """
    errors = []
    diario_path = info.get("diario")
    mundo_path = info.get("mundo")

    clock_names = set()
    if diario_path and diario_path.exists():
        clock_names = {c["name"].strip().lower() for c in parse_clocks_from_diario(diario_path)}

    for raw in (clock_advance or "").split("|"):
        if not raw.strip():
            continue
        name, _ = _split_name_value(raw)
        if name and name.lower() not in clock_names:
            errors.append(
                f"Relógio '{name}' não existe em diario.md. Crie-o com 'lazy_turn.py clock --add \"{name}\"'."
            )

    for raw in (clock_resolve or "").split("|"):
        name = raw.strip()
        if name and name.lower() not in clock_names:
            errors.append(
                f"Relógio '{name}' não existe em diario.md. Crie-o com 'lazy_turn.py clock --add \"{name}\"'."
            )

    quests = {}
    if diario_path and diario_path.exists():
        quests = {q["id"].upper(): q for q in parse_quests_from_diario(diario_path)}

    for raw in (quest_progress or "").split("|"):
        if not raw.strip():
            continue
        qid = raw.split(":", 1)[0].strip()
        if qid and qid.upper() not in quests:
            errors.append(f"Missão '{qid}' não existe em diario.md.")

    for raw in (quest_complete or "").split("|"):
        qid = raw.strip().upper()
        if qid and qid not in quests:
            errors.append(f"Missão '{qid}' não existe em diario.md.")

    for raw in (quest_fail or "").split("|"):
        if not raw.strip():
            continue
        qid = raw.split(":", 1)[0].strip()
        if qid and qid.upper() not in quests:
            errors.append(f"Missão '{qid}' não existe em diario.md.")

    faction_keys = set()
    if mundo_path and mundo_path.exists():
        for faction in parse_factions_from_mundo(mundo_path):
            faction_keys.add(faction["name"].strip().lower())
            faction_keys.add(faction["tag"].strip().lower())

    for label, raw_value in (
        ("facção", faction_rep),
        ("facção", faction_favor),
        ("facção", faction_debt),
    ):
        for raw in (raw_value or "").split("|"):
            if not raw.strip():
                continue
            name, _ = _split_name_value(raw)
            if name and name.lower() not in faction_keys:
                errors.append(
                    f"{label.capitalize()} '{name}' não existe em mundo.md. "
                    f"Registre-a com 'lazy_turn.py faction --add \"{name}\"'."
                )

    return errors
