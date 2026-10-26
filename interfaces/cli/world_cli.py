"""interfaces/cli/world_cli.py: despacho dos comandos de simulação de mundo (Fase 05)."""

from __future__ import annotations

import json

from application.world_schedule import cmd_queue, cmd_schedule
from application.world_tick import cmd_world_tick


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def run_world_tick(args) -> int:
    res = cmd_world_tick(
        args.campaign,
        minutes=args.minutes,
        to=args.to,
        trigger=args.trigger,
        seed=args.seed,
        budget=args.budget,
        dry_run=args.dry_run,
    )
    if args.json:
        _print_json(res)
    elif res.get("error"):
        print(f"[ERRO]: {res['error']}")
    else:
        print(f"\nSimulação de Mundo — Campanha '{args.campaign}':")
        print(f"  Ciclo: {res['tick_id']} [{res['status']}]")
        print(f"  Tempo: {res['from']} -> {res['to']} (+{res['elapsed_minutes']} min, gatilho: {res['trigger']})")
        print(f"  Orçamento: {res['budget_limit']} itens ({'adaptativo' if res['budget_adaptive'] else 'teto explícito'})")
        print(f"  Executados: {len(res['selected'])} | Adiados: {len(res['deferred'])}")
        for outcome in res.get("outcomes", []):
            mark = "OK " if outcome["status"] == "completed" else "FALHA"
            print(f"    [{mark}] {outcome['kind']} {outcome['entity_id']}: "
                  f"{outcome.get('summary') or outcome.get('error')}")
        if res.get("silent_entities"):
            print("  Sem trabalho devido: " + ", ".join(res["silent_entities"]))
        if res.get("dry_run"):
            print("  [dry-run] Nada foi gravado.")
        else:
            print(f"  Eventos: {res.get('events_appended', 0)} | Fila: {res.get('queue_hash') or 'n/d'}")
    return 1 if res.get("error") else 0


def run_schedule(args) -> int:
    res = cmd_schedule(
        args.campaign,
        at=args.at,
        kind=args.kind,
        entity=args.entity,
        payload=args.payload,
        priority=args.priority,
    )
    if args.json:
        _print_json(res)
    elif res.get("error"):
        print(f"[ERRO]: {res['error']}")
    elif res.get("status") == "rejected":
        print(f"\nAgendamento rejeitado — Campanha '{args.campaign}':")
        for reason in res.get("reasons", []):
            print(f"  * {reason}")
    else:
        print(f"\nAgendamento registrado — Campanha '{args.campaign}':")
        print(f"  Trabalho: {res['work_id']} ({res['kind']} em '{res['entity_id']}')")
        print(f"  Quando: {res['due_game_time']} (sort {res['due_at_sort']}) | Prioridade {res['priority']}")
    if res.get("error"):
        return 1
    return 2 if res.get("status") == "rejected" else 0


def run_queue(args) -> int:
    res = cmd_queue(args.campaign)
    if args.json:
        _print_json(res)
    elif res.get("error"):
        print(f"[ERRO]: {res['error']}")
    else:
        print(f"\nFila de Simulação — Campanha '{args.campaign}':")
        last_tick = res.get("last_tick") or {}
        if last_tick:
            print(f"  Último ciclo: {last_tick.get('tick_id')} -> {last_tick.get('to_game_time')} "
                  f"({last_tick.get('selected')} executados, {last_tick.get('deferred')} adiados)")
        sections = (
            ("Agendados", res.get("scheduled", [])),
            ("Adiados", res.get("deferred", [])),
            ("Falhas", res.get("failed", [])),
        )
        empty = True
        for title, rows in sections:
            if not rows:
                continue
            empty = False
            print(f"\n  {title}:")
            for row in rows:
                extra = ""
                if title == "Falhas":
                    extra = f" | {row['attempts']} tentativa(s){' (permanente)' if row.get('permanent') else ''}"
                elif title == "Agendados":
                    extra = f" | due {row.get('due_game_time')}"
                print(f"    * {row['kind']} {row['entity_id']} [{row['work_id']}]{extra}")
        if empty:
            print("  (Fila vazia)")
        print(f"\n  Hash: {res.get('queue_hash') or 'n/d'}")
    return 1 if res.get("error") else 0


__all__ = ["run_queue", "run_schedule", "run_world_tick"]
