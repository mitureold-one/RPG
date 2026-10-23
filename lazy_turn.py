"""lazy_turn.py: Orquestrador Determinístico de Turno para RPG (SSOT Markdown + ai-memory).

Ponto de entrada enxuto. A lógica vive em:
- interfaces/cli: parser argparse, despacho e formatação de saída
- application: casos de uso (prepare, commit, clock, plan, arc, quest,
  progress, faction, check-prose) e fronteira transacional por campanha
- council/ e rulesets/: domínio (SSOT, NPCs, facções, missões, resolução)

Os nomes `cmd_*` e `build_cli` continuam reexportados aqui para não quebrar
testes e chamadas externas.
"""

import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from application import (  # noqa: E402
    cmd_arc,
    cmd_check_prose,
    cmd_clock,
    cmd_commit,
    cmd_faction,
    cmd_plan,
    cmd_prepare,
    cmd_progress,
    cmd_quest,
    cmd_review,
    validate_commit_entities,
)
from interfaces.cli import build_cli, main  # noqa: E402

__all__ = [
    "build_cli",
    "cmd_arc",
    "cmd_check_prose",
    "cmd_clock",
    "cmd_commit",
    "cmd_faction",
    "cmd_plan",
    "cmd_prepare",
    "cmd_progress",
    "cmd_quest",
    "cmd_review",
    "main",
    "validate_commit_entities",
]

if __name__ == "__main__":
    main()
