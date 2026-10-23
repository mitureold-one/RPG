"""Caso de uso de auditoria preventiva de prosa."""

import re
import sys
from pathlib import Path

from council import (
    find_campaign,
    parse_ficha_md,
    parse_npcs_md,
    check_prose_lints,
)


def cmd_check_prose(campaign_id: str = "", file_path: str = "", text: str = "") -> dict:
    """Audita rascunho de prosa literária contra regras de estilo (emojis, formato script, 4ª parede)."""
    prose_content = ""
    label = "prosa_inline"
    if file_path:
        f = Path(file_path)
        if not f.exists():
            return {"error": f"Arquivo de prosa '{file_path}' não encontrado.", "status": "FILE_NOT_FOUND", "has_violations": True, "issues": []}
        prose_content = f.read_text(encoding="utf-8")
        label = file_path
    elif text:
        prose_content = text
    else:
        if not sys.stdin.isatty():
            prose_content = sys.stdin.read()
            label = "stdin"
        else:
            return {"error": "Nenhum texto fornecido para check-prose. Use --file ou --text.", "status": "EMPTY", "has_violations": False, "issues": []}

    known_speakers = None
    if campaign_id:
        try:
            info = find_campaign(campaign_id)
            if info:
                ficha = parse_ficha_md(info["ficha"])
                all_npcs = parse_npcs_md(info["npcs"])
                known_speakers = set()
                if ficha.get("name"):
                    known_speakers.add(ficha["name"].strip())
                    for tok in re.split(r"[\s(),&_-]+", ficha["name"]):
                        if len(tok) >= 3 and tok[0].isupper():
                            known_speakers.add(tok)
                for npc_obj in all_npcs:
                    n_name = npc_obj.get("name", "").strip()
                    if n_name:
                        known_speakers.add(n_name)
                        for tok in re.split(r"[\s(),&_-]+", n_name):
                            if len(tok) >= 3 and tok[0].isupper():
                                known_speakers.add(tok)
        except Exception:
            pass

    issues = check_prose_lints(prose_content, context_label=label, known_speakers=known_speakers)
    return {
        "status": "CLEAN" if not issues else f"FOUND_{len(issues)}_ISSUES",
        "has_violations": len(issues) > 0,
        "campaign": campaign_id or None,
        "target": label,
        "issues": issues,
    }
