"""Cálculo determinístico de relevância causal para entidades e fatos."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from contracts.context import ContextItem, ContextLimits, ContextRequest
from contracts.ports import ContextStateView


def _text_matches(query: str, text: str) -> bool:
    if not query or not text:
        return False
    return query.lower() in text.lower()


def _is_mentioned(needle: str, haystack: Sequence[str] | str) -> bool:
    if not needle:
        return False
    n = needle.lower()
    if isinstance(haystack, str):
        return n in haystack.lower()
    return any(n in str(item).lower() for item in haystack)


def _extract_relational_vector(npc_data: Mapping[str, Any], target_id: str = "") -> dict[str, int]:
    raw = npc_data.get("relational_vector") or npc_data.get("relationships") or ()
    if isinstance(raw, dict):
        return {k: int(raw.get(k, 0)) for k in ("trust", "rivalry", "debt", "loyalty", "dependency")}
    if isinstance(raw, (list, tuple)):
        if target_id:
            for item in raw:
                if isinstance(item, dict) and item.get("target_id") == target_id:
                    return {k: int(item.get(k, 0)) for k in ("trust", "rivalry", "debt", "loyalty", "dependency")}
        best, max_int = {}, -1
        for item in raw:
            if isinstance(item, dict):
                cur_int = int(item.get("rivalry", 0)) * 2 + abs(int(item.get("debt", 0))) + abs(int(item.get("trust", 0)))
                if cur_int > max_int:
                    best, max_int = item, cur_int
        if best:
            return {k: int(best.get(k, 0)) for k in ("trust", "rivalry", "debt", "loyalty", "dependency")}
    return {k: 0 for k in ("trust", "rivalry", "debt", "loyalty", "dependency")}


def score_npc(
    npc_data: Mapping[str, Any],
    request: ContextRequest,
    state: ContextStateView,
    context_facts: Sequence[Mapping[str, Any]] = (),
) -> tuple[int, tuple[str, ...]]:
    """Calcula pontuação inteira e razões de inclusão causal para um NPC."""
    score = 0
    reasons: list[str] = []

    npc_id = str(npc_data.get("id") or "").strip()
    npc_name = str(npc_data.get("name") or npc_id).strip()
    npc_loc = str(npc_data.get("location") or "").strip()

    # 1. Presença na cena (+1000)
    is_present = (
        npc_id in request.scene.present
        or _is_mentioned(npc_name, request.scene.present)
        or (npc_loc and _text_matches(npc_loc, request.scene.location))
    )
    if is_present:
        score += 1000
        reasons.append("presenca")
    else:
        # 10. Distância física (-100)
        score -= 100
        reasons.append("fora_de_cena")

    # 2. Foco explícito (+500)
    in_focus = _is_mentioned(npc_id, request.focus) or _is_mentioned(npc_name, request.focus)
    in_action = _text_matches(npc_id, request.action) or _text_matches(npc_name, request.action)
    if in_focus or in_action:
        score += 500
        reasons.append("foco_explicito")

    # 3. Relógio crítico vinculado (+300)
    clocks = state.clocks()
    has_critical_clock = False
    for clk in clocks:
        c_name = getattr(clk, "name", "") if hasattr(clk, "name") else clk.get("name", "")
        c_cur = getattr(clk, "current", 0) if hasattr(clk, "current") else clk.get("current", 0)
        c_max = getattr(clk, "max", 4) if hasattr(clk, "max") else clk.get("max", 4)
        c_status = getattr(clk, "status", "ACTIVE") if hasattr(clk, "status") else clk.get("status", "ACTIVE")
        if c_status in ("ACTIVE", "active") and c_cur >= max(1, c_max - 1):
            if _text_matches(npc_id, c_name) or _text_matches(npc_name, c_name):
                has_critical_clock = True
                break
    if has_critical_clock:
        score += 300
        reasons.append("relogio_critico")

    # 4. Plano iminente (+300)
    plan = npc_data.get("plan") or npc_data.get("active_plan") or {}
    if isinstance(plan, dict):
        plan_status = plan.get("status", "")
        plan_steps = plan.get("steps") or []
        has_in_progress = any(s.get("status") == "in_progress" for s in plan_steps if isinstance(s, dict))
        is_imminent = bool(plan.get("imminent")) or has_in_progress
    else:
        plan_status = getattr(plan, "status", "")
        plan_steps = getattr(plan, "steps", ())
        has_in_progress = any(
            getattr(s, "status", "") == "in_progress"
            or (isinstance(s, dict) and s.get("status") == "in_progress")
            for s in plan_steps
        )
        is_imminent = bool(getattr(plan, "imminent", False)) or has_in_progress
    if plan_status == "active" and (is_imminent or has_critical_clock):
        score += 300
        reasons.append("plano_iminente")

    # 5. Missão ativa vinculada (+250)
    quests = state.quests()
    has_active_quest = False
    for q in quests:
        q_contractor = getattr(q, "contractor", "") if hasattr(q, "contractor") else q.get("contractor", "")
        q_target = getattr(q, "target", "") if hasattr(q, "target") else q.get("target", "")
        q_status = getattr(q, "status", "active") if hasattr(q, "status") else q.get("status", "active")
        if q_status in ("active", "ACTIVE") and (
            _text_matches(npc_id, q_contractor)
            or _text_matches(npc_name, q_contractor)
            or _text_matches(npc_id, q_target)
            or _text_matches(npc_name, q_target)
        ):
            has_active_quest = True
            break
    if has_active_quest:
        score += 250
        reasons.append("missao_ativa")

    # 6. Arco ativo (+200)
    arc_data = state.arc()
    arc_text = str(arc_data)
    if _text_matches(npc_id, arc_text) or _text_matches(npc_name, arc_text):
        score += 200
        reasons.append("arco_ativo")

    # 7. Ameaça (+200) e 8. Dívida/favor (+150)
    target_id = getattr(request, "target", "") or (request.audience.id if getattr(request, "audience", None) and request.audience.kind == "protagonist" else "")
    rv = _extract_relational_vector(npc_data, target_id=target_id)
    rivalry = rv.get("rivalry", 0)
    trust = rv.get("trust", 0)
    debt = rv.get("debt", 0)
    if rivalry >= 2 or trust <= -2:
        score += 200
        reasons.append("ameaca")
    if debt != 0:
        score += 150
        reasons.append("divida")

    # 9. Consequência recente (+100)
    recent = state.recent_events(limit=10)
    has_recent_consequence = False
    for evt in recent:
        refs = getattr(evt, "refs", ()) if hasattr(evt, "refs") else evt.get("refs", ())
        summary = getattr(evt, "summary", "") if hasattr(evt, "summary") else evt.get("summary", "")
        if npc_id in refs or _text_matches(npc_id, summary) or _text_matches(npc_name, summary):
            has_recent_consequence = True
            break
    if has_recent_consequence:
        score += 100
        reasons.append("consequencia_recente")

    return score, tuple(reasons)


def score_faction(
    faction_data: Mapping[str, Any],
    request: ContextRequest,
    state: ContextStateView,
    context_facts: Sequence[Mapping[str, Any]] = (),
) -> tuple[int, tuple[str, ...]]:
    """Calcula pontuação inteira e razões de inclusão causal para uma facção."""
    score = 0
    reasons: list[str] = []

    tag = str(faction_data.get("tag") or faction_data.get("id") or "").strip()
    name = str(faction_data.get("name") or tag).strip()
    territory = str(faction_data.get("territory") or "").strip()

    # 1. Presença na cena (+1000)
    is_present = (
        tag in request.scene.present
        or _is_mentioned(name, request.scene.present)
        or (territory and _text_matches(territory, request.scene.location))
    )
    if is_present:
        score += 1000
        reasons.append("presenca")
    elif territory and not _text_matches(territory, request.scene.location):
        score -= 100
        reasons.append("fora_de_cena")

    # 2. Foco explícito (+500)
    if _is_mentioned(tag, request.focus) or _is_mentioned(name, request.focus) or _text_matches(tag, request.action) or _text_matches(name, request.action):
        score += 500
        reasons.append("foco_explicito")

    # 3. Relógio crítico (+300)
    has_critical_clock = False
    for clk in state.clocks():
        c_name = getattr(clk, "name", "") if hasattr(clk, "name") else clk.get("name", "")
        c_cur = getattr(clk, "current", 0) if hasattr(clk, "current") else clk.get("current", 0)
        c_max = getattr(clk, "max", 4) if hasattr(clk, "max") else clk.get("max", 4)
        c_status = getattr(clk, "status", "ACTIVE") if hasattr(clk, "status") else clk.get("status", "ACTIVE")
        if c_status in ("ACTIVE", "active") and c_cur >= max(1, c_max - 1):
            if _text_matches(tag, c_name) or _text_matches(name, c_name):
                has_critical_clock = True
                break
    if has_critical_clock:
        score += 300
        reasons.append("relogio_critico")

    # 4. Plano iminente (+300)
    plan = faction_data.get("active_plan") or faction_data.get("plan") or faction_data.get("initiative") or {}
    if plan.get("status") in ("active", "in_progress") or plan.get("imminent"):
        score += 300
        reasons.append("plano_iminente")

    # 5. Missão ativa (+250)
    for q in state.quests():
        q_contractor = getattr(q, "contractor", "") if hasattr(q, "contractor") else q.get("contractor", "")
        q_target = getattr(q, "target", "") if hasattr(q, "target") else q.get("target", "")
        if _text_matches(tag, q_contractor) or _text_matches(name, q_contractor) or _text_matches(tag, q_target) or _text_matches(name, q_target):
            score += 250
            reasons.append("missao_ativa")
            break

    # 6. Arco ativo (+200)
    arc_text = str(state.arc())
    if _text_matches(tag, arc_text) or _text_matches(name, arc_text):
        score += 200
        reasons.append("arco_ativo")

    # 7. Ameaça / Rivalidade (+200) e 8. Dívida (+150)
    reputation = int(faction_data.get("reputation", 0) or 0)
    rivals = faction_data.get("rivals") or ()
    if reputation <= -2 or rivals:
        score += 200
        reasons.append("ameaca")
    if int(faction_data.get("debt", 0) or 0) != 0:
        score += 150
        reasons.append("divida")

    # 9. Consequência recente (+100)
    for evt in state.recent_events(limit=10):
        refs = getattr(evt, "refs", ()) if hasattr(evt, "refs") else evt.get("refs", ())
        summary = getattr(evt, "summary", "") if hasattr(evt, "summary") else evt.get("summary", "")
        if tag in refs or _text_matches(tag, summary) or _text_matches(name, summary):
            score += 100
            reasons.append("consequencia_recente")
            break

    return score, tuple(reasons)


def select(items: Sequence[ContextItem], limits: ContextLimits) -> tuple[ContextItem, ...]:
    """Filtra e ordena itens por relevância de forma estritamente determinística."""
    # Itens da camada core não passam por corte de relevância
    core_items = [item for item in items if item.layer == "core"]
    causal_items = [
        item
        for item in items
        if item.layer == "causal"
        and (
            item.score >= limits.min_relevance
            or item.kind in ("fact", "consequence", "quest", "clock", "claim")
        )
    ]

    # Ordenação estável: (-score, kind, id)
    causal_items.sort(key=lambda x: (-x.score, x.kind, x.id))

    # Aplicação de limites por kind
    selected_causal: list[ContextItem] = []
    counts: dict[str, int] = {"npc": 0, "faction": 0, "fact": 0, "consequence": 0}
    max_counts = {
        "npc": limits.max_npcs,
        "faction": limits.max_factions,
        "fact": limits.max_facts,
        "consequence": limits.max_consequences,
    }
    for item in causal_items:
        if item.kind in counts:
            if counts[item.kind] < max_counts[item.kind]:
                selected_causal.append(item)
                counts[item.kind] += 1
        else:
            selected_causal.append(item)

    return tuple(core_items + selected_causal)


__all__ = ["score_faction", "score_npc", "select"]
