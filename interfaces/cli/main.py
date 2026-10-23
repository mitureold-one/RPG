"""Despacho da CLI: traduz argumentos em casos de uso e formata a saída."""

import json
import sys

from application import (
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
    find_campaign,
    init_campaign_from_templates,
    upsert_npc_to_md,
)
from interfaces.cli.parser import build_cli


def main():
    parser = build_cli()
    args = parser.parse_args()
    if args.cmd == "prepare":
        res = cmd_prepare(
            args.campaign,
            args.action,
            args.variant,
            args.dc,
            args.stat,
            args.roll,
            args.no_roll,
            args.mode,
            args.turns,
            args.stakes,
            args.critical,
            scene_type=args.scene_type,
            actors=args.actors,
            focus=args.focus,
            contest_npc=args.contest_npc,
            vs_npc=args.vs_npc,
            npc_stat=args.npc_stat,
            vs_stat=args.vs_stat,
            npc_variant=args.npc_variant,
            vs_variant=args.vs_variant,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "commit":
        res = cmd_commit(
            args.campaign,
            args.summary,
            args.cost,
            args.time,
            args.location,
            args.present_npcs,
            args.npc_updates,
            state_shift=args.state_shift,
            clock_advance=args.clock_advance,
            clock_resolve=args.clock_resolve,
            scene_type=args.scene_type,
            add_ability=args.add_ability,
            add_milestone=args.add_milestone,
            add_item=args.add_item,
            prose=args.prose,
            prose_file=args.prose_file,
            force=args.force,
            quest_progress=args.quest_progress,
            quest_complete=args.quest_complete,
            quest_fail=args.quest_fail,
            faction_rep=args.faction_rep,
            faction_favor=args.faction_favor,
            faction_debt=args.faction_debt,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        if res.get("prose_status") == "REJECTED":
            sys.exit(1)
    elif args.cmd == "check-prose":
        res = cmd_check_prose(
            campaign_id=args.campaign,
            file_path=args.file,
            text=args.text,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        if res.get("has_violations"):
            sys.exit(1)
    elif args.cmd == "review":
        res = cmd_review(args.campaign)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "clock":
        res = cmd_clock(
            args.campaign,
            list_clocks=args.list,
            add_name=args.add,
            max_steps=args.max,
            trigger=args.trigger,
            advance_name=args.advance,
            advance_steps=args.steps,
            resolve_name=args.resolve,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\nRelógios Narrativos — Campanha '{args.campaign}':")
            if not res.get("clocks"):
                print("  (Nenhum relógio cadastrado em diario.md)")
            for c in res.get("clocks", []):
                st_icon = "BREACHED" if c["status"] == "BREACHED" else ("RESOLVED" if c["status"] == "RESOLVED" else "ACTIVE")
                trig_txt = f" -> Gatilho: {c['trigger']}" if c["trigger"] else ""
                print(f"  * [{c['name']}]: {c['progress']} {c['bar']} [{st_icon}]{trig_txt}")
            if res.get("action_result"):
                act = res["action_result"]
                print(f"\n[Ação]: Relógio '{act.get('name')}' {act.get('action')} -> {act.get('current')}/{act.get('max')} [{act.get('status')}]")
    elif args.cmd == "plan":
        res = cmd_plan(
            args.campaign,
            list_plan=args.list,
            add_beat=args.add,
            scene_type=args.scene_type,
            actors=args.actors,
            complete_idx=args.complete,
            add_milestone=args.milestone,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\nPlanejamento de Trama & Fila de Cenas — Campanha '{args.campaign}':")
            print(f"  Arco Ativo: {res['arc'].get('title', 'Nenhum')} ({res['arc'].get('stage', 'Fase não definida')})")
            print(f"  Ritmo Linear: {res['consecutive_standard_turns']} turnos standard seguidos -> [{res['pacing_advice']}]")
            print("\n  Fila de Cenas Agendadas:")
            if not res.get("planned_scenes"):
                print("    (Nenhuma cena agendada em diario.md)")
            for idx, sc in enumerate(res.get("planned_scenes", [])):
                st = "[x]" if sc["done"] else "[ ]"
                act = f" (Atores: {sc['actors']})" if sc["actors"] else ""
                print(f"    {idx}. {st} [{sc['scene_type']}]{act}: {sc['beat']}")
            if res.get("future_milestones"):
                print("\n  Marcos Futuros do Arco:")
                for m in res["future_milestones"]:
                    print(f"    * {m}")
            if res.get("action_result") and res["action_result"] != "status_queried":
                print(f"\n[Ação]: {res['action_result']}")
    elif args.cmd == "arc":
        res = cmd_arc(
            args.campaign,
            title=args.title,
            question=args.question,
            stage=args.stage,
            scene_name=args.scene_name,
            location=args.location,
            date_time=args.date,
            present=args.present,
            resolve_clocks=args.resolve_clocks,
            milestone=args.milestone,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\nTransição de Arco / Cena — Campanha '{args.campaign}':")
            print(f"  Cabeçalho: {res['current_scene_header']}")
            print(f"  Arco: {res['arc'].get('title', 'Nenhum')} ({res['arc'].get('stage', 'Fase não definida')})")
            print(f"  Pergunta Central: {res['arc'].get('central_question', 'Nenhuma')}")
            for up in res.get("action_result", {}).get("updates", []):
                print(f"  * {up}")
    elif args.cmd == "upsert-npc":
        try:
            info = find_campaign(args.campaign)
        except (ValueError, FileNotFoundError) as e:
            print(json.dumps({"error": str(e)}))
            return
        if not info:
            print(json.dumps({"error": f"Campanha '{args.campaign}' não encontrada."}))
        else:
            res = upsert_npc_to_md(
                info["npcs"],
                name=args.name,
                classification=args.classification,
                role=args.role,
                faction=args.faction,
                attitude=args.attitude,
                psychology=args.psychology,
                will=args.will,
                weakness=args.weakness,
                dynamics=args.dynamics,
                appearance=args.appearance,
                bonds=args.bonds,
                relation=args.relation,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "init-campaign":
        res = init_campaign_from_templates(
            campaign_id=args.campaign,
            title=args.title,
            protagonist_name=args.protagonist,
            start_date=args.date,
            start_loc=args.location,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "quest":
        res = cmd_quest(
            args.campaign,
            list_quests=args.list,
            add_title=args.add,
            quest_type=args.type,
            objective=args.objective,
            faction=args.faction,
            clock=args.clock,
            reward=args.reward,
            phase=args.phase,
            check_target=args.check,
            complete_id=args.complete,
            fail_id=args.fail,
            block_id=args.block,
            unblock_id=args.unblock,
            abandon_id=args.abandon,
            reopen_id=args.reopen,
            reason=args.reason,
            evidence=args.evidence,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\nMissões & Objetivos — Campanha '{args.campaign}':")
            if not res.get("quests"):
                print("  (Nenhuma missão cadastrada em diario.md)")
            for q in res.get("quests", []):
                st_icon = q["status"]
                prg = f"[{q['progress_summary']}]"
                print(f"  * [{q['id']}] [{q['type']}] {q['title']} — {prg} [{st_icon}] (Recompensa: {q.get('reward') or 'N/A'})")
                for obj in q.get("objectives", []):
                    chk = "[x]" if obj["done"] else "[ ]"
                    print(f"      {obj['index']}. {chk} {obj['text']}")
            if res.get("action_result"):
                print(f"\n[Ação]: {res['action_result']}")
    elif args.cmd == "progress":
        res = cmd_progress(
            args.campaign,
            list_progress=args.list,
            spend_attr=args.spend_attr,
            spend_ability=args.spend_ability,
            training=args.training,
            award=args.award,
            reason=args.reason,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            prg = res.get("progression", {})
            print(f"\nProgressão do Protagonista — Campanha '{args.campaign}':")
            print(f"  Nível: {prg.get('level', 1)}")
            print(f"  Experiência (XP): {prg.get('xp', 0)} / {prg.get('next_threshold', 250)}")
            print(f"  Pontos de Atributo Disponíveis: {prg.get('attribute_points', 0)}")
            print(f"  Pontos de Habilidade Disponíveis: {prg.get('ability_points', 0)}")
            if res.get("action_result"):
                print(f"\n[Ação]: {res['action_result']}")
    elif args.cmd == "faction":
        res = cmd_faction(
            args.campaign,
            list_factions=args.list,
            add_name=args.add,
            tag=args.tag,
            power=args.power,
            scale=args.scale,
            clock=args.clock,
            desc=args.desc,
            rep=args.rep,
            reason=args.reason,
            favor=args.favor,
            debt=args.debt,
            tick=args.tick,
            create=args.create,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        elif res.get("error"):
            print(f"[ERRO]: {res['error']}")
        else:
            print(f"\nFacções & Reputação — Campanha '{args.campaign}':")
            if not res.get("factions"):
                print("  (Nenhuma facção cadastrada em mundo.md)")
            for f in res.get("factions", []):
                rep_info = f.get("protagonist_reputation", {})
                sc = rep_info.get("score", 0)
                tier = rep_info.get("tier", "Neutro")
                fav = rep_info.get("favors", 0)
                deb = rep_info.get("debts", 0)
                mod = rep_info.get("social_dc_modifier", 0)
                clk_str = f" [Relógio: {f['clock_progress'] or f.get('clock')}]" if f.get("clock") else ""
                print(f"  * [{f['tag']}] {f['name']} (Poder {f['power']} / {f['scale']}){clk_str}")
                print(f"      Reputação: {sc:+d} [{tier}] (Mod DC: {mod:+d}) | Favores: {fav} | Débitos: {deb}")
                if f.get("description"):
                    print(f"      Agenda: {f['description']}")
            if res.get("action_result"):
                act = res["action_result"]
                print(f"\n[Ação]: {json.dumps(act, ensure_ascii=False)}")
    else:
        parser.print_help()
