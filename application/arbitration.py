"""Arbitragem mecânica de rolagens, disputas e cálculo de criticidade.

Extraído de application/prepare.py conforme etapa R2 da arquitetura.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ArbitrationResult:
    """Resultado da arbitragem de regras e dados para o turno."""

    needs_roll: bool
    chosen_stat: str
    stat_val: int
    roll_data: Mapping[str, Any] | None
    contest_data: Mapping[str, Any] | None
    is_critical: bool
    critical_reasons: tuple[str, ...]
    cost_guide: str
    focal_npcs: tuple[Mapping[str, Any], ...]


def resolve_arbitration(
    action: str,
    ruleset: Any,
    ficha: Mapping[str, Any],
    all_npcs: Sequence[Mapping[str, Any]],
    scene_npcs: Sequence[Mapping[str, Any]],
    focal_npcs: Sequence[Mapping[str, Any]],
    scene_type: str = "standard",
    mode: str = "gm",
    variant: str = "normal",
    dc: int = 15,
    stat: str = "",
    force_roll: bool = False,
    no_roll: bool = False,
    contest_npc: str = "",
    vs_npc: str = "",
    npc_stat: str = "",
    vs_stat: str = "",
    npc_variant: str = "normal",
    vs_variant: str = "normal",
    stakes: str = "normal",
    critical: bool = False,
    pre_audit: Mapping[str, Any] | None = None,
) -> ArbitrationResult:
    """Resolve a mecânica de rolagens, disputas e determinação de criticidade."""
    # Decisão de Rolagem: Se cena for cutscene sem protagonista, waive roll
    if scene_type in ("interlude", "parallel", "dossier"):
        needs_roll = False
    elif mode in ("writer", "architect"):
        needs_roll = False
    elif mode == "narrator":
        needs_roll = force_roll or bool(stat)
    else:
        needs_roll = (not no_roll) and (force_roll or bool(stat))

    chosen_stat = stat.upper().strip() if stat else ""
    ficha_stats = ficha.get("stats", {})
    if needs_roll and not chosen_stat and ficha_stats:
        chosen_stat = next(iter(ficha_stats.keys()))

    stat_val = ficha_stats.get(chosen_stat, 10) if ficha_stats else 10

    focal_list = list(focal_npcs)
    contest_data = None
    roll_data = None

    if contest_npc and contest_npc.strip():
        raw_c1 = contest_npc.strip()
        raw_c2 = vs_npc.strip() if vs_npc else ""

        if not raw_c2 and " vs " in raw_c1.lower():
            parts = re.split(r"\s+vs\s+", raw_c1, flags=re.IGNORECASE)
            if len(parts) >= 2:
                raw_c1, raw_c2 = parts[0].strip(), parts[1].strip()

        def find_npc_match(q: str):
            q_lower = q.lower()
            return next(
                (
                    n
                    for n in all_npcs
                    if any(
                        p.lower() in q_lower or q_lower in n["name"].lower()
                        for p in re.split(r"[\s(),&]+", n["name"])
                        if len(p) > 2
                    )
                ),
                None,
            )

        if raw_c2:
            m_npc1 = find_npc_match(raw_c1) or {"name": raw_c1, "psychology": "", "classification": "Elite"}
            m_npc2 = find_npc_match(raw_c2) or {"name": raw_c2, "psychology": "", "classification": "Elite"}

            for m in (m_npc1, m_npc2):
                if not any(n["name"] == m["name"] for n in focal_list):
                    focal_list.append(m)

            n1_stat_name, n1_stat_mod = ruleset.extract_npc_contest_modifier(m_npc1, npc_stat)
            n2_stat_name, n2_stat_mod = ruleset.extract_npc_contest_modifier(m_npc2, vs_stat)

            contest_data = ruleset.roll_contest(
                pc_name=m_npc1["name"],
                pc_stat_name=n1_stat_name,
                pc_stat_val=n1_stat_mod,
                npc_name=m_npc2["name"],
                npc_stat_name=n2_stat_name,
                npc_stat_mod=n2_stat_mod,
                pc_variant=npc_variant,
                npc_variant=vs_variant if vs_variant != "normal" else "normal",
                p1_is_npc=True,
            )
        else:
            matched_npc = find_npc_match(raw_c1)
            if not matched_npc:
                matched_npc = scene_npcs[0] if scene_npcs else {"name": raw_c1, "psychology": "", "classification": "Elite"}

            if not any(n["name"] == matched_npc["name"] for n in focal_list):
                focal_list.append(matched_npc)

            n_stat_name, n_stat_mod = ruleset.extract_npc_contest_modifier(matched_npc, npc_stat)
            contest_data = ruleset.roll_contest(
                pc_name=ficha.get("name", "Protagonista"),
                pc_stat_name=chosen_stat,
                pc_stat_val=stat_val,
                npc_name=matched_npc["name"],
                npc_stat_name=n_stat_name,
                npc_stat_mod=n_stat_mod,
                pc_variant=variant,
                npc_variant=npc_variant,
                p1_is_npc=False,
            )
    else:
        roll_data = ruleset.roll_3_gates(action[:35], variant, dc, chosen_stat, stat_val) if needs_roll else None

    critical_reasons: list[str] = []
    if critical or stakes.lower() in ("high", "climax"):
        critical_reasons.append(f"Tensão dramática declarada pelo Mestre para a situação atual (stakes='{stakes}').")
    if needs_roll and dc >= 20:
        critical_reasons.append(f"Dificuldade mecânica extrema (DC {dc}).")

    if contest_data is not None:
        if contest_data.get("is_npc_vs_npc"):
            if "Catástrofe" in contest_data["tier"] or "Dádiva" in contest_data["tier"] or contest_data["p1"]["natural"] in (1, 20) or contest_data["p2"]["natural"] in (1, 20):
                critical_reasons.append(f"Clímax de disputa direta entre NPCs ({contest_data['tier']}).")
        else:
            if contest_data["p1"]["natural"] in (1, 20) or contest_data["p2"]["natural"] in (1, 20) or "Catástrofe" in contest_data["tier"] or "Dádiva" in contest_data["tier"]:
                critical_reasons.append(f"Desfecho extremo na disputa de dados PC vs NPC ({contest_data['tier']}).")
            elif contest_data["delta"] < 0:
                critical_reasons.append(f"NPC venceu o confronto ({contest_data['p2']['name']} superou o herói por {abs(contest_data['delta'])}).")
    elif roll_data is not None and (roll_data["natural"] in (1, 20) or "Catástrofe" in roll_data["tier"] or "Dádiva" in roll_data["tier"]):
        critical_reasons.append(f"Desfecho extremo nos dados ({roll_data['tier'].split('(')[0].strip()}).")

    vitals = ficha.get("vitals", {})
    for v in vitals.values():
        if isinstance(v, dict) and v.get("max", 0) > 0 and (v.get("current", 0) / v["max"]) <= 0.30:
            critical_reasons.append(f"Recurso vital em nível crítico: {v.get('label', 'Vital')} em {v.get('current')}/{v['max']} (<= 30%).")

    audit = pre_audit or {}
    if audit.get("ssot_status") and audit["ssot_status"] != "CLEAN":
        critical_reasons.append(f"Anomalia de integridade detectada na pré-auditoria ({audit['ssot_status']}).")
    for iss in audit.get("issues", []):
        if iss.get("type") == "CLOCK_BREACHED":
            critical_reasons.append(f"Relógio narrativo rompido: {iss.get('detail', '')}")
        elif iss.get("type") == "NARRATIVE_STAGNATION":
            critical_reasons.append(f"Inércia narrativa detectada: {iss.get('detail', '')}")

    is_critical = len(critical_reasons) > 0

    if contest_data:
        cost_guide = contest_data["cost_directive"]
    elif roll_data:
        if "Custo" in roll_data["tier"] or "Falha" in roll_data["tier"] or "Catástrofe" in roll_data["tier"]:
            cost_guide = "OBRIGATÓRIO deduzir recursos vitais no --cost do commit devido ao atrito/revés do dado."
        else:
            cost_guide = "Deduza recursos (energia/fôlego/munição) caso a ação tenha exigido esforço ou habilidade ativa."
    else:
        cost_guide = "Resolução sem rolagem: aplique avanço de tempo (time +Xm) ou alteração de recursos conforme a situação narrada."

    return ArbitrationResult(
        needs_roll=needs_roll,
        chosen_stat=chosen_stat,
        stat_val=stat_val,
        roll_data=roll_data,
        contest_data=contest_data,
        is_critical=is_critical,
        critical_reasons=tuple(critical_reasons),
        cost_guide=cost_guide,
        focal_npcs=tuple(focal_list),
    )


__all__ = ["ArbitrationResult", "resolve_arbitration"]
