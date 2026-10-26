"""resources/factions/tick.py: Agência Off-Screen e Tick de Mundo de Facções (RPGPRO).

Avança deterministicamente relógios narrativos de facções com base em seu atributo de Poder (1 a 5).
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from council.helpers import atomic_write_text
from resources.factions.parser import parse_factions_from_mundo


def simulate_faction_tick(campaign_info: Dict[str, Any]) -> Dict[str, Any]:
    """Avança deterministicamente relógios narrativos de facções com base em seu atributo de Poder (1 a 5).

    Regra de Agência Off-Screen Determinística:
    - Poder 4 ou 5: avança 1 passo garantido no tick.
    - Poder 2 ou 3: avança 1 passo se o relógio já foi iniciado em cena (current >= 1).
    - Poder 1: só avança em cena sob intervenção direta do protagonista.
    """
    mundo_path = campaign_info["mundo"]
    diario_path = campaign_info["diario"]

    if not mundo_path.exists() or not diario_path.exists():
        return {"error": "Arquivos mundo.md ou diario.md não localizados."}

    from council.ssot import parse_clocks_from_diario, upsert_clock_in_diario, parse_diario_md

    factions = parse_factions_from_mundo(mundo_path)
    clocks = parse_clocks_from_diario(diario_path)
    clock_map = {c["name"].lower(): c for c in clocks}

    advancements = []
    breaches = []

    for f in factions:
        c_name = f.get("clock")
        if not c_name:
            continue
        c_match = clock_map.get(c_name.lower())
        if not c_match or c_match.get("status") != "ACTIVE":
            continue

        power = f.get("power", 3)
        should_advance = False
        if power >= 4:
            should_advance = True
        elif power >= 2 and c_match["current"] >= 1:
            should_advance = True

        if should_advance:
            res = upsert_clock_in_diario(diario_path, c_match["name"], advance=1, create_if_missing=False)
            adv = {
                "faction": f["name"],
                "power": power,
                "clock": c_match["name"],
                "previous_progress": c_match["progress"],
                "new_progress": f"{res['current']}/{res['max']}",
                "status": res["status"],
            }
            advancements.append(adv)
            if res.get("status") == "BREACHED":
                breaches.append(adv)

    if advancements:
        cur_turn = parse_diario_md(diario_path).get("last_turn_num", 1)
        d_text = diario_path.read_text(encoding="utf-8")
        lines_to_add = [f"* **Tick Off-Screen (Turno {cur_turn}):**"]
        for adv in advancements:
            b_note = " [Gatilho de Ruptura Disparado!]" if adv.get("status") == "BREACHED" else ""
            lines_to_add.append(
                f"  * **{adv['faction']}:** Avançou relógio '{adv['clock']}' para {adv['new_progress']} (Poder {adv['power']}){b_note}."
            )
        entry_block = "\n".join(lines_to_add)

        sec_header = "### Movimentações de Facções Off-Screen"
        if sec_header in d_text:
            m_sec = re.search(rf"({re.escape(sec_header)}[^\n]*\n)(.*?)(?=\n###|\Z)", d_text, re.DOTALL)
            if m_sec:
                header_part = m_sec.group(1)
                body_part = m_sec.group(2)
                new_sec = header_part + body_part.rstrip() + "\n" + entry_block + "\n"
                d_text = d_text[:m_sec.start()] + new_sec + d_text[m_sec.end():]
            else:
                d_text = d_text.rstrip() + f"\n\n{sec_header}\n{entry_block}\n"
        else:
            if "### Histórico de Turnos" in d_text:
                d_text = d_text.replace("### Histórico de Turnos", f"{sec_header}\n{entry_block}\n\n### Histórico de Turnos", 1)
            else:
                d_text = d_text.rstrip() + f"\n\n{sec_header}\n{entry_block}\n"
        atomic_write_text(diario_path, d_text)

    return {
        "campaign": campaign_info.get("id", ""),
        "operation": "faction_tick",
        "advancements": advancements,
        "breaches": breaches,
    }
