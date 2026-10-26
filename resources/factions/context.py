"""resources/factions/context.py: Resolução de Contexto de Cena e Postura de Facções (RPGPRO).

Identifica facções representadas na cena por NPCs presentes ou território e calcula modificadores sociais.
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from resources.factions.parser import parse_factions_from_mundo
from resources.factions.reputation import (
    parse_reputation_from_ficha,
    SOCIAL_DC_MODIFIERS,
    SUGGESTED_VARIANTS,
)
from resources.npcs.parser import parse_npcs_md


def resolve_scene_factions(
    campaign_info: Dict[str, Any],
    scene_npcs: List[str],
    location: str,
) -> List[Dict[str, Any]]:
    """Identifica facções representadas na cena por NPCs presentes ou território e calcula modificadores sociais."""
    mundo_path = campaign_info.get("mundo")
    ficha_path = campaign_info.get("ficha")
    npcs_path = campaign_info.get("npcs")

    if not mundo_path or not mundo_path.exists():
        return []

    factions = parse_factions_from_mundo(mundo_path)
    if not factions:
        return []
    reputations = parse_reputation_from_ficha(ficha_path) if ficha_path and ficha_path.exists() else {}

    all_npcs = parse_npcs_md(npcs_path) if npcs_path and npcs_path.exists() else []
    npc_faction_map = {}
    for n in all_npcs:
        n_low = n["name"].lower().strip()
        n_fac = (n.get("faction") or "").strip()

        # Se não tiver facção explícita ou for genérica
        if not n_fac or n_fac.lower() in ("independente", "neutro", "nenhuma", "-"):
            for f in factions:
                if n_low in f.get("description", "").lower():
                    n_fac = f["name"]
                    break
            if not n_fac or n_fac.lower() in ("independente", "neutro", "nenhuma", "-"):
                npc_profile = f"{n.get('role', '')} {n.get('classification', '')} {n.get('summary', '')}".lower()
                for f in factions:
                    if f["name"].lower() in npc_profile or f["tag"].lower() in npc_profile:
                        n_fac = f["name"]
                        break

        if n_fac and n_fac.lower() not in ("independente", "neutro", "nenhuma", "-"):
            npc_faction_map[n_low] = n_fac

    matched_factions = []
    seen_tags = set()

    # 1. Resolução por NPCs presentes em cena
    for pres_name in scene_npcs:
        pres_low = pres_name.lower().strip()
        if not pres_low:
            continue
        matched_npc_fac = None
        for n_k, n_fac in npc_faction_map.items():
            if n_k in pres_low or pres_low in n_k:
                matched_npc_fac = n_fac
                break

        if not matched_npc_fac:
            for f in factions:
                if f["name"].lower() in pres_low:
                    matched_npc_fac = f["name"]
                    break

        if matched_npc_fac:
            for f in factions:
                if f["name"].lower() == matched_npc_fac.lower() or f["tag"].lower() == matched_npc_fac.lower():
                    if f["tag"] not in seen_tags:
                        seen_tags.add(f["tag"])
                        rep_data = reputations.get(f["name"].lower(), reputations.get(f["tag"].lower(), {}))
                        score = rep_data.get("score", 0)
                        tier = rep_data.get("tier", "Neutro")
                        favors = rep_data.get("favors", 0)
                        debts = rep_data.get("debts", 0)
                        dc_mod = SOCIAL_DC_MODIFIERS.get(score, 0)
                        variant = SUGGESTED_VARIANTS.get(score, "normal")

                        directive = "Postura diplomática neutra e pragmática."
                        if score >= 2:
                            directive = f"POSTURA OBRIGATÓRIA DE FACÇÃO ALIADA ({tier}): Membros desta facção agem com prestatividade, oferecem refúgio e colaboração armada."
                        elif score <= -2:
                            directive = f"POSTURA OBRIGATÓRIA DE FACÇÃO HOSTIL: Membros de {f['name']} tratam o protagonista como inimigo jurado ({score}). Proibida qualquer cordialidade, cooperação espontânea ou confiança sem coerção física ou chantagem comprovada."

                        matched_factions.append({
                            "name": f["name"],
                            "tag": f["tag"],
                            "score": score,
                            "tier": tier,
                            "favors": favors,
                            "debts": debts,
                            "social_dc_mod": dc_mod,
                            "suggested_variant": variant,
                            "source": "npc",
                            "focal_members": [pres_name],
                            "members_in_scene": [pres_name],
                            "writer_directive": directive,
                        })
                    else:
                        for mf in matched_factions:
                            if mf["tag"] == f["tag"]:
                                if pres_name not in mf["members_in_scene"]:
                                    mf["members_in_scene"].append(pres_name)
                                    mf["focal_members"].append(pres_name)

    # 2. Resolução por Território / Localização
    loc_clean = (location or "").strip()
    if loc_clean:
        loc_low = loc_clean.lower()
        stopwords_loc = {"posto", "zona", "ruas", "porto", "sala", "torre", "ponte", "castelo", "distrito", "vila", "cidade", "aposentos", "palacio", "quarto", "corredor"}
        loc_keywords = [w for w in re.findall(r"\w{4,}", loc_low) if w not in stopwords_loc]

        for f in factions:
            f_desc_low = f.get("description", "").lower()
            f_name_low = f["name"].lower()
            is_territory = False

            if f_name_low in loc_low:
                is_territory = True
            elif loc_low in f_desc_low:
                is_territory = True
            elif any(kw in f_desc_low for kw in loc_keywords):
                is_territory = True

            if is_territory:
                if f["tag"] not in seen_tags:
                    seen_tags.add(f["tag"])
                    rep_data = reputations.get(f["name"].lower(), reputations.get(f["tag"].lower(), {}))
                    score = rep_data.get("score", 0)
                    tier = rep_data.get("tier", "Neutro")
                    favors = rep_data.get("favors", 0)
                    debts = rep_data.get("debts", 0)
                    dc_mod = SOCIAL_DC_MODIFIERS.get(score, 0)
                    variant = SUGGESTED_VARIANTS.get(score, "normal")

                    directive = f"TERRITÓRIO DOMINADO POR {f['name']} ({tier}): O protagonista opera sob jurisdição e vigilância de {f['name']} em '{loc_clean}'."
                    if score >= 2:
                        directive += " Facilidade de trânsito, refúgio seguro e cooperação da população local."
                    elif score <= -2:
                        directive += " Território hostil: patrulhas ativas, desconfiança ostensiva e risco imediato de emboscada ou denúncia."
                    else:
                        directive += f" Modificador social {dc_mod} aplicado em interações públicas."

                    matched_factions.append({
                        "name": f["name"],
                        "tag": f["tag"],
                        "score": score,
                        "tier": tier,
                        "favors": favors,
                        "debts": debts,
                        "social_dc_mod": dc_mod,
                        "suggested_variant": variant,
                        "source": "territory",
                        "territory_in_scene": loc_clean,
                        "focal_members": [],
                        "members_in_scene": [],
                        "writer_directive": directive,
                    })
                else:
                    for mf in matched_factions:
                        if mf["tag"] == f["tag"]:
                            mf["territory_in_scene"] = loc_clean

    return matched_factions
