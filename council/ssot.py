"""council.ssot: Parsers e persistência dos 5 arquivos Markdown (ficha, diario, npcs, mundo, regras)."""

import re
from pathlib import Path

def normalize_vital_key(raw: str, vitals_dict: dict = None) -> str:
    """Normaliza o nome de qualquer recurso vital dinamicamente a partir da ficha.md ou sinônimos universais."""
    low = raw.strip().lower()
    if low in ("hp", "vida", "pv", "saúde", "saude"):
        base = "hp"
    elif low in ("stamina", "folego", "fôlego", "fadiga", "sta", "vigor"):
        base = "stamina"
    elif low in ("ce", "mp", "energia", "mana", "ea", "pe", "magia"):
        base = "ce"
    else:
        base = low

    if vitals_dict:
        if base in vitals_dict:
            return base
        for k, v in vitals_dict.items():
            lbl_low = v["label"].lower()
            short_low = lbl_low.split("(")[0].strip()
            m_abbr = re.search(r"\(([^)]+)\)", lbl_low)
            abbr_low = m_abbr.group(1).strip() if m_abbr else ""
            if low in (k, lbl_low, short_low, abbr_low):
                return k
    return base


def parse_ficha_md(ficha_path: Path) -> dict:
    """Extrai dinamicamente nome, recursos vitais (qualquer 'Recurso: X/Y') e atributos de ficha.md."""
    data = {"name": "Protagonista", "vitals": {}, "stats": {}, "raw_vitals_line": "", "inventory": [], "milestones": []}
    if not ficha_path.exists():
        return data
    text = ficha_path.read_text(encoding="utf-8")

    m_name = re.search(r"\*\*Nome:\*\*\s*([^\n(—]+)", text)
    if m_name:
        data["name"] = m_name.group(1).strip()

    vitals_parts = []
    for m in re.finditer(r"\*\s*\*\*([^:*]+):\*\*\s*(\d+)\s*/\s*(\d+)", text):
        label, cur, mx = m.group(1).strip(), int(m.group(2)), int(m.group(3))
        low = label.lower()
        m_abbr = re.search(r"\(([^)]+)\)", low)
        abbr = m_abbr.group(1).strip() if m_abbr else ""
        short_name = low.split("(")[0].strip()

        if "hp" in low or "vida" in low or "pv" in low:
            key = "hp"
        elif "stamina" in low or "fôlego" in low or "folego" in low or "fadiga" in low or "vigor" in low:
            key = "stamina"
        elif "ce" in (low, abbr) or "energia" in low or "mp" in (low, abbr) or "mana" in low:
            key = "ce"
        else:
            key = abbr or short_name

        data["vitals"][key] = {"label": label, "current": cur, "max": mx, "short": label.split("(")[0].strip(), "abbr": abbr}
        vitals_parts.append(f"{label}: {cur}/{mx}")
    data["raw_vitals_line"] = " | ".join(vitals_parts)

    # Extrai qualquer atributo no formato '* **COD ...:** Valor' ou '* **Atributo (COD):** Valor'
    for m in re.finditer(r"\*\s*\*\*([A-ZÀ-Ú]{2,5})\b[^*]*\*\*\s*(\d+)", text):
        stat_code = m.group(1).upper()
        val = int(m.group(2))
        data["stats"][stat_code] = val

    # Extrai inventário
    inventory = []
    m_inv = re.search(r"### Equipamento & Inventário\s*\n(.*?)(?=\n###|\Z)", text, re.DOTALL)
    if m_inv:
        for line in m_inv.group(1).splitlines():
            line = line.strip()
            if line.startswith("*"):
                inventory.append(line.lstrip("* ").strip())
    data["inventory"] = inventory

    # Extrai marcos
    milestones = []
    m_mil = re.search(r"### Marcos de Evolução Pessoal[^\n]*\s*\n(.*?)(?=\n###|\Z)", text, re.DOTALL)
    if m_mil:
        for line in m_mil.group(1).splitlines():
            line = line.strip()
            if line.startswith("*"):
                milestones.append(line.lstrip("* ").strip())
    data["milestones"] = milestones

    return data


def render_progress_bar(current: int, max_steps: int, length: int = 4) -> str:
    """Gera uma barra de progresso em texto simples (ex: [██░░])."""
    if max_steps <= 0:
        return "[]"
    filled = min(max_steps, max(0, current))
    ratio = filled / max_steps
    bar_filled = round(ratio * length)
    return "[" + ("█" * bar_filled) + ("░" * (length - bar_filled)) + "]"


def upsert_ficha_feature(
    ficha_path: Path,
    ability: str = "",
    milestone: str = "",
    item: str = "",
) -> list:
    """Insere novas Habilidades, Marcos ou Itens em ficha.md atomicamente."""
    if not ficha_path.exists():
        return []
    text = ficha_path.read_text(encoding="utf-8")
    applied = []

    if ability:
        sec = "### Habilidades & Técnicas"
        if sec in text:
            idx = text.find(sec) + len(sec)
            line = ability.strip().lstrip("* -")
            if not line.startswith("**"):
                if ":" in line:
                    title, desc = line.split(":", 1)
                    formatted_line = f"\n* **{title.strip()}:** {desc.strip()}"
                else:
                    formatted_line = f"\n* **{line}:** Habilidade adquirida."
            else:
                formatted_line = f"\n* {line}"
            text = text[:idx] + formatted_line + text[idx:]
            applied.append(f"Habilidade adicionada à ficha: {ability.strip()}")

    if milestone:
        sec = "### Marcos de Evolução Pessoal (Milestones do Protagonista)"
        if sec in text:
            idx = text.find(sec) + len(sec)
            line = milestone.strip().lstrip("* -")
            formatted_line = f"\n* {line}" if line.startswith("**") or line.startswith("Marco") else f"\n* **{line}**"
            text = text[:idx] + formatted_line + text[idx:]
            applied.append(f"Marco adicionado à ficha: {milestone.strip()}")

    if item:
        sec = "### Equipamento & Inventário"
        if sec in text:
            idx = text.find(sec) + len(sec)
            line = item.strip().lstrip("* -")
            formatted_line = f"\n* {line}"
            text = text[:idx] + formatted_line + text[idx:]
            applied.append(f"Item adicionado ao inventário: {item.strip()}")

    if applied:
        ficha_path.write_text(text, encoding="utf-8")
    return applied


def parse_clocks_from_diario(diario_path: Path) -> list:
    """Extrai os Relógios Narrativos de Ameaça e Facções cadastrados em diario.md."""
    if not diario_path.exists():
        return []
    text = diario_path.read_text(encoding="utf-8")
    clocks = []
    pattern = r"\*\s*\*\*\[([^\]]+)\]:\*\*\s*(\d+)\s*/\s*(\d+)(?:\s*\((?:Gatilho:\s*)?([^)]*)\))?(?:\s*\[(ACTIVE|BREACHED|RESOLVED)\])?"
    for m in re.finditer(pattern, text, re.IGNORECASE):
        name = m.group(1).strip()
        cur = int(m.group(2))
        max_s = int(m.group(3))
        trigger = (m.group(4) or "").strip()
        raw_status = (m.group(5) or "").upper()
        if cur >= max_s and raw_status != "RESOLVED":
            status = "BREACHED"
        elif raw_status in ("ACTIVE", "BREACHED", "RESOLVED"):
            status = raw_status
        else:
            status = "ACTIVE"
        clocks.append({
            "name": name,
            "current": cur,
            "max": max_s,
            "progress": f"{cur}/{max_s}",
            "trigger": trigger,
            "status": status,
            "bar": render_progress_bar(cur, max_s),
        })
    return clocks


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
        text = re.sub(r"(\*\s*\*\*\[[^\]]+\]:\*\*\s*\d+/\d+[^\n]*?)\[ACTIVE\]", repl_clk, text, flags=re.IGNORECASE)
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
            text = text[:m_sc.start()] + f"## Cena {cur_num}: {scene_name.strip()}" + text[m_sc.end():]
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
            text = text[:m_dt_loc.start(2)] + f"{final_dt} — {final_loc}." + text[m_dt_loc.end():]
            applied.append(f"Data & Local atualizados -> '{final_dt} — {final_loc}'.")

    if present:
        text = re.sub(r"(\*\s*\*\*Presentes:\*\*\s*)[^\n]+", rf"\g<1>{present.strip()}.", text, count=1)
        applied.append(f"Presentes atualizados -> '{present.strip()}'.")

    if archive_milestone:
        sec_m = "### Marcos da Crônica"
        if sec_m in text:
            idx = text.find(sec_m) + len(sec_m)
            text = text[:idx] + f"\n* {archive_milestone.strip()}" + text[idx:]
            applied.append(f"Marco da Crônica registrado: '{archive_milestone.strip()}'.")

    diario_path.write_text(text, encoding="utf-8")
    return {"action": "arc_updated", "updates": applied}


def upsert_clock_in_diario(
    diario_path: Path,
    name: str,
    current: int = None,
    max_steps: int = None,
    trigger: str = "",
    status: str = "",
    advance: int = 0,
) -> dict:
    """Insere, atualiza ou avança um Relógio Narrativo em diario.md atomicamente."""
    if not diario_path.exists():
        return {"error": "diario.md não encontrado"}
    text = diario_path.read_text(encoding="utf-8")

    section_header = "### Relógios de Ameaça & Prazos"
    if "Relógios de Ameaça & Prazos" not in text:
        m_scene = re.search(r"(##\s*Cena\s+[^\n]+)", text)
        if m_scene:
            ins_pos = m_scene.end()
            text = text[:ins_pos] + f"\n\n{section_header}\n" + text[ins_pos:]
        else:
            text = f"{section_header}\n\n" + text

    clock_pat = rf"(\*\s*\*\*\[{re.escape(name)}\]:\*\*\s*)(\d+)\s*/\s*(\d+)(?:\s*\((?:Gatilho:\s*)?([^)]*)\))?(?:\s*\[(ACTIVE|BREACHED|RESOLVED)\])?"
    m = re.search(clock_pat, text, re.IGNORECASE)

    if m:
        cur_val = int(m.group(2))
        max_val = int(m.group(3))
        existing_trigger = (m.group(4) or "").strip()
        existing_status = (m.group(5) or "").upper() or "ACTIVE"

        new_max = max_steps if max_steps is not None else max_val
        if current is not None:
            new_cur = current
        elif advance:
            new_cur = cur_val + advance
        else:
            new_cur = cur_val

        new_cur = max(0, new_cur)
        new_trigger = trigger.strip() if trigger else existing_trigger

        if status:
            new_status = status.upper()
        elif new_cur >= new_max and existing_status != "RESOLVED":
            new_status = "BREACHED"
        else:
            new_status = "ACTIVE" if existing_status != "RESOLVED" else "RESOLVED"

        trigger_part = f" (Gatilho: {new_trigger})" if new_trigger else ""
        new_line = f"* **[{name}]:** {new_cur}/{new_max}{trigger_part} [{new_status}]"
        text = text[:m.start()] + new_line + text[m.end():]
        diario_path.write_text(text, encoding="utf-8")
        return {
            "name": name,
            "current": new_cur,
            "max": new_max,
            "trigger": new_trigger,
            "status": new_status,
            "bar": render_progress_bar(new_cur, new_max),
            "action": "updated",
        }
    else:
        new_max = max_steps if max_steps is not None else 4
        new_cur = current if current is not None else 0
        if advance:
            new_cur += advance
        new_cur = max(0, new_cur)
        new_trigger = trigger.strip()
        new_status = status.upper() if status else ("BREACHED" if new_cur >= new_max else "ACTIVE")

        trigger_part = f" (Gatilho: {new_trigger})" if new_trigger else ""
        new_line = f"* **[{name}]:** {new_cur}/{new_max}{trigger_part} [{new_status}]\n"

        sec_idx = text.find(section_header)
        after_header = sec_idx + len(section_header)
        text = text[:after_header] + "\n" + new_line + text[after_header:]
        diario_path.write_text(text, encoding="utf-8")
        return {
            "name": name,
            "current": new_cur,
            "max": new_max,
            "trigger": new_trigger,
            "status": new_status,
            "bar": render_progress_bar(new_cur, new_max),
            "action": "created",
        }


def parse_plot_from_diario(diario_path: Path) -> dict:
    """Extrai cenas planejadas e marcos futuros de diario.md (Planejamento de Trama & Fila de Cenas)."""
    data = {"planned_scenes": [], "future_milestones": [], "next_scene": None}
    if not diario_path.exists():
        return data
    text = diario_path.read_text(encoding="utf-8")
    sec_match = re.search(r"###\s*Planejamento de Trama[^\n]*\n(.*?)(?=\n###|\n##|\Z)", text, re.DOTALL | re.IGNORECASE)
    if not sec_match:
        return data
    sec_text = sec_match.group(1)

    item_pattern = r"\*\s*\[([ xX])\]\s*\*\*\[([^\]]+)\]\*\*(?:\s*\((?:Atores:\s*)?([^)]+)\))?:\s*([^\n]+)"
    for m in re.finditer(item_pattern, sec_text):
        done = m.group(1).lower() == "x"
        scene_type = m.group(2).strip().lower()
        actors = (m.group(3) or "").strip()
        beat = m.group(4).strip()
        scene_obj = {
            "done": done,
            "scene_type": scene_type,
            "actors": actors,
            "beat": beat,
        }
        data["planned_scenes"].append(scene_obj)
        if not done and data["next_scene"] is None:
            data["next_scene"] = scene_obj

    for line in sec_text.splitlines():
        line_s = line.strip()
        if not line_s or re.search(r"\[([ xX])\]\s*\*\*\[", line_s):
            continue
        m_m = re.match(r"\*\s*\*\*Marco[^*]*\*\*:\s*([^\n]+)", line_s) or re.match(r"\*\s*\*\*Marco[^*]*:\*\*\s*([^\n]+)", line_s)
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

    # Se a seção não existir, insere antes de '### Marcos da Crônica' ou '### Histórico de Turnos'
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

    # Se for para marcar como concluída
    if mark_done_idx is not None:
        matches = list(re.finditer(r"\*\s*\[ \]\s*\*\*\[", text))
        if 0 <= mark_done_idx < len(matches):
            m = matches[mark_done_idx]
            text = text[:m.start()] + "* [x] **[" + text[m.end():]
            diario_path.write_text(text, encoding="utf-8")
            return {"action": "completed", "index": mark_done_idx}
        return {"error": f"Índice de cena {mark_done_idx} não encontrado"}

    # Se for para adicionar novo marco futuro
    if future_milestone:
        sec_idx = text.find(section_header) + len(section_header)
        new_line = f"\n* **Marco Futuro:** {future_milestone.strip()}"
        text = text[:sec_idx] + new_line + text[sec_idx:]
        diario_path.write_text(text, encoding="utf-8")
        return {"action": "milestone_added", "milestone": future_milestone}

    # Se for para adicionar nova cena à fila
    if beat:
        actors_part = f" (Atores: {actors.strip()})" if actors else ""
        new_line = f"\n* [ ] **[{scene_type.lower().strip()}]**{actors_part}: {beat.strip()}"
        sec_idx = text.find(section_header) + len(section_header)
        text = text[:sec_idx] + new_line + text[sec_idx:]
        diario_path.write_text(text, encoding="utf-8")
        return {"action": "scene_added", "scene_type": scene_type, "actors": actors, "beat": beat}

    return {"action": "noop"}


def parse_diario_md(diario_path: Path) -> dict:
    """Extrai data/hora, local, presentes, último turno, relógios, arco, ritmo e plano de trama de diario.md."""
    ctx = {
        "date_time": "Dia 1, 12:00",
        "location": "Local Ativo",
        "present": "Presentes na Cena",
        "last_turn_num": 0,
        "last_turn_summary": "",
        "clocks": [],
        "arc": {},
        "plot_plan": {},
        "recent_state_shifts": [],
        "consecutive_standard_turns": 0,
        "total_turns": 0,
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

    # Reconhece turnos com ou sem tag estrutural (ex: Turno 56 ou Turno 56 [INTERLÚDIO])
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
    for m in re.finditer(r"\*\s*\*\*Turno\s+(\d+)(?:\s*\[[^\]]+\])?:\*\*[^\n]+\n\s*\*\s*\*\*Mudança de Estado:\*\*\s*([^\n]+)", text):
        shifts.append({"turn": int(m.group(1)), "shift": m.group(2).strip()})
    ctx["recent_state_shifts"] = shifts

    ctx["clocks"] = parse_clocks_from_diario(diario_path)
    ctx["arc"] = parse_arc_from_diario(diario_path)
    ctx["plot_plan"] = parse_plot_from_diario(diario_path)

    return ctx


def extract_turns_from_diario(diario_path: Path, turns_spec: str = "") -> list:
    """Extrai turnos específicos (ex: '40-46' ou últimos 5) do diario.md para o Modo Escritor."""
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
