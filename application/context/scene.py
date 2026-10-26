"""Auxiliares de cena, presença e atores para o pipeline de contexto."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from council import derive_npc_initiative


def resolve_scene_actors(
    action: str,
    actors: str,
    focus: str,
    diario: Mapping[str, Any],
    all_npcs: Sequence[Mapping[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Identifica personagens presentes na cena, separando NPCs focais e de fundo."""
    if actors and actors.strip():
        scene_present = actors.strip()
    else:
        scene_present = str(diario.get("present", ""))

    present_lower = scene_present.lower()

    # Identifica NPCs que constam como presentes na cena
    scene_npcs = [
        dict(n)
        for n in all_npcs
        if any(part.strip().lower() in present_lower for part in re.split(r"[\s(),&]+", str(n.get("name", ""))) if len(part.strip()) > 2)
    ]

    # Se a cena não listou NPCs explicitamente, verifica se a ação ou foco citam alguém conhecido
    if not scene_npcs:
        target_text = f"{action} {focus}".lower()
        scene_npcs = [
            dict(n)
            for n in all_npcs
            if any(part.strip().lower() in target_text for part in re.split(r"[\s(),&]+", str(n.get("name", ""))) if len(part.strip()) > 2)
        ]

    # Determina NPCs Focais vs Figurantes (Background)
    focal_names: set[str] = set()
    if focus and focus.strip():
        focus_lower = focus.lower()
        for n in all_npcs:
            n_name = str(n.get("name", ""))
            if any(part.strip().lower() in focus_lower for part in re.split(r"[\s(),&]+", n_name) if len(part.strip()) > 2):
                focal_names.add(n_name)

    action_lower = action.lower()
    for n in (scene_npcs or all_npcs):
        n_name = str(n.get("name", ""))
        if any(part.strip().lower() in action_lower for part in re.split(r"[\s(),&]+", n_name) if len(part.strip()) > 2):
            focal_names.add(n_name)

    if not focal_names and scene_npcs:
        for n in scene_npcs:
            if n.get("will") or n.get("plan"):
                focal_names.add(str(n.get("name", "")))
                break

    focal_npcs: list[dict[str, Any]] = []
    background_npcs: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for n in all_npcs:
        n_name = str(n.get("name", ""))
        if n_name in focal_names:
            focal_npcs.append(dict(n))
            seen_names.add(n_name)

    for n in scene_npcs:
        n_name = str(n.get("name", ""))
        if n_name not in seen_names:
            background_npcs.append(dict(n))
            seen_names.add(n_name)

    return scene_present, scene_npcs, focal_npcs, background_npcs


def build_npc_dynamics(focal_npcs: Sequence[Mapping[str, Any]]) -> list[str]:
    """Gera diretivas textuais de atrito e vontade para NPCs focais."""
    prompts: list[str] = []
    for n_obj in focal_npcs:
        n_desc = f"{n_obj.get('name', '')}"
        if n_obj.get("will"):
            n_desc += f" (Vontade: {n_obj['will']})"
        if n_obj.get("weakness"):
            n_desc += f" (Fraqueza/Ponto Cego: {n_obj['weakness']})"
        if n_obj.get("dynamics"):
            n_desc += f" (Atritos/Laços: {n_obj['dynamics']})"
        prompts.append(n_desc)
    return prompts


def build_writer_mandates(action: str, outcome_summary: str) -> dict[str, str]:
    """Retorna os mandatos de prosa mapeados por tipo de cena."""
    return {
        "standard": (
            f"MANDATO DE ESCRITA (Padrão/Equilibrado):\n"
            f"- Ação do Jogador: '{action}'\n"
            f"- Desfecho Mecânico: {outcome_summary}\n"
            f"- Diretriz Dramática: Narre com base nos fatos estabelecidos, dando agência total aos NPCs da cena e avançando a trama conforme o resultado."
        ),
        "dossier": (
            f"MANDATO DE ESCRITA (Dossiê/Arquivo):\n"
            f"- Ação do Jogador: '{action}'\n"
            f"- Diretriz: Relatório analítico, perspectiva documental/histórica da cena."
        ),
        "interlude": (
            f"MANDATO DE ESCRITA (Interlúdio):\n"
            f"- Ação do Jogador: '{action}'\n"
            f"- Diretriz: Cena de descanso, contemplação ou transição entre arcos."
        ),
        "parallel": (
            f"MANDATO DE ESCRITA (Paralela):\n"
            f"- Ação do Jogador: '{action}'\n"
            f"- Diretriz: Corte para outra perspectiva temporal ou espacial."
        ),
    }


def resolve_scheduled_scene(
    scene_type: str,
    next_sched: Mapping[str, Any] | None,
    actors: str,
    action: str,
) -> dict[str, Any]:
    """Avalia sementes dramáticas agendadas na fila da trama."""
    if scene_type == "standard" and next_sched and not actors:
        return {
            "has_scheduled": True,
            "scene_type": next_sched["scene_type"],
            "actors": next_sched["actors"],
            "beat": next_sched["beat"],
            "recommendation": (
                f"SEMENTE DRAMÁTICA AGENDADA: A fila de trama possui uma cena sugerida como [{next_sched['scene_type']}] "
                f"com atores '{next_sched['actors'] or 'Protagonista'}': '{next_sched['beat']}'. "
                f"PROTOCOLO DE CONCILIAÇÃO: Avalie a ação do jogador '{action[:45]}'. "
                f"Se a ação do jogador concluir a batida atual ou se a situação pedir corte cinematográfico imediato, "
                f"execute a transição usando --scene-type {next_sched['scene_type']} e --actors '{next_sched['actors']}'. "
                f"Se a ação do jogador abrir novo atrito em tempo real que deve ser resolvido antes, resolva a ação "
                f"e mantenha a semente na fila para o momento oportuno."
            ),
        }
    return {"has_scheduled": False}


def build_progression_data(ficha_path: Any) -> dict[str, Any]:
    """Extrai e calibra os dados de progressão do herói."""
    from council import parse_progression_from_ficha
    progression_data = parse_progression_from_ficha(ficha_path)
    lvl = progression_data.get("level", 1)
    scale_guide = (
        f"Protagonista Nível {lvl}: Calibre a escala de oponentes e atrito para desafios "
        + ("iniciais de sobrevivência e reputação local." if lvl == 1 else
           ("moderados condizentes com um herói em ascensão." if lvl <= 3 else
            ("veteranos e ameaças regionais de alta letalidade." if lvl <= 6 else
             "épicos e forças transcendentais de nível mestre.")))
    )
    progression_data["scale_guidance"] = scale_guide
    return progression_data


def build_quest_context(diario_path: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extrai sumário de missões ativas e mandato de pressão."""
    from council import parse_quests_from_diario
    all_quests = parse_quests_from_diario(diario_path)
    active_quests_summary = [q for q in all_quests if str(q.get("status", "")).upper() == "ACTIVE"]
    quest_mandate = "Nenhuma missão ativa."
    if active_quests_summary:
        first_q = active_quests_summary[0]
        quest_mandate = (
            f"PRESSÃO DE MISSÃO: O protagonista está engajado em '{first_q['title']}' ({first_q['id']}) "
            f"para o contratante '{first_q['contractor']}'. Próximo objetivo: '{first_q['objectives'][0] if first_q['objectives'] else 'avançar na investigação'}'. "
            f"Se a ação atual se conectar a isso, avance a missão com --quest-progress '{first_q['id']}:1'."
        )
    return {
        "active_quests": active_quests_summary,
        "quest_pressure_mandate": quest_mandate,
    }, active_quests_summary


def build_commit_hint(
    campaign_id: str,
    focal_npcs: Sequence[Mapping[str, Any]],
    contest_data: Mapping[str, Any] | None,
    roll_data: Mapping[str, Any] | None,
    scene_type: str,
    active_quests_summary: Sequence[Mapping[str, Any]],
) -> str:
    """Monta o template de comando commit sugerido pós-turno."""
    if focal_npcs:
        prefilled_npc = " | ".join(f"{n['name']}: Atitude: <postura pós-cena>; Relação: <relação pós-cena>" for n in focal_npcs)
    else:
        prefilled_npc = "<NPC: Atitude: ...; Relação: ...>"

    commit_hint = f'python lazy_turn.py commit --campaign {campaign_id} --summary "<resumo_factual>" --state-shift "<mudança_concreta>" --npc-updates "{prefilled_npc}"'
    if contest_data and not contest_data.get("is_npc_vs_npc") and ("Catástrofe" in contest_data.get("tier", "") or "Revés" in contest_data.get("tier", "") or "Impasse" in contest_data.get("tier", "") or contest_data.get("delta", 0) <= 0):
        commit_hint += ' --cost "<HP -X, Stamina -Y>"'
    elif roll_data and ("Custo" in roll_data.get("tier", "") or "Falha" in roll_data.get("tier", "") or "Catástrofe" in roll_data.get("tier", "")):
        commit_hint += ' --cost "<HP -X, Stamina -Y>"'
    if scene_type != "standard":
        commit_hint += f' --scene-type {scene_type}'
    if active_quests_summary:
        commit_hint += f' --quest-progress "{active_quests_summary[0]["id"]}:1"'
    return commit_hint


__all__ = [
    "build_commit_hint",
    "build_npc_dynamics",
    "build_progression_data",
    "build_quest_context",
    "build_writer_mandates",
    "resolve_scene_actors",
    "resolve_scheduled_scene",
]
