"""resources/ledger.py: Domínio e parsers do diário de campanha, arcos e trama (diario.md)."""

from __future__ import annotations

import re
from pathlib import Path

from adapters.persistence.files import atomic_write_text
from resources.clocks import parse_clocks_from_diario

def parse_arc_from_diario(diario_path: Path) -> dict:
    """Extrai o Arco Narrativo Ativo de diario.md ou retorna valor padrão agnóstico."""
    default_arc = {
        "title": "Arco Principal da Campanha",
        "central_question": "Como os protagonistas superarão o conflito e a resistência iminente?",
        "stage": "Confrontação",
    }
    if not diario_path.exists():
        return default_arc
    text = diario_path.read_text(encoding="utf-8")
    m_title = re.search(r"\*\s*\*\*(?:Título|Arco|Nome):\*\*\s*([^\n]+)", text, re.IGNORECASE)
    m_q = re.search(r"\*\s*\*\*(?:Pergunta Central|Conflito Central|Questão):\*\*\s*([^\n]+)", text, re.IGNORECASE)
    m_stage = re.search(r"\*\s*\*\*(?:Fase|Estágio|Etapa):\*\*\s*([^\n]+)", text, re.IGNORECASE)
    if m_title:
        default_arc["title"] = m_title.group(1).strip().rstrip(".")
    if m_q:
        default_arc["central_question"] = m_q.group(1).strip().rstrip(".")
    if m_stage:
        default_arc["stage"] = m_stage.group(1).strip().rstrip(".")
    return default_arc

def update_arc_in_diario(
    diario_path: Path,
    title: str = "",
    central_question: str = "",
    stage: str = "",
    scene_name: str = "",
    date_time: str = "",
    location: str = "",
    present: str = "",
    resolve_clocks: bool = False,
    archive_milestone: str = "",
) -> dict:
    """Atualiza o Arco Dramático, cabeçalho da cena ativa e marcos em diario.md."""
    if not diario_path.exists():
        return {"error": "diario.md não encontrado"}
    text = diario_path.read_text(encoding="utf-8")
    applied = []

    if resolve_clocks:
        count = 0

        def repl_clk(m):
            nonlocal count
            count += 1
            return m.group(1) + "[RESOLVED]"

        text = re.sub(
            r"(\*\s*\*\*\[[^\]]+\]:\*\*\s*\d+/\d+[^\n]*?)\[ACTIVE\]",
            repl_clk,
            text,
            flags=re.IGNORECASE,
        )
        applied.append(f"{count} relógios ativos marcados como RESOLVED.")

    if title:
        text = re.sub(r"(\*\s*\*\*(?:Título|Arco|Nome):\*\*\s*)[^\n]+", rf"\g<1>{title.strip()}", text, flags=re.IGNORECASE)
        applied.append(f"Título do Arco atualizado -> '{title.strip()}'.")
    if central_question:
        text = re.sub(r"(\*\s*\*\*(?:Pergunta Central|Conflito Central|Questão):\*\*\s*)[^\n]+", rf"\g<1>{central_question.strip()}", text, flags=re.IGNORECASE)
        applied.append(f"Pergunta Central atualizada -> '{central_question.strip()}'.")
    if stage:
        text = re.sub(r"(\*\s*\*\*(?:Fase|Estágio|Etapa):\*\*\s*)[^\n]+", rf"\g<1>{stage.strip()}", text, flags=re.IGNORECASE)
        applied.append(f"Fase do Arco atualizada -> '{stage.strip()}'.")

    if scene_name:
        m_sc = re.search(r"##\s*Cena\s+(\d+):[^\n]+", text, re.IGNORECASE)
        if m_sc:
            cur_num = int(m_sc.group(1)) + 1
            text = text[: m_sc.start()] + f"## Cena {cur_num}: {scene_name.strip()}" + text[m_sc.end() :]
        else:
            text = re.sub(r"##\s*Cena[^\n]+", f"## Cena 2: {scene_name.strip()}", text, count=1, flags=re.IGNORECASE)
        applied.append(f"Cabeçalho de Cena atualizado -> '{scene_name.strip()}'.")

    if date_time or location:
        m_dt_loc = re.search(r"(\*\s*\*\*Data\s*&\s*Local:\*\*\s*)([^\n]+)", text)
        if m_dt_loc:
            cur_val = m_dt_loc.group(2).strip().rstrip(".")
            cur_dt, cur_loc = cur_val.split("—", 1) if "—" in cur_val else (cur_val, "Local Ativo")
            final_dt = date_time.strip() if date_time else cur_dt.strip()
            final_loc = location.strip() if location else cur_loc.strip()
            text = text[: m_dt_loc.start(2)] + f"{final_dt} — {final_loc}." + text[m_dt_loc.end() :]
            applied.append(f"Data & Local atualizados -> '{final_dt} — {final_loc}'.")

    if present:
        text = re.sub(r"(\*\s*\*\*Presentes:\*\*\s*)[^\n]+", rf"\g<1>{present.strip()}.", text, count=1)
        applied.append(f"Presentes atualizados -> '{present.strip()}'.")

    if archive_milestone:
        sec_m = "### Marcos da Crônica"
        if sec_m in text:
            ms_entry = f"* {archive_milestone.strip()}"
            if ms_entry not in text:
                idx = text.find(sec_m) + len(sec_m)
                text = text[:idx] + f"\n{ms_entry}" + text[idx:]
                applied.append(f"Marco da Crônica registrado: '{archive_milestone.strip()}'.")
            else:
                applied.append(f"Marco da Crônica '{archive_milestone.strip()}' já constava nos registros.")

    atomic_write_text(diario_path, text)
    return {"action": "arc_updated", "updates": applied}

def parse_plot_from_diario(diario_path: Path) -> dict:
    """Extrai cenas planejadas e marcos futuros de diario.md."""
    data = {"planned_scenes": [], "future_milestones": [], "next_scene": None}
    if not diario_path.exists():
        return data
    text = diario_path.read_text(encoding="utf-8")
    sec_match = re.search(
        r"###\s*Planejamento de Trama[^\n]*\n(.*?)(?=\n###|\n##|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not sec_match:
        return data
    sec_text = sec_match.group(1)

    item_pattern = r"\*\s*\[([ xX])\]\s*\*\*\[([^\]]+)\]\*\*(?:\s*\((?:Atores:\s*)?([^)]+)\))?:\s*([^\n]+)"
    for m in re.finditer(item_pattern, sec_text):
        done = m.group(1).lower() == "x"
        scene_type = m.group(2).strip().lower()
        actors = (m.group(3) or "").strip()
        beat = m.group(4).strip()
        scene_obj = {"done": done, "scene_type": scene_type, "actors": actors, "beat": beat}
        data["planned_scenes"].append(scene_obj)
        if not done and data["next_scene"] is None:
            data["next_scene"] = scene_obj

    for line in sec_text.splitlines():
        line_s = line.strip()
        if not line_s or re.search(r"\[([ xX])\]\s*\*\*\[", line_s):
            continue
        m_m = re.match(r"\*\s*\*\*Marco[^*]*\*\*:\s*([^\n]+)", line_s) or re.match(
            r"\*\s*\*\*Marco[^*]*:\*\*\s*([^\n]+)", line_s
        )
        if m_m:
            val = m_m.group(1).strip()
            if val and not val.endswith(":"):
                data["future_milestones"].append(val)
        elif (line.startswith("  * ") or line.startswith("    * ")) and not line_s.startswith("* ["):
            sub_val = line_s.lstrip("* ").strip()
            if sub_val:
                data["future_milestones"].append(sub_val)

    return data

def upsert_planned_scene_in_diario(
    diario_path: Path,
    scene_type: str = "interlude",
    beat: str = "",
    actors: str = "",
    mark_done_idx: int = None,
    future_milestone: str = "",
) -> dict:
    """Cadastra nova cena planejada, marco futuro ou marca cena concluída em diario.md."""
    if not diario_path.exists():
        return {"error": "diario.md não encontrado"}
    text = diario_path.read_text(encoding="utf-8")
    section_header = "### Planejamento de Trama & Fila de Cenas"

    if section_header.lower() not in text.lower():
        insert_marker = "### Marcos da Crônica"
        if insert_marker in text:
            idx = text.find(insert_marker)
            text = text[:idx] + f"{section_header}\n\n" + text[idx:]
        else:
            insert_marker = "### Histórico de Turnos"
            if insert_marker in text:
                idx = text.find(insert_marker)
                text = text[:idx] + f"{section_header}\n\n" + text[idx:]
            else:
                text += f"\n\n{section_header}\n"

    if mark_done_idx is not None:
        matches = list(re.finditer(r"\*\s*\[ \]\s*\*\*\[", text))
        if 0 <= mark_done_idx < len(matches):
            m = matches[mark_done_idx]
            text = text[: m.start()] + "* [x] **[" + text[m.end() :]
            atomic_write_text(diario_path, text)
            return {"action": "completed", "index": mark_done_idx}
        return {"error": f"Índice de cena {mark_done_idx} não encontrado"}

    if future_milestone:
        sec_idx = text.find(section_header) + len(section_header)
        new_line = f"\n* **Marco Futuro:** {future_milestone.strip()}"
        text = text[:sec_idx] + new_line + text[sec_idx:]
        atomic_write_text(diario_path, text)
        return {"action": "milestone_added", "milestone": future_milestone}

    if beat:
        actors_part = f" (Atores: {actors.strip()})" if actors else ""
        new_line = f"\n* [ ] **[{scene_type.lower().strip()}]**{actors_part}: {beat.strip()}"
        sec_idx = text.find(section_header) + len(section_header)
        text = text[:sec_idx] + new_line + text[sec_idx:]
        atomic_write_text(diario_path, text)
        return {"action": "scene_added", "scene_type": scene_type, "actors": actors, "beat": beat}

    return {"action": "noop"}

def parse_diario_md(diario_path: Path) -> dict:
    """Extrai data/hora, local, presentes, último turno, relógios, arco e trama de diario.md."""
    ctx = {
        "date_time": "Dia 1, 12:00", "location": "Local Ativo", "present": "Presentes na Cena",
        "last_turn_num": 0, "last_turn_summary": "", "clocks": [], "arc": {}, "plot_plan": {},
        "recent_state_shifts": [], "consecutive_standard_turns": 0, "total_turns": 0,
    }
    if not diario_path.exists():
        return ctx
    text = diario_path.read_text(encoding="utf-8")

    for m in re.finditer(r"\*\*Data\s*&\s*Local:\*\*\s*([^\n]+)", text):
        raw = m.group(1).strip().rstrip(".")
        if "—" in raw:
            dt, loc = raw.split("—", 1)
            ctx["date_time"] = dt.strip()
            ctx["location"] = loc.strip()
        elif " - " in raw:
            dt, loc = raw.split(" - ", 1)
            ctx["date_time"] = dt.strip()
            ctx["location"] = loc.strip()
        else:
            ctx["date_time"] = raw

    for m in re.finditer(r"\*\*Presentes:\*\*\s*([^\n]+)", text):
        ctx["present"] = m.group(1).strip().rstrip(".")

    all_turns = []
    for m in re.finditer(r"\*\s*\*\*Turno\s+(\d+)(?:\s*\[([^\]]+)\])?:\*\*\s*([^\n]+)", text):
        t_num = int(m.group(1))
        t_tag = (m.group(2) or "").strip().upper()
        t_sum = m.group(3).strip()
        all_turns.append({"turn": t_num, "tag": t_tag, "summary": t_sum})
        ctx["last_turn_num"] = t_num
        ctx["last_turn_summary"] = t_sum

    consecutive_standard = 0
    for t in reversed(all_turns):
        tag = t["tag"]
        if not tag or tag in ("STANDARD", "PADRÃO", "PADRAO"):
            consecutive_standard += 1
        else:
            break
    ctx["consecutive_standard_turns"] = consecutive_standard
    ctx["total_turns"] = len(all_turns)

    shifts = []
    for m in re.finditer(
        r"\*\s*\*\*Turno\s+(\d+)(?:\s*\[[^\]]+\])?:\*\*[^\n]+\n\s*\*\s*\*\*Mudança de Estado:\*\*\s*([^\n]+)",
        text,
    ):
        shifts.append({"turn": int(m.group(1)), "shift": m.group(2).strip()})
    ctx["recent_state_shifts"] = shifts

    ctx["clocks"] = parse_clocks_from_diario(diario_path)
    ctx["arc"] = parse_arc_from_diario(diario_path)
    ctx["plot_plan"] = parse_plot_from_diario(diario_path)

    return ctx

def extract_turns_from_diario(diario_path: Path, turns_spec: str = "") -> list[dict]:
    """Extrai turnos específicos do diario.md para o Modo Escritor."""
    if not diario_path.exists():
        return []
    text = diario_path.read_text(encoding="utf-8")
    matches = re.findall(r"\*\s*\*\*Turno\s+(\d+)(?:\s*\[[^\]]+\])?:\*\*\s*([^\n]+)", text)
    all_turns = [{"turn": int(num), "text": body.strip()} for num, body in matches]
    if not all_turns:
        return []
    if turns_spec and "-" in turns_spec:
        start_s, end_s = turns_spec.split("-", 1)
        start_t, end_t = int(start_s.strip()), int(end_s.strip())
        return [t for t in all_turns if start_t <= t["turn"] <= end_t]
    if turns_spec and turns_spec.strip().isdigit():
        target = int(turns_spec.strip())
        return [t for t in all_turns if t["turn"] == target]
    return all_turns[-5:]

__all__ = [
    "extract_turns_from_diario",
    "parse_arc_from_diario",
    "parse_diario_md",
    "parse_plot_from_diario",
    "update_arc_in_diario",
    "upsert_planned_scene_in_diario",
]
