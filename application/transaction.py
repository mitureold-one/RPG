"""Fronteira transacional dos casos de uso que mutam o SSOT da campanha."""

from __future__ import annotations

import functools
import os
import shutil
from pathlib import Path
from typing import Sequence

from application.rebuild import rebuild_projections
from campaign.locator import parse_regras_manifest
from contracts.event import ActorRef, AppendResult, EventDraft
from contracts.ports import EventStore, create_event_store
from council import find_campaign
from council.helpers import atomic_write_text, campaign_lock
from resources.ledger import parse_diario_md
from temporal.calendar import game_time_to_minutes

_SNAPSHOT_DIRS = ("events", "projections", "artifacts", "snapshots")


def _capture_dir_snapshot(base: Path) -> dict[Path, bytes]:
    data: dict[Path, bytes] = {}
    if not base.exists():
        return data
    for p in base.rglob("*"):
        if p.is_file():
            data[p] = p.read_bytes()
    return data


def _restore_dir_snapshot(base: Path, existed: bool, snapshot: dict[Path, bytes]) -> None:
    if not existed:
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
        return
    if base.exists():
        for p in list(base.rglob("*")):
            if p.is_file() and p not in snapshot:
                try:
                    p.unlink()
                except OSError:
                    pass
    for p, raw in snapshot.items():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        except OSError:
            pass


def _serialized_campaign_mutation(func):
    """Serializa comandos que fazem read-modify-write no SSOT e no EventStore da campanha."""

    @functools.wraps(func)
    def wrapper(campaign_id, *args, **kwargs):
        allow_missing = func.__name__ == "cmd_rebuild"
        try:
            info = find_campaign(campaign_id, allow_missing_projections=allow_missing)
        except TypeError:
            info = find_campaign(campaign_id)
        except (ValueError, FileNotFoundError) as exc:
            return {"error": str(exc)}
        if not info:
            return func(campaign_id, *args, **kwargs)
        camp_dir = Path(info["dir"])
        timeout = float(os.environ.get("RPGPRO_LOCK_TIMEOUT", "10.0"))
        try:
            with campaign_lock(camp_dir, timeout=timeout):
                md_snapshots: dict[Path, str | None] = {}
                for key in ("ficha", "diario", "npcs", "mundo", "regras"):
                    path = info.get(key)
                    if path:
                        p_obj = Path(path)
                        md_snapshots[p_obj] = p_obj.read_text(encoding="utf-8") if p_obj.exists() else None

                dir_existed: dict[str, bool] = {}
                dir_snapshots: dict[str, dict[Path, bytes]] = {}
                for dname in _SNAPSHOT_DIRS:
                    dpath = camp_dir / dname
                    dir_existed[dname] = dpath.exists()
                    dir_snapshots[dname] = _capture_dir_snapshot(dpath)

                queue_path = camp_dir / "queue.jsonl"
                queue_bytes = queue_path.read_bytes() if queue_path.exists() else None

                try:
                    return func(campaign_id, *args, **kwargs)
                except BaseException:
                    for path, content in md_snapshots.items():
                        try:
                            if content is None:
                                if path.exists():
                                    path.unlink()
                            else:
                                atomic_write_text(path, content)
                        except OSError:
                            pass
                    for dname in _SNAPSHOT_DIRS:
                        _restore_dir_snapshot(
                            camp_dir / dname,
                            dir_existed[dname],
                            dir_snapshots[dname],
                        )
                    if queue_bytes is None:
                        if queue_path.exists():
                            try:
                                queue_path.unlink()
                            except OSError:
                                pass
                    else:
                        try:
                            queue_path.write_bytes(queue_bytes)
                        except OSError:
                            pass
                    raise
        except TimeoutError as exc:
            return {"error": str(exc)}

    return wrapper


def _read_campaign_baseline(camp_dir: Path) -> dict[str, str]:
    baseline: dict[str, str] = {}
    for fname in ("diario.md", "ficha.md", "npcs.md"):
        fpath = camp_dir / fname
        if fpath.exists():
            baseline[fname] = fpath.read_text(encoding="utf-8")
    return baseline


def ensure_campaign_event_log(
    camp_dir: Path,
    campaign_id: str,
    *,
    title: str | None = None,
    start_game_time: str | None = None,
) -> tuple[EventStore, int, str]:
    """Garante que o EventStore da campanha esteja inicializado e sincronizado com o SSOT."""
    store = create_event_store(camp_dir)
    last_seq = store.last_seq(campaign_id)

    regras_path = camp_dir / "regras.md"
    rules_manifest = parse_regras_manifest(regras_path) if regras_path.exists() else {}
    system_id = str(rules_manifest.get("system") or "default")
    calendar_cfg = rules_manifest.get("calendar") or "standard"

    diario_path = camp_dir / "diario.md"
    diario_ctx = parse_diario_md(diario_path) if diario_path.exists() else {}
    gt = start_game_time or str(diario_ctx.get("date_time") or "Dia 1, 08:00")
    gt_sort = game_time_to_minutes(
        gt,
        calendar=calendar_cfg if isinstance(calendar_cfg, dict) else None,
        fallback_turn=0,
    )

    baseline = _read_campaign_baseline(camp_dir)

    if last_seq == 0:
        camp_title = title or campaign_id
        res = store.append(
            campaign_id,
            [
                EventDraft(
                    type="campaign.created",
                    schema_version=1,
                    actor=ActorRef("system", "bootstrap"),
                    game_time=gt,
                    game_time_sort=gt_sort,
                    payload={
                        "title": camp_title,
                        "system": system_id,
                        "calendar": calendar_cfg,
                        "start_game_time": gt,
                        "config_version": 1,
                    },
                    meta={"baseline": baseline},
                )
            ],
            expected_last_seq=0,
        )
        created_ev = res.events[0]
        rebuild_projections(store, campaign_id, camp_dir, emit_audit_event=False)
        return store, created_ev.seq, created_ev.event_id

    proj_dir = camp_dir / "projections"
    out_of_band = False
    for fname, root_txt in baseline.items():
        proj_file = proj_dir / fname
        if proj_file.exists() and proj_file.read_text(encoding="utf-8") != root_txt:
            out_of_band = True
            break

    events = list(store.read(campaign_id, after_seq=0))
    last_ev = events[-1]

    if out_of_band:
        res_sync = store.append(
            campaign_id,
            [
                EventDraft(
                    type="command.executed",
                    schema_version=1,
                    actor=ActorRef("system", "sync"),
                    game_time=gt,
                    game_time_sort=max(last_ev.game_time_sort, gt_sort),
                    payload={
                        "command": "sync",
                        "status": "ok",
                        "summary": "Sincronização de edição direta no SSOT",
                        "files": dict(baseline),
                    },
                    meta={"dependencies": [last_ev.event_id]},
                )
            ],
            expected_last_seq=last_seq,
        )
        sync_ev = res_sync.events[-1]
        rebuild_projections(store, campaign_id, camp_dir, emit_audit_event=False)
        return store, sync_ev.seq, sync_ev.event_id

    return store, last_ev.seq, last_ev.event_id


def commit_events_and_project(
    camp_dir: Path,
    campaign_id: str,
    drafts: Sequence[EventDraft],
    store: EventStore,
    expected_last_seq: int,
) -> AppendResult:
    """Grava lote de eventos no EventStore primeiro e atualiza projeções + raiz atomicamente."""
    res = store.append(campaign_id, drafts, expected_last_seq=expected_last_seq)
    rebuild_projections(store, campaign_id, camp_dir, emit_audit_event=False)
    return res


def record_command_mutation(
    camp_dir: Path,
    campaign_id: str,
    store: EventStore,
    expected_last_seq: int,
    prev_event_id: str,
    drafts: Sequence[EventDraft],
) -> AppendResult:
    """Anexa dependências causais aos drafts de um comando (sem snapshots *_after em meta) e projeta."""
    enriched: list[EventDraft] = []
    for idx, d in enumerate(drafts):
        meta = dict(d.meta or {})
        if "dependencies" not in meta:
            meta["dependencies"] = [prev_event_id] if (idx == 0 and prev_event_id) else ([f"batch:{idx - 1}"] if idx > 0 else [])
        for k in ("diario_after", "ficha_after", "npcs_after"):
            meta.pop(k, None)
        enriched.append(
            EventDraft(
                type=d.type,
                schema_version=d.schema_version,
                actor=d.actor,
                payload=d.payload,
                game_time=d.game_time,
                game_time_sort=d.game_time_sort,
                causation_id=d.causation_id,
                correlation_id=d.correlation_id,
                meta=meta,
            )
        )
    return commit_events_and_project(camp_dir, campaign_id, enriched, store, expected_last_seq)


__all__ = [
    "_serialized_campaign_mutation",
    "commit_events_and_project",
    "ensure_campaign_event_log",
    "record_command_mutation",
]
