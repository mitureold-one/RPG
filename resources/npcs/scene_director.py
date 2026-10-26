"""resources/npcs/scene_director.py: Análise situacional de cena e estruturas narrativas alternativas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def derive_situational_scene_structures(
    action: str,
    last_turn_summary: str,
    recent_shifts: list[dict[str, Any]],
    clocks: list[dict[str, Any]],
    consecutive_standard: int,
    focal_npcs: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Analisa os sinais dramáticos concretos da situação imediata e das Vontades/Traumas dos NPCs."""
    text_pool = (
        action + " " +
        last_turn_summary + " " +
        " ".join(s.get("shift", "") for s in recent_shifts)
    ).lower()

    proposals = []
    focal_npcs = focal_npcs or []

    for n in focal_npcs:
        n_name = n.get("name", "NPC")
        n_will = n.get("will", "")
        n_weak = n.get("weakness", "")

        weak_low = n_weak.lower()
        if any(w in weak_low for w in ["trauma", "cicatriz", "passado", "paranoia", "paranóica", "perda", "culpa", "medo", "honra"]):
            proposals.append({
                "scene_type": "flashback",
                "focus_actor": n_name,
                "trigger_signal": f"Trauma/ponto cego de {n_name}: '{n_weak}'.",
                "narrative_hook": f"Flashback revelando a origem da fraqueza/cicatriz de {n_name} e o momento do passado que dita sua conduta no presente."
            })

        will_low = n_will.lower()
        if any(w in will_low for w in ["clã", "cla", "matilha", "povo", "família", "familia", "reino", "irmandade", "facção", "faccao", "tribo", "aliança"]):
            proposals.append({
                "scene_type": "parallel",
                "focus_actor": f"Clã / Aliados de {n_name}",
                "trigger_signal": f"Vontade autônoma de {n_name} em relação à sua facção: '{n_will}'.",
                "narrative_hook": f"Cena paralela mostrando a base/clã de {n_name} reagindo aos ecos da batalha e tomando decisões estratégicas sem a liderança dela."
            })

    if len(focal_npcs) >= 2:
        n1, n2 = focal_npcs[0]["name"], focal_npcs[1]["name"]
        proposals.append({
            "scene_type": "interlude",
            "focus_actor": f"{n1} e {n2}",
            "trigger_signal": f"Vínculos e hierarquia interna entre {n1} e {n2}.",
            "narrative_hook": f"Conferência secreta entre {n1} e {n2}: as duas se afastam por alguns metros e deliberam em sussurros/dialeto nativo sobre se devem confiar, usar ou trair o protagonista."
        })

    dossier_signals = [
        "corvo", "relatório", "relatorio", "carta", "ordem", "inquisição", "inquisicao",
        "senado", "patrulha", "patrulhas", "busca", "buscas", "sensor", "sensores",
        "investigação", "investigacao", "tribunal", "boletim", "mandado", "procurado",
        "registro", "escuta", "espião", "espiao", "espiões", "espioes"
    ]
    if any(sig in text_pool for sig in dossier_signals):
        proposals.append({
            "scene_type": "dossier",
            "focus_actor": "Rede de Inteligência / Autoridades",
            "trigger_signal": "Comunicações oficiais, investigações ou relatórios de busca ativos no cenário.",
            "narrative_hook": "Apresentar a cena como relatório confidencial de inteligência, carta interceptada ou mandado oficial avaliando a anomalia ou os NPCs presentes."
        })

    critical_clocks = [c for c in clocks if c.get("status") == "ACTIVE" and (c.get("current", 0) / max(1, c.get("max", 1))) >= 0.70]
    antagonist_generic_words = [
        "reagrupamento", "conselho", "vanguarda", "generais", "mobilização", "mobilizacao",
        "patrulhas de busca", "inimigo", "senado", "tropa", "esquadrão", "esquadrao",
        "guarnição", "guarnicao", "comandante", "oficial", "alerta geral", "emboscada"
    ]
    if critical_clocks or any(sig in text_pool for sig in antagonist_generic_words):
        reasons = [f"Relógio crítico '[{c['name']}]' em {c['progress']}" for c in critical_clocks]
        proposals.append({
            "scene_type": "interlude",
            "focus_actor": "Forças Antagônicas / Comandantes",
            "trigger_signal": "; ".join(reasons) if reasons else "Movimentação de forças antagônicas fora da presença do protagonista.",
            "narrative_hook": "Cortar a perspectiva para os antagonistas organizando o cerco ou a resposta tática nos bastidores."
        })

    timeskip_signals = [
        "curada", "curadas", "curado", "curados", "descanso", "acampar", "dormir", "noite",
        "amanhecer", "anoitecer", "esperar", "vigília", "vigilia", "viagem", "estrada",
        "recuperação", "recuperacao", "horas", "dias", "estabilizados", "estabilizado"
    ]
    if any(sig in text_pool for sig in timeskip_signals):
        proposals.append({
            "scene_type": "timeskip",
            "focus_actor": "Grupo em Transição",
            "trigger_signal": "Crise imediata estabilizada (cura concluída ou necessidade de deslocamento/vigília).",
            "narrative_hook": "Condensar horas ou dias de viagem, treino ou vigília sob montagem sensorial acelerada até o próximo ponto de atrito."
        })

    fade_signals = [
        "beijo", "pele", "calor", "toque", "abraço", "abraco", "abrigo", "caverna",
        "despir", "despida", "despido", "ofegante", "olhar nos olhos", "sussurro",
        "intimidade", "respiração próxima", "respiracao proxima", "leito"
    ]
    if any(sig in text_pool for sig in fade_signals):
        proposals.append({
            "scene_type": "fade_to_black",
            "focus_actor": "Personagens em Intimidade",
            "trigger_signal": "Intimidade tátil e vulnerabilidade mútua no limiar físico.",
            "narrative_hook": "Construir a tensão sensorial até o ápice e aplicar corte cinematográfico para preto, aterrissando no despertar com novas dinâmicas emocionais."
        })

    pacing_status = {
        "consecutive_standard_turns": consecutive_standard,
        "is_linear_fatigue": consecutive_standard >= 4,
        "available_situational_proposals": proposals,
        "recommendation": (
            f"FADIGA LINEAR DETECTADA ({consecutive_standard} turnos padrão): O Mestre deve considerar transferir a perspectiva ou quebrar a rotina escolhendo uma das {len(proposals)} estruturas situacionais sugeridas via '--scene-type <tipo>' (com foco nos NPCs ou nas forças do mundo)."
            if consecutive_standard >= 4 and proposals
            else (
                f"Sinais situacionais ativos para quebra orgânica centrada nos NPCs ou no mundo: {', '.join(p['scene_type'] for p in proposals)}. Use '--scene-type <tipo>' se desejar explorar."
                if proposals
                else "Cena padrão em tempo real recomendada para a situação imediata."
            )
        )
    }
    return pacing_status


__all__ = ["derive_situational_scene_structures"]
